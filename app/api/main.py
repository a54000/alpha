"""FastAPI application for the read-only Swing Research Cockpit."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import os
import subprocess
import sys
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.api.dashboard_service import CockpitConfigurationError, CockpitDatabaseError, CockpitReadService
from app.api.disha_db_service import DishaDatabaseService, DishaDatabaseServiceError
from app.api.disha_service import DishaReadService, DishaReadServiceError
from app.api.market_breadth_service import MarketBreadthError, MarketBreadthService
from app.api.read_cache import clear_cache, get_or_set
from app.api.trade_analysis_service import (
    TradeAnalysisError,
    TradeAnalysisRequest,
    TradeAnalysisService,
    TradeAnalysisValidationError,
)
from app.api.rolling_portfolio_service import (
    RollingPortfolioError,
    RollingPortfolioRequest,
    RollingPortfolioSimulationService,
    RollingPortfolioValidationError,
)
from app.api.sector_rotation_service import SectorRotationError, SectorRotationService
from app.api.stock_analysis_service import StockAnalysisError, StockAnalysisService


REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

app = FastAPI(
    title="Swing Research Cockpit API",
    version="5.0.0",
    description="Read-only API for Swing V2.1 research, paper trading, and operations monitoring.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


DISHA_ENVIRONMENT_LABEL = "development"
DISHA_SYNC_CONFIRMATION_PHRASE = "SYNC DISHA"
DISHA_MUTATION_ALLOWLIST = [
    {
        "method": "POST",
        "path": "/api/db/sync",
        "label": "Sync local Disha artifacts to app DB",
        "requires_confirmation_phrase": DISHA_SYNC_CONFIRMATION_PHRASE,
        "trading_effect": "none",
    }
]
DISHA_PAPER_WORKFLOW_TYPES = {"session_checklist", "scanner_reconciliation", "mf_sweep", "fill_quality"}
DISHA_PAPER_WORKFLOW_STATUSES = {"complete", "pending", "blocked", "mismatch", "not_applicable"}


def get_service() -> CockpitReadService:
    return CockpitReadService()


def get_trade_analysis_service() -> TradeAnalysisService:
    return TradeAnalysisService()


def get_rolling_portfolio_service() -> RollingPortfolioSimulationService:
    return RollingPortfolioSimulationService()


def get_stock_analysis_service() -> StockAnalysisService:
    return StockAnalysisService()


def get_sector_rotation_service() -> SectorRotationService:
    return SectorRotationService()


def get_market_breadth_service() -> MarketBreadthService:
    return MarketBreadthService()


def get_disha_service() -> DishaReadService:
    return DishaReadService()


def get_disha_database_service() -> DishaDatabaseService:
    return DishaDatabaseService()


class TradeAnalysisRunPayload(BaseModel):
    start_date: date
    end_date: date
    strategy: Literal["TOP5_WEEKLY", "TOP10_WEEKLY", "TOP10_SECTOR_CAP", "SECTOR_ROTATION_ADX_ROLLING10"]
    recommendation_model: Literal["swing_v2_1", "sector_rotation_adx_1m3m"] = "swing_v2_1"
    initial_capital: float = Field(gt=0)
    charge_model: Literal["ZERODHA_DEFAULT"] = "ZERODHA_DEFAULT"


class RollingPortfolioPayload(BaseModel):
    start_date: date
    weeks: int = Field(default=1, ge=1, le=260)
    initial_capital: float = Field(default=1_000_000, gt=0)
    recommendation_model: Literal["swing_v2_1", "sector_rotation_adx_1m3m"] = "swing_v2_1"


class PipelineRunPayload(BaseModel):
    business_date: date
    portfolio_id: int = Field(default=1, ge=1)
    portfolio_size: int = Field(default=10, ge=1, le=50)
    max_candidate_rank: int = Field(default=5, ge=1, le=50)
    dry_run: bool = False
    sync_dry_run: bool = False
    rebalance_paper: bool = False
    resume: bool = False
    from_step: Literal[
        "",
        "angel_data_sync",
        "market_data_validation",
        "daily_bar_refresh",
        "feature_generation",
        "swing_v2_1_scoring",
        "recommendation_generation",
        "decision_journal_capture",
        "paper_portfolio_update",
        "monitoring_report_generation",
    ] = ""


class DishaSyncPayload(BaseModel):
    confirmation_phrase: str = Field(default="")


class DishaPaperWorkflowPayload(BaseModel):
    session: int = Field(ge=0, le=10_000)
    event_date: date
    workflow_type: str
    status: str
    notes: str = Field(min_length=1, max_length=2_000)
    symbol: str | None = Field(default=None, max_length=40)


class Nifty500ExpansionBackfillPayload(BaseModel):
    to_date: date = Field(default_factory=date.today)
    from_date: date = Field(default_factory=lambda: date(2021, 6, 14))
    execute: bool = False
    confirmation_phrase: str = ""
    batch_size: int = Field(default=25, ge=1, le=200)
    start_batch: int = Field(default=1, ge=1)
    end_batch: int | None = Field(default=None, ge=1)


@app.on_event("startup")
def validate_cockpit_configuration() -> None:
    try:
        CockpitReadService().validate_configuration()
    except CockpitConfigurationError:
        # Keep Disha and other artifact-backed endpoints available even when
        # the older Swing cockpit database environment is not configured.
        return


@app.exception_handler(CockpitConfigurationError)
def configuration_error_handler(_, exc: CockpitConfigurationError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "error_type": "configuration_error"},
    )


@app.exception_handler(CockpitDatabaseError)
def database_error_handler(_, exc: CockpitDatabaseError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "error_type": "database_error"},
    )


@app.exception_handler(DishaReadServiceError)
def disha_read_service_error_handler(_, exc: DishaReadServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "error_type": "disha_artifact_error"},
    )


@app.exception_handler(DishaDatabaseServiceError)
def disha_database_service_error_handler(_, exc: DishaDatabaseServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "error_type": "disha_database_error"},
    )


@app.exception_handler(SectorRotationError)
def sector_rotation_error_handler(_, exc: SectorRotationError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "error_type": "sector_rotation_error"},
    )


@app.exception_handler(MarketBreadthError)
def market_breadth_error_handler(_, exc: MarketBreadthError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "error_type": "market_breadth_error"},
    )


@app.get("/health")
def health(service: CockpitReadService = Depends(get_service)) -> dict[str, object]:
    return service.health()


@app.get("/api/health")
def disha_health(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.health()


@app.get("/api/readiness")
def disha_readiness(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.readiness()


@app.get("/api/rules/locked")
def disha_locked_rules(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.locked_rules()


@app.get("/api/backtest/summary")
def disha_backtest_summary(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.backtest_summary()


@app.get("/api/market/regime")
def disha_market_regime(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.market_regime()


@app.get("/api/signals/today")
def disha_signals_today(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.signals_today()


@app.get("/api/portfolio/summary")
def disha_portfolio_summary(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.portfolio_summary()


@app.get("/api/paper/status")
def disha_paper_status(service: DishaReadService = Depends(get_disha_service)) -> dict[str, object]:
    return service.paper_status()


@app.get("/api/paper/logs")
def disha_paper_logs(
    limit: int = Query(default=50, ge=1, le=500),
    service: DishaReadService = Depends(get_disha_service),
) -> dict[str, object]:
    return service.paper_logs(limit=limit)


@app.post("/api/db/sync")
def disha_db_sync(
    payload: DishaSyncPayload,
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    if payload.confirmation_phrase != DISHA_SYNC_CONFIRMATION_PHRASE:
        service.log_operator_event(
            action="artifact_sync",
            status="rejected",
            confirmation_status="invalid",
            summary="Artifact sync rejected: invalid confirmation phrase",
            raw_payload={"confirmation_supplied": bool(payload.confirmation_phrase)},
        )
        raise HTTPException(status_code=403, detail="Invalid Disha sync confirmation phrase")
    service.log_operator_event(
        action="artifact_sync",
        status="attempted",
        confirmation_status="valid",
        summary="Artifact sync attempt accepted",
        raw_payload={"confirmation_supplied": True},
    )
    counts = service.sync_artifacts()
    service.log_operator_event(
        action="artifact_sync",
        status="succeeded",
        confirmation_status="valid",
        summary="Artifact sync completed successfully",
        raw_payload={"counts": counts},
    )
    return {"status": "synced", "counts": counts}


@app.get("/api/db/sync/status")
def disha_db_sync_status(service: DishaDatabaseService = Depends(get_disha_database_service)) -> dict[str, object]:
    return service.sync_status()


@app.get("/api/db/readiness")
def disha_db_readiness(service: DishaDatabaseService = Depends(get_disha_database_service)) -> dict[str, object]:
    return service.readiness()


@app.get("/api/operator/boundary")
def disha_operator_boundary() -> dict[str, object]:
    return {
        "environment": DISHA_ENVIRONMENT_LABEL,
        "live_trading_enabled": False,
        "orders_enabled": False,
        "read_only_default": True,
        "mutation_allowlist": DISHA_MUTATION_ALLOWLIST
        + [
            {
                "method": "POST",
                "path": "/api/db/paper/workflow-events",
                "label": "Append paper-trading workflow note",
                "requires_confirmation_phrase": None,
                "trading_effect": "none",
            }
        ],
        "confirmation_phrase": DISHA_SYNC_CONFIRMATION_PHRASE,
        "disabled_actions": ["place_order", "modify_order", "cancel_order", "redeem_mf", "invest_mf"],
    }


@app.get("/api/db/audit/trail")
def disha_db_audit_trail(
    limit: int = Query(default=100, ge=1, le=500),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.audit_trail(limit=limit)


@app.get("/api/db/audit/operator")
def disha_db_operator_audit(
    limit: int = Query(default=100, ge=1, le=500),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.operator_events(limit=limit)


@app.get("/api/db/paper/workflow-events")
def disha_db_paper_workflow_events(
    limit: int = Query(default=100, ge=1, le=500),
    event_date: date | None = Query(default=None),
    session: int | None = Query(default=None, ge=0, le=10_000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_workflow_events(limit=limit, event_date=event_date, session=session)


@app.get("/api/db/paper/workflow-events/export.csv")
def disha_db_paper_workflow_events_export(
    limit: int = Query(default=500, ge=1, le=5000),
    event_date: date | None = Query(default=None),
    session: int | None = Query(default=None, ge=0, le=10_000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> Response:
    rows = service.paper_workflow_events(limit=limit, event_date=event_date, session=session)["events"]
    return Response(
        content=service.rows_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=disha_paper_workflow_events.csv"},
    )


@app.get("/api/db/audit/trail/export.csv")
def disha_db_audit_trail_export(
    limit: int = Query(default=500, ge=1, le=5000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> Response:
    rows = service.audit_trail(limit=limit)["events"]
    return Response(
        content=service.rows_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=disha_operational_audit_trail.csv"},
    )


@app.get("/api/db/paper/review-packet")
def disha_db_paper_review_packet(
    event_date: date | None = Query(default=None),
    session: int | None = Query(default=None, ge=0, le=10_000),
    limit: int = Query(default=500, ge=1, le=5000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_review_packet(event_date=event_date, session=session, limit=limit)


@app.get("/api/db/paper/session-health")
def disha_db_paper_session_health(
    event_date: date | None = Query(default=None),
    session: int | None = Query(default=None, ge=0, le=10_000),
    limit: int = Query(default=500, ge=1, le=5000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_session_health(event_date=event_date, session=session, limit=limit)


@app.get("/api/db/paper/day-closeout")
def disha_db_paper_day_closeout(
    event_date: date | None = Query(default=None),
    session: int | None = Query(default=None, ge=0, le=10_000),
    limit: int = Query(default=500, ge=1, le=5000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_day_closeout(event_date=event_date, session=session, limit=limit)


@app.get("/api/db/paper/workflow-gap-suggestion")
def disha_db_paper_workflow_gap_suggestion(
    event_date: date | None = Query(default=None),
    session: int | None = Query(default=None, ge=0, le=10_000),
    limit: int = Query(default=500, ge=1, le=5000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_workflow_gap_suggestion(event_date=event_date, session=session, limit=limit)


@app.get("/api/db/paper/milestones")
def disha_db_paper_milestones(
    limit: int = Query(default=5000, ge=1, le=10000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_milestone_tracker(limit=limit)


@app.get("/api/db/paper/day1-launch-checklist")
def disha_db_paper_day1_launch_checklist(
    limit: int = Query(default=5000, ge=1, le=10000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_day1_launch_checklist(limit=limit)


@app.get("/api/db/scanner/remediation")
def disha_db_scanner_remediation(
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.scanner_remediation()


@app.get("/api/db/scanner/rerun-runbook")
def disha_db_scanner_rerun_runbook(
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.scanner_rerun_runbook()


@app.get("/api/db/scanner/reconciliation-suggestion")
def disha_db_scanner_reconciliation_suggestion(
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.scanner_reconciliation_suggestion()


@app.get("/api/db/paper/review-packet.md")
def disha_db_paper_review_packet_markdown(
    event_date: date | None = Query(default=None),
    session: int | None = Query(default=None, ge=0, le=10_000),
    limit: int = Query(default=500, ge=1, le=5000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> Response:
    suffix = event_date.isoformat() if event_date else "all"
    if session is not None:
        suffix = f"{suffix}_session_{session}"
    return Response(
        content=service.paper_review_packet_markdown(event_date=event_date, session=session, limit=limit),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=disha_paper_review_packet_{suffix}.md"},
    )


@app.post("/api/db/paper/workflow-events")
def disha_db_append_paper_workflow_event(
    payload: DishaPaperWorkflowPayload,
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    if payload.workflow_type not in DISHA_PAPER_WORKFLOW_TYPES:
        raise HTTPException(status_code=422, detail="Invalid paper workflow type")
    if payload.status not in DISHA_PAPER_WORKFLOW_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid paper workflow status")
    event = service.append_paper_workflow_event(
        session=payload.session,
        event_date=payload.event_date,
        workflow_type=payload.workflow_type,
        status=payload.status,
        symbol=payload.symbol,
        notes=payload.notes,
        raw_payload=payload.model_dump(mode="json"),
    )
    service.log_operator_event(
        action="paper_workflow_append",
        status="succeeded",
        confirmation_status="not_required",
        summary=f"Paper workflow note appended: {payload.workflow_type}",
        raw_payload={"workflow_event_id": event["workflow_event_id"], "workflow_type": payload.workflow_type, "status": payload.status},
    )
    return {"status": "appended", "event": event}


@app.get("/api/db/signals")
def disha_db_signals(
    limit: int = Query(default=100, ge=1, le=1000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.signals(limit=limit)


@app.get("/api/db/positions")
def disha_db_positions(
    limit: int = Query(default=100, ge=1, le=1000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.positions(limit=limit)


@app.get("/api/db/portfolio/snapshots")
def disha_db_portfolio_snapshots(
    limit: int = Query(default=100, ge=1, le=1000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.portfolio_snapshots(limit=limit)


@app.get("/api/db/paper/events")
def disha_db_paper_events(
    limit: int = Query(default=100, ge=1, le=1000),
    service: DishaDatabaseService = Depends(get_disha_database_service),
) -> dict[str, object]:
    return service.paper_events(limit=limit)


@app.get("/dashboard")
def dashboard(
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    return get_or_set(("dashboard",), service.dashboard, refresh=refresh)


@app.get("/recommendations/latest")
def recommendations_latest(
    model: str = Query(default="swing_v2_1"),
    limit: int = Query(default=20, ge=1, le=100),
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    return get_or_set(
        ("recommendations_latest", model, limit),
        lambda: service.latest_recommendations(model=model, limit=limit),
        refresh=refresh,
    )


@app.get("/recommendations/{symbol}/explanation")
def recommendation_explanation(
    symbol: str,
    recommendation_type: str = Query(default="swing_v2_1"),
    business_date: date | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    normalized_symbol = symbol.upper()
    return get_or_set(
        ("recommendation_explanation", normalized_symbol, recommendation_type, business_date),
        lambda: service.recommendation_explanation(
            symbol=normalized_symbol,
            recommendation_type=recommendation_type,
            business_date=business_date,
        ),
        refresh=refresh,
    )


@app.get("/portfolio")
def portfolio(
    portfolio_id: int | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    return get_or_set(
        ("portfolio", portfolio_id),
        lambda: service.portfolio(portfolio_id=portfolio_id),
        refresh=refresh,
    )


@app.get("/portfolio/attribution")
def portfolio_attribution(
    portfolio_id: int | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    return get_or_set(
        ("portfolio_attribution", portfolio_id),
        lambda: service.portfolio_attribution(portfolio_id=portfolio_id),
        refresh=refresh,
    )


@app.get("/trades")
def trades(
    portfolio_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    return get_or_set(
        ("trades", portfolio_id, limit),
        lambda: service.trades(portfolio_id=portfolio_id, limit=limit),
        refresh=refresh,
    )


@app.get("/pipeline/status")
def pipeline_status(
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    return get_or_set(("pipeline_status",), service.pipeline_status, refresh=refresh)


@app.post("/pipeline/run")
def run_pipeline(payload: PipelineRunPayload) -> dict[str, object]:
    logs_dir = REPO_ROOT / "logs" / "daily_pipeline"
    reports_dir = REPO_ROOT / "reports"
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    cleared_cache_entries = clear_cache()

    business_date = payload.business_date.isoformat()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"daily_pipeline_ui_{business_date}_{timestamp}.log"
    summary_path = reports_dir / f"phase4b_full_daily_pipeline_{business_date}.json"

    command = [
        sys.executable,
        "scripts/run_full_daily_pipeline.py",
        "--business-date",
        business_date,
        "--portfolio-id",
        str(payload.portfolio_id),
        "--portfolio-size",
        str(payload.portfolio_size),
        "--max-candidate-rank",
        str(payload.max_candidate_rank),
        "--output-json",
        str(summary_path),
    ]
    if payload.dry_run:
        command.append("--dry-run")
    if payload.sync_dry_run:
        command.append("--sync-dry-run")
    if payload.rebalance_paper:
        command.append("--rebalance-paper")
    if payload.resume:
        command.append("--resume")
    if payload.from_step:
        command.extend(["--from-step", payload.from_step])

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    log_handle = log_path.open("w", encoding="utf-8")
    log_handle.write(f"[{datetime.now().isoformat()}] Starting UI-triggered pipeline\n")
    log_handle.write(f"ProjectRoot={REPO_ROOT}\n")
    log_handle.write(f"BusinessDate={business_date}\n")
    log_handle.write(f"Command={' '.join(command)}\n\n")
    log_handle.flush()

    try:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
        )
    except OSError as exc:
        log_handle.close()
        raise HTTPException(status_code=503, detail=f"Unable to start pipeline: {exc}") from exc

    return {
        "status": "started",
        "pid": process.pid,
        "business_date": business_date,
        "log_path": str(log_path),
        "summary_path": str(summary_path),
        "command": command,
        "what_this_does": [
            "Syncs missing Angel 15-minute candles.",
            "Validates latest market data.",
            "Refreshes cleaned pilot daily bars.",
            "Regenerates strategy features.",
            "Computes scores and recommendations.",
            "Captures recommendation explanations.",
            "Updates the paper portfolio when enabled.",
            "Generates monitoring output.",
        ],
        "safety": {
            "broker_orders": False,
            "strategy_changes": False,
            "production_tables_modified": False,
        },
        "cache": {
            "cleared_read_entries": cleared_cache_entries,
            "reason": "pipeline run requested",
        },
    }


@app.post("/pipeline/universe/audit")
def run_universe_audit() -> dict[str, object]:
    logs_dir = REPO_ROOT / "logs" / "daily_pipeline"
    reports_dir = REPO_ROOT / "reports"
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"nifty500_universe_audit_{timestamp}.log"
    command = [sys.executable, "scripts/audit_nifty500_universe_expansion.py"]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    with log_path.open("w", encoding="utf-8") as log_handle:
        log_handle.write(f"[{datetime.now().isoformat()}] Starting universe audit\n")
        log_handle.write(f"ProjectRoot={REPO_ROOT}\n")
        log_handle.write(f"Command={' '.join(command)}\n\n")
        log_handle.flush()
        try:
            completed = subprocess.run(command, cwd=REPO_ROOT, stdout=log_handle, stderr=subprocess.STDOUT, env=env, check=False)
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Unable to start universe audit: {exc}") from exc
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "log_path": str(log_path),
        "command": command,
        "reports": [
            str(REPO_ROOT / "reports" / "nifty500_backfill_status.csv"),
            str(REPO_ROOT / "reports" / "nifty500_universe_expansion_audit.json"),
            str(REPO_ROOT / "docs" / "PHASE7A_NIFTY500_UNIVERSE_EXPANSION.md"),
        ],
    }


@app.post("/pipeline/universe/prepare-backfill")
def prepare_universe_backfill() -> dict[str, object]:
    logs_dir = REPO_ROOT / "logs" / "daily_pipeline"
    reports_dir = REPO_ROOT / "reports"
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"nifty500_backfill_prep_{timestamp}.log"
    command = [sys.executable, "scripts/prepare_nifty500_expansion_batches.py"]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    with log_path.open("w", encoding="utf-8") as log_handle:
        log_handle.write(f"[{datetime.now().isoformat()}] Preparing backfill batches\n")
        log_handle.write(f"ProjectRoot={REPO_ROOT}\n")
        log_handle.write(f"Command={' '.join(command)}\n\n")
        log_handle.flush()
        try:
            completed = subprocess.run(command, cwd=REPO_ROOT, stdout=log_handle, stderr=subprocess.STDOUT, env=env, check=False)
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Unable to prepare backfill batches: {exc}") from exc
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "log_path": str(log_path),
        "command": command,
        "reports": [
            str(REPO_ROOT / "reports" / "nifty500_expansion_universe_symbols.csv"),
            str(REPO_ROOT / "reports" / "nifty500_needs_angel_backfill_symbols.csv"),
            str(REPO_ROOT / "reports" / "nifty500_backfill_batches"),
            str(REPO_ROOT / "reports" / "nifty500_expansion_batch_plan.json"),
        ],
    }


@app.post("/pipeline/universe/run-backfill")
def run_universe_backfill(payload: Nifty500ExpansionBackfillPayload) -> dict[str, object]:
    if payload.execute and payload.confirmation_phrase != "RUN NIFTY500 BACKFILL":
        raise HTTPException(status_code=403, detail="Invalid confirmation phrase for live backfill execution")
    logs_dir = REPO_ROOT / "logs" / "daily_pipeline"
    reports_dir = REPO_ROOT / "reports"
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"nifty500_backfill_{timestamp}.log"
    command = [
        sys.executable,
        "scripts/run_nifty500_backfill_batches.py",
        "--from-date",
        payload.from_date.isoformat(),
        "--to-date",
        payload.to_date.isoformat(),
        "--start-batch",
        str(payload.start_batch),
        "--summary-json",
        "reports/nifty500_backfill_batches_summary.json",
    ]
    if payload.end_batch is not None:
        command.extend(["--end-batch", str(payload.end_batch)])
    if payload.execute:
        command.append("--execute")
    command.extend(["--batch-dir", "reports/nifty500_backfill_batches"])
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    with log_path.open("w", encoding="utf-8") as log_handle:
        log_handle.write(f"[{datetime.now().isoformat()}] Starting backfill batches\n")
        log_handle.write(f"ProjectRoot={REPO_ROOT}\n")
        log_handle.write(f"Command={' '.join(command)}\n\n")
        log_handle.flush()
        try:
            completed = subprocess.run(command, cwd=REPO_ROOT, stdout=log_handle, stderr=subprocess.STDOUT, env=env, check=False)
        except OSError as exc:
            raise HTTPException(status_code=503, detail=f"Unable to start backfill batches: {exc}") from exc
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "log_path": str(log_path),
        "command": command,
        "safety": {
            "execute": payload.execute,
            "confirmation_required": True,
            "live_angel_calls": payload.execute,
        },
        "reports": [
            str(REPO_ROOT / "reports" / "nifty500_backfill_batches_summary.json"),
            str(REPO_ROOT / "reports" / "nifty500_backfill_status.csv"),
        ],
    }


@app.get("/research/metrics")
def research_metrics(
    refresh: bool = Query(default=False),
    service: CockpitReadService = Depends(get_service),
) -> dict[str, object]:
    return get_or_set(("research_metrics",), service.research_metrics, refresh=refresh)


@app.get("/research/sector-rotation/insights")
def sector_rotation_insights(
    as_of: date | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: SectorRotationService = Depends(get_sector_rotation_service),
) -> dict[str, object]:
    return get_or_set(
        ("sector_rotation_insights", as_of),
        lambda: service.insights(as_of=as_of),
        refresh=refresh,
    )


@app.get("/research/sector-rotation/industry-confirmation")
def sector_rotation_industry_confirmation(
    sector: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: SectorRotationService = Depends(get_sector_rotation_service),
) -> dict[str, object]:
    return get_or_set(
        ("sector_rotation_industry_confirmation", sector, as_of),
        lambda: service.industry_confirmation(sector=sector, as_of=as_of),
        refresh=refresh,
    )


@app.get("/market-breadth")
def market_breadth(
    as_of: date | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: MarketBreadthService = Depends(get_market_breadth_service),
) -> dict[str, object]:
    return get_or_set(
        ("market_breadth", as_of),
        lambda: service.breadth(as_of=as_of),
        refresh=refresh,
    )


@app.get("/stock-analysis/search")
def stock_analysis_search(
    q: str = Query(default="", min_length=0, max_length=40),
    limit: int = Query(default=20, ge=1, le=50),
    refresh: bool = Query(default=False),
    service: StockAnalysisService = Depends(get_stock_analysis_service),
) -> dict[str, object]:
    try:
        normalized_query = q.strip().upper()
        return get_or_set(
            ("stock_analysis_search", normalized_query, limit),
            lambda: service.search_symbols(normalized_query, limit=limit),
            refresh=refresh,
        )
    except StockAnalysisError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/stock-analysis/{symbol}")
def stock_analysis_dashboard(
    symbol: str,
    refresh: bool = Query(default=False),
    service: StockAnalysisService = Depends(get_stock_analysis_service),
) -> dict[str, object]:
    try:
        normalized_symbol = symbol.upper()
        return get_or_set(
            ("stock_analysis_dashboard", normalized_symbol),
            lambda: service.dashboard(normalized_symbol),
            refresh=refresh,
        )
    except StockAnalysisError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/research/rolling-portfolio/defaults")
def rolling_portfolio_defaults(
    recommendation_model: Literal["swing_v2_1", "sector_rotation_adx_1m3m"] = Query(default="swing_v2_1"),
    refresh: bool = Query(default=False),
    service: RollingPortfolioSimulationService = Depends(get_rolling_portfolio_service),
) -> dict[str, object]:
    try:
        return get_or_set(
            ("rolling_portfolio_defaults", recommendation_model),
            lambda: service.defaults(recommendation_model=recommendation_model),
            refresh=refresh,
        )
    except RollingPortfolioError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/research/rolling-portfolio/simulate")
def simulate_rolling_portfolio(
    payload: RollingPortfolioPayload,
    service: RollingPortfolioSimulationService = Depends(get_rolling_portfolio_service),
) -> dict[str, object]:
    try:
        return service.simulate(
            RollingPortfolioRequest(
                start_date=payload.start_date,
                weeks=payload.weeks,
                initial_capital=payload.initial_capital,
                recommendation_model=payload.recommendation_model,
            )
        )
    except RollingPortfolioValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RollingPortfolioError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/research/trade-analysis/run")
def run_trade_analysis(
    payload: TradeAnalysisRunPayload,
    service: TradeAnalysisService = Depends(get_trade_analysis_service),
) -> dict[str, object]:
    try:
        return service.run(
            TradeAnalysisRequest(
                start_date=payload.start_date,
                end_date=payload.end_date,
                strategy=payload.strategy,
                recommendation_model=payload.recommendation_model,
                initial_capital=payload.initial_capital,
                charge_model=payload.charge_model,
            )
        )
    except TradeAnalysisValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TradeAnalysisError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/research/trade-analysis/model-status")
def trade_analysis_model_status(
    model: Literal["swing_v2_1", "sector_rotation_adx_1m3m"] = Query(default="sector_rotation_adx_1m3m"),
    service: TradeAnalysisService = Depends(get_trade_analysis_service),
) -> dict[str, object]:
    try:
        return service.recommendation_model_status(model)
    except TradeAnalysisError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/research/trade-analysis/{report_id}")
def get_trade_analysis(
    report_id: str,
    refresh: bool = Query(default=False),
    service: TradeAnalysisService = Depends(get_trade_analysis_service),
) -> dict[str, object]:
    try:
        return get_or_set(
            ("trade_analysis_report", report_id),
            lambda: service.get(report_id),
            refresh=refresh,
        )
    except TradeAnalysisError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/research/trade-analysis/{report_id}/artifact/{artifact_name}")
def get_trade_analysis_artifact(
    report_id: str,
    artifact_name: str,
    service: TradeAnalysisService = Depends(get_trade_analysis_service),
) -> FileResponse:
    try:
        path = service.artifact_path(report_id, artifact_name)
    except TradeAnalysisError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    media_type = "text/markdown" if artifact_name.endswith(".md") else "text/csv" if artifact_name.endswith(".csv") else "application/json"
    return FileResponse(path, media_type=media_type, filename=artifact_name)
