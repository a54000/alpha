"""Dash dashboard for Disha paper-trading operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from dash import Dash, Input, Output, dash_table, dcc, html
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "results" / "sprint_2_8"
SPRINT_27 = ROOT / "results" / "sprint_2_7"
SPRINT_23 = ROOT / "results" / "sprint_2_3"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except Exception:
        return "-"


def _fmt_num(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except Exception:
        return "-"


def _metric_card(label: str, value: str, detail: str = "") -> html.Div:
    return html.Div(
        [html.Div(label, className="metric-label"), html.Div(value, className="metric-value"), html.Div(detail, className="metric-detail")],
        className="metric-card",
    )


def _table(frame: pd.DataFrame, table_id: str, max_rows: int = 10) -> dash_table.DataTable:
    if frame.empty:
        frame = pd.DataFrame([{"status": "No rows yet"}])
    frame = frame.tail(max_rows)
    return dash_table.DataTable(
        id=table_id,
        data=frame.to_dict("records"),
        columns=[{"name": column, "id": column} for column in frame.columns],
        page_size=max_rows,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "Inter, Segoe UI, Arial, sans-serif",
            "fontSize": "12px",
            "padding": "8px",
            "textAlign": "left",
            "maxWidth": "220px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
        style_header={"fontWeight": "700", "backgroundColor": "#eef2f6"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#fafbfc"}],
    )


def _equity_figure() -> go.Figure:
    equity = _read_csv(SPRINT_23 / "static_15_80_05_idle_yield" / "combined_equity_curve.csv")
    fig = go.Figure()
    if not equity.empty and {"date", "equity"}.issubset(equity.columns):
        fig.add_trace(go.Scatter(x=equity["date"], y=equity["equity"], mode="lines", name="Equity", line={"color": "#1f6f5b", "width": 2}))
    fig.update_layout(
        margin={"l": 24, "r": 16, "t": 16, "b": 24},
        height=260,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis={"showgrid": False},
        yaxis={"gridcolor": "#edf0f2"},
    )
    return fig


def _layout() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="refresh", interval=60_000, n_intervals=0),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("Disha Paper Trading"),
                            html.P("Operational dashboard for the locked V4b + VCP + idle-yield setup."),
                        ],
                        className="title-block",
                    ),
                    html.Button("Refresh", id="manual-refresh", n_clicks=0, className="refresh-button"),
                ],
                className="topbar",
            ),
            html.Div(id="metrics", className="metric-grid"),
            html.Div(
                [
                    html.Div([html.H2("Portfolio Curve"), dcc.Graph(id="equity-graph", config={"displayModeBar": False})], className="panel panel-wide"),
                    html.Div([html.H2("Caveats"), html.Div(id="caveats")], className="panel"),
                ],
                className="content-grid",
            ),
            html.Div(
                [
                    html.Div([html.H2("Latest Scanner"), html.Div(id="scanner-summary"), html.Div(id="scanner-table")], className="panel panel-wide"),
                    html.Div([html.H2("Order Sheet"), html.Div(id="orders-table")], className="panel panel-wide"),
                    html.Div([html.H2("MF Sweep"), html.Div(id="mf-table")], className="panel panel-wide"),
                    html.Div([html.H2("Fill Quality"), html.Div(id="fills-table")], className="panel panel-wide"),
                    html.Div([html.H2("Positions"), html.Div(id="positions-table")], className="panel panel-wide"),
                ],
                className="section-stack",
            ),
        ],
        className="page",
    )


app = Dash(__name__)
app.title = "Disha Paper Trading"
app.layout = _layout


@app.callback(
    Output("metrics", "children"),
    Output("equity-graph", "figure"),
    Output("caveats", "children"),
    Output("scanner-summary", "children"),
    Output("scanner-table", "children"),
    Output("orders-table", "children"),
    Output("mf-table", "children"),
    Output("fills-table", "children"),
    Output("positions-table", "children"),
    Input("refresh", "n_intervals"),
    Input("manual-refresh", "n_clicks"),
)
def refresh_dashboard(_: int, __: int):
    status = _read_json(PAPER / "paper_trading_status.json")
    tax = _read_json(SPRINT_27 / "tax_adjusted_yield.json")
    scanner = _read_json(PAPER / "day0_scanner_dry_run_summary.json")
    readiness = _read_json(SPRINT_27 / "risk_controls.json")
    metrics = [
        _metric_card("Readiness", "Ready" if status.get("ready") else "Check", f"Missing files: {len(status.get('missing_files', []))}"),
        _metric_card("Sessions Logged", str(status.get("sessions_logged", 0)), "30-session paper test"),
        _metric_card("Production CAGR", _fmt_pct(tax.get("production_cagr_est")), "4.81% net idle yield"),
        _metric_card("Max DD", _fmt_pct(tax.get("max_drawdown_at_rate")), "production estimate"),
        _metric_card("Scanner Date", str(scanner.get("scan_date", "-")), f"{scanner.get('symbols_scanned', 0)} symbols"),
        _metric_card("Signals", f"V4b {scanner.get('v4b_signals', 0)} | VCP {scanner.get('vcp_signals', 0)}", str(scanner.get("market", {}).get("regime_label", "-"))),
    ]
    caveat_items = [
        "09:15 bid-ask spread validation needs live order-book data.",
        "AMFI NAV source selected; daily NAV workflow still needs manual confirmation.",
        "MF redemption/sweep workflow needs 20-session paper validation.",
        f"Daily loss halt: {_fmt_pct((readiness.get('portfolio') or {}).get('daily_loss_halt'))}",
    ]
    caveats = html.Ul([html.Li(item) for item in caveat_items], className="caveat-list")
    scanner_summary = html.Div(
        [
            html.Span(f"Regime: {scanner.get('market', {}).get('regime_label', '-')}"),
            html.Span(f"VCP gate: {scanner.get('market', {}).get('vcp_market_gate', '-')}"),
            html.Span(f"NIFTY 60D: {_fmt_pct(scanner.get('market', {}).get('nifty_return_60d'))}"),
        ],
        className="inline-facts",
    )
    return (
        metrics,
        _equity_figure(),
        caveats,
        scanner_summary,
        _table(_read_csv(PAPER / "day0_scanner_dry_run_signals.csv"), "scanner"),
        _table(_read_csv(PAPER / "day1_order_sheet.csv"), "orders"),
        _table(_read_csv(PAPER / "mf_sweep_log.csv"), "mf"),
        _table(_read_csv(PAPER / "fill_quality_log.csv"), "fills"),
        _table(_read_csv(PAPER / "position_ledger.csv"), "positions"),
    )


app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body { margin: 0; background: #f4f6f7; color: #17212b; font-family: Inter, "Segoe UI", Arial, sans-serif; }
            .page { padding: 24px; max-width: 1480px; margin: 0 auto; }
            .topbar { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 18px; }
            h1 { margin: 0; font-size: 28px; line-height: 1.2; letter-spacing: 0; }
            h2 { margin: 0 0 12px; font-size: 16px; line-height: 1.3; letter-spacing: 0; }
            p { margin: 6px 0 0; color: #5f6f7d; }
            .refresh-button { border: 1px solid #b9c5ce; background: white; border-radius: 6px; padding: 9px 14px; cursor: pointer; }
            .metric-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
            .metric-card, .panel { background: white; border: 1px solid #dce3e8; border-radius: 8px; box-shadow: 0 1px 2px rgba(20, 31, 42, 0.04); }
            .metric-card { padding: 14px; min-height: 76px; }
            .metric-label { color: #647482; font-size: 12px; font-weight: 700; text-transform: uppercase; }
            .metric-value { font-size: 22px; font-weight: 750; margin-top: 8px; }
            .metric-detail { color: #6d7b86; font-size: 12px; margin-top: 4px; }
            .content-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; margin-bottom: 12px; }
            .section-stack { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
            .panel { padding: 14px; min-width: 0; }
            .panel-wide { min-width: 0; }
            .inline-facts { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
            .inline-facts span { background: #eef5f2; border: 1px solid #cfe1d9; color: #1f5b4c; border-radius: 6px; padding: 6px 8px; font-size: 12px; font-weight: 700; }
            .caveat-list { margin: 0; padding-left: 18px; color: #344451; line-height: 1.6; }
            @media (max-width: 1100px) { .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .content-grid, .section-stack { grid-template-columns: 1fr; } }
            @media (max-width: 700px) { .page { padding: 14px; } .metric-grid { grid-template-columns: 1fr 1fr; } .topbar { align-items: flex-start; flex-direction: column; } }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


if __name__ == "__main__":
    app.run_server(host="127.0.0.1", port=8050, debug=False)

