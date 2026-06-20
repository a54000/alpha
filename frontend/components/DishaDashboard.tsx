"use client";

import { useState } from "react";
import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Badge, Button, Card, Col, Descriptions, Empty, Input, InputNumber, Modal, Progress, Row, Select, Space, Statistic, Table, Tabs, Tag, Typography, message } from "antd";
import { API_BASE } from "@/lib/api";

type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

type TableRow = Record<string, unknown> & { key: number | string };

export type LockedRules = {
  portfolio?: {
    name?: string;
    status?: string;
    initial_capital?: number;
    allocations?: Record<string, unknown>;
  };
  v4b_mean_reversion?: Record<string, unknown>;
  vcp_breakout?: Record<string, unknown>;
  idle_yield_proxy?: Record<string, unknown>;
  risk_controls?: Record<string, unknown>;
};

export type BacktestSummary = {
  portfolio?: Record<string, string>;
  sleeves?: Record<string, Record<string, string>>;
  key_findings?: string[];
  open_caveats?: string[];
};

export type MarketRegime = {
  latest?: Record<string, unknown>;
  distribution?: Record<string, { sessions?: number; pct?: number }>;
  total_sessions?: number;
};

export type SignalsToday = {
  count?: number;
  summary?: Record<string, unknown>;
  signals?: Array<Record<string, unknown>>;
};

export type PaperStatus = {
  ready?: boolean;
  sessions_logged?: number;
  scanner_reconciliations?: number;
  mf_sweep_events?: number;
  fill_checks?: number;
  open_positions_logged?: number;
};

export type PortfolioSummary = {
  summary?: Record<string, unknown>;
};

export type DbCount = {
  count?: number;
  signals?: Array<Record<string, unknown>>;
  positions?: Array<Record<string, unknown>>;
  snapshots?: Array<Record<string, unknown>>;
  events?: Array<Record<string, unknown>>;
};

export type SyncStatus = {
  counts?: Record<string, number>;
  latest_sync_at?: string | null;
};

export type ReadinessPayload = {
  status?: string;
  artifact_checks?: Record<string, { exists?: boolean; status?: string; modified_at?: string | null }>;
  paper?: Record<string, unknown>;
  scanner?: Record<string, unknown>;
};

export type DbReadinessPayload = {
  status?: string;
  migration?: { current?: string | null; expected?: string; status?: string };
  tables?: Record<string, { exists?: boolean; status?: string }>;
};

export type AuditTrailPayload = {
  count?: number;
  events?: Array<Record<string, unknown>>;
};

export type OperatorBoundaryPayload = {
  environment?: string;
  live_trading_enabled?: boolean;
  orders_enabled?: boolean;
  read_only_default?: boolean;
  confirmation_phrase?: string;
  mutation_allowlist?: Array<Record<string, unknown>>;
  disabled_actions?: string[];
};

export type PaperWorkflowEventsPayload = {
  count?: number;
  events?: Array<Record<string, unknown>>;
};

export type PaperSessionHealthPayload = {
  verdict?: string;
  completion_pct?: number;
  missing_workflows?: string[];
  unresolved_items?: Array<Record<string, unknown>>;
  checks?: Array<Record<string, unknown>>;
  workflow_event_count?: number;
};

export type PaperMilestonesPayload = {
  verdict?: string;
  sessions_logged?: number;
  latest_session?: number | null;
  milestones?: Array<Record<string, unknown>>;
  unresolved_items?: Array<Record<string, unknown>>;
};

export type PaperDay1LaunchPayload = {
  verdict?: string;
  ready_count?: number;
  review_count?: number;
  blocked_count?: number;
  steps?: Array<Record<string, unknown>>;
  operator_flow?: string[];
  guardrails?: string[];
};

export type ScannerRemediationPayload = {
  status?: string;
  primary_gap?: string;
  next_action?: string;
  artifact?: Record<string, unknown>;
  database?: Record<string, unknown>;
  safe_actions?: string[];
  disabled_actions?: string[];
};

export type ScannerRerunRunbookPayload = {
  status?: string;
  runbook_path?: string;
  runbook_exists?: boolean;
  primary_command?: string;
  research_override_command?: string;
  working_directory?: string;
  expected_outputs?: string[];
  post_run_checks?: string[];
  workflow_capture?: Record<string, unknown>;
  guardrails?: string[];
};

export type ScannerReconciliationSuggestionPayload = {
  suggested_payload?: Record<string, unknown>;
  review_action?: string;
  guardrails?: string[];
};

export type PaperDayCloseoutPayload = {
  verdict?: string;
  blockers?: string[];
  session_health?: PaperSessionHealthPayload;
  scanner_suggestion?: ScannerReconciliationSuggestionPayload;
  milestones?: PaperMilestonesPayload;
  review_counts?: Record<string, unknown>;
  export_links?: Record<string, string>;
  operator_closeout_steps?: string[];
  guardrails?: string[];
};

export type PaperWorkflowGapSuggestionPayload = {
  status?: string;
  missing_workflows?: string[];
  suggested_payload?: Record<string, unknown> | null;
  review_action?: string;
  guardrails?: string[];
};

export type DishaDashboardProps = {
  rulesResult: ApiResult<LockedRules>;
  backtestResult: ApiResult<BacktestSummary>;
  regimeResult: ApiResult<MarketRegime>;
  signalsResult: ApiResult<SignalsToday>;
  paperResult: ApiResult<PaperStatus>;
  portfolioResult: ApiResult<PortfolioSummary>;
  readinessResult: ApiResult<ReadinessPayload>;
  dbReadinessResult: ApiResult<DbReadinessPayload>;
  auditResult: ApiResult<AuditTrailPayload>;
  operatorBoundaryResult: ApiResult<OperatorBoundaryPayload>;
  paperWorkflowResult: ApiResult<PaperWorkflowEventsPayload>;
  paperSessionHealthResult: ApiResult<PaperSessionHealthPayload>;
  paperMilestonesResult: ApiResult<PaperMilestonesPayload>;
  paperDay1LaunchResult: ApiResult<PaperDay1LaunchPayload>;
  scannerRemediationResult: ApiResult<ScannerRemediationPayload>;
  scannerRerunRunbookResult: ApiResult<ScannerRerunRunbookPayload>;
  scannerReconciliationSuggestionResult: ApiResult<ScannerReconciliationSuggestionPayload>;
  paperDayCloseoutResult: ApiResult<PaperDayCloseoutPayload>;
  paperWorkflowGapSuggestionResult: ApiResult<PaperWorkflowGapSuggestionPayload>;
  db: {
    signals: ApiResult<DbCount>;
    positions: ApiResult<DbCount>;
    snapshots: ApiResult<DbCount>;
    events: ApiResult<DbCount>;
    syncStatus: ApiResult<SyncStatus>;
  };
};

const money = (value: unknown): string => {
  if (value === null || value === undefined || value === "") return "n/a";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return number.toLocaleString("en-IN", { maximumFractionDigits: 2 });
};

const percent = (value: unknown) => {
  const number = Number(value);
  if (Number.isNaN(number)) return "n/a";
  return `${(number * 100).toFixed(1)}%`;
};

const text = (value: unknown) => {
  if (value === null || value === undefined || value === "") return "n/a";
  return String(value);
};

const pctNumber = (value: unknown) => {
  const number = Number(value);
  if (Number.isNaN(number)) return 0;
  return Math.max(0, Math.min(100, number * 100));
};

function MiniBar({ label, value, tone = "default" }: { label: string; value: number; tone?: "default" | "ok" | "warn" | "bad" }) {
  return (
    <div className="mini-bar-row">
      <div className="mini-bar-label">{label}</div>
      <div className="mini-bar-track">
        <div className={`mini-bar-fill ${tone}`} style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
      </div>
      <div className="mini-bar-value">{value.toFixed(1)}%</div>
    </div>
  );
}

function HealthBadge({ label, status }: { label: string; status?: string }) {
  const normalized = status === "ok" ? "ok" : status === "missing" || status === "bad" ? "bad" : "warn";
  const color = normalized === "ok" ? "green" : normalized === "bad" ? "red" : "gold";
  return (
    <Tag color={color} style={{ marginInlineEnd: 0 }}>
      {label}: {status || "unknown"}
    </Tag>
  );
}

export function DishaDashboard({
  rulesResult,
  backtestResult,
  regimeResult,
  signalsResult,
  paperResult,
  portfolioResult,
  readinessResult,
  dbReadinessResult,
  auditResult,
  operatorBoundaryResult,
  paperWorkflowResult,
  paperSessionHealthResult,
  paperMilestonesResult,
  paperDay1LaunchResult,
  scannerRemediationResult,
  scannerRerunRunbookResult,
  scannerReconciliationSuggestionResult,
  paperDayCloseoutResult,
  paperWorkflowGapSuggestionResult,
  db
}: DishaDashboardProps) {
  const [syncing, setSyncing] = useState(false);
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [syncPhrase, setSyncPhrase] = useState("");
  const [workflowSaving, setWorkflowSaving] = useState(false);
  const [workflowRows, setWorkflowRows] = useState<TableRow[]>((paperWorkflowResult.ok ? paperWorkflowResult.data.events || [] : []).map((row, index) => ({ key: index, ...row })));
  const [paperHealthState, setPaperHealthState] = useState<ApiResult<PaperSessionHealthPayload>>(paperSessionHealthResult);
  const [paperMilestonesState, setPaperMilestonesState] = useState<ApiResult<PaperMilestonesPayload>>(paperMilestonesResult);
  const [paperDayCloseoutState, setPaperDayCloseoutState] = useState<ApiResult<PaperDayCloseoutPayload>>(paperDayCloseoutResult);
  const [paperWorkflowGapState, setPaperWorkflowGapState] = useState<ApiResult<PaperWorkflowGapSuggestionPayload>>(paperWorkflowGapSuggestionResult);
  const [scannerSuggestionState, setScannerSuggestionState] = useState<ApiResult<ScannerReconciliationSuggestionPayload>>(scannerReconciliationSuggestionResult);
  const [filterLoading, setFilterLoading] = useState(false);
  const [derivedRefreshing, setDerivedRefreshing] = useState(false);
  const [lastScopedRefreshAt, setLastScopedRefreshAt] = useState<string | null>(null);
  const [dailyFilter, setDailyFilter] = useState({
    event_date: "",
    session: ""
  });
  const [workflowForm, setWorkflowForm] = useState({
    session: 1,
    event_date: new Date().toISOString().slice(0, 10),
    workflow_type: "session_checklist",
    status: "complete",
    symbol: "",
    notes: ""
  });
  const [syncStatus, setSyncStatus] = useState<ApiResult<SyncStatus>>(db.syncStatus);
  const [liveDbCounts, setLiveDbCounts] = useState({
    signals: db.signals.ok ? Number(db.signals.data.count || 0) : 0,
    positions: db.positions.ok ? Number(db.positions.data.count || 0) : 0,
    portfolio_snapshots: db.snapshots.ok ? Number(db.snapshots.data.count || 0) : 0,
    paper_events: db.events.ok ? Number(db.events.data.count || 0) : 0
  });
  const hasCriticalError = !rulesResult.ok || !backtestResult.ok || !regimeResult.ok;
  const rules = rulesResult.ok ? rulesResult.data : {};
  const backtest = backtestResult.ok ? backtestResult.data : {};
  const regime = regimeResult.ok ? regimeResult.data : {};
  const signals = signalsResult.ok ? signalsResult.data : { count: 0, signals: [] };
  const paper = paperResult.ok ? paperResult.data : {};
  const portfolio = portfolioResult.ok ? portfolioResult.data.summary || {} : {};
  const readiness = readinessResult.ok ? readinessResult.data : {};
  const dbReadiness = dbReadinessResult.ok ? dbReadinessResult.data : {};
  const operatorBoundary = operatorBoundaryResult.ok ? operatorBoundaryResult.data : {};
  const paperSessionHealth = paperHealthState.ok ? paperHealthState.data : {};
  const paperMilestones = paperMilestonesState.ok ? paperMilestonesState.data : {};
  const paperDay1Launch = paperDay1LaunchResult.ok ? paperDay1LaunchResult.data : {};
  const scannerRemediation = scannerRemediationResult.ok ? scannerRemediationResult.data : {};
  const scannerRerunRunbook = scannerRerunRunbookResult.ok ? scannerRerunRunbookResult.data : {};
  const scannerReconciliationSuggestion = scannerSuggestionState.ok ? scannerSuggestionState.data : {};
  const paperDayCloseout = paperDayCloseoutState.ok ? paperDayCloseoutState.data : {};
  const paperWorkflowGapSuggestion = paperWorkflowGapState.ok ? paperWorkflowGapState.data : {};
  const scannerSuggestionPayload = scannerReconciliationSuggestion.suggested_payload || {};
  const workflowGapPayload = paperWorkflowGapSuggestion.suggested_payload || {};
  const allocations = rules.portfolio?.allocations || {};
  const requiredSyncPhrase = operatorBoundary.confirmation_phrase || "SYNC DISHA";

  const signalRows: TableRow[] = (signals.signals || []).map((row, index) => ({ key: index, ...row }));
  const dbSignalRows: TableRow[] = (db.signals.ok ? db.signals.data.signals || [] : []).map((row, index) => ({ key: index, ...row }));
  const dbPositionRows: TableRow[] = (db.positions.ok ? db.positions.data.positions || [] : []).map((row, index) => ({ key: index, ...row }));
  const dbSnapshotRows: TableRow[] = (db.snapshots.ok ? db.snapshots.data.snapshots || [] : []).map((row, index) => ({ key: index, ...row }));
  const dbEventRows: TableRow[] = (db.events.ok ? db.events.data.events || [] : []).map((row, index) => ({ key: index, ...row }));
  const auditRows: TableRow[] = (auditResult.ok ? auditResult.data.events || [] : []).map((row, index) => ({ key: index, ...row }));
  const distributionRows = Object.entries(regime.distribution || {}).map(([label, item]) => ({
    key: label,
    regime: label,
    sessions: item.sessions,
    pct: percent(item.pct)
  }));
  const dbCounts = [
    { label: "Signals", value: liveDbCounts.signals },
    { label: "Positions", value: liveDbCounts.positions },
    { label: "Snapshots", value: liveDbCounts.portfolio_snapshots },
    { label: "Events", value: liveDbCounts.paper_events }
  ];
  const maxDbCount = Math.max(1, ...dbCounts.map((item) => item.value));
  const readinessItems = [
    { label: "Sessions", value: Number(paper.sessions_logged || 0), target: 30 },
    { label: "Scanner reconciliation", value: Number(paper.scanner_reconciliations || 0), target: 5 },
    { label: "MF sweep", value: Number(paper.mf_sweep_events || 0), target: 20 },
    { label: "Fill checks", value: Number(paper.fill_checks || 0), target: 30 }
  ];
  const activeReviewScope = dailyFilter.event_date || dailyFilter.session ? `${dailyFilter.event_date || "all dates"} / session ${dailyFilter.session || "all"}` : "All paper sessions";
  const nextOperatorAction = text(paperWorkflowGapSuggestion.review_action || paperDayCloseout.blockers?.[0] || scannerReconciliationSuggestion.review_action || "Review paper closeout evidence.");

  const runManualSync = async () => {
    setSyncing(true);
    try {
      const response = await fetch(`${API_BASE}/api/db/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation_phrase: syncPhrase })
      });
      if (!response.ok) throw new Error(`Sync failed: ${response.status}`);
      const payload = await response.json();
      const statusResponse = await fetch(`${API_BASE}/api/db/sync/status`);
      if (!statusResponse.ok) throw new Error(`Status refresh failed: ${statusResponse.status}`);
      const statusPayload = await statusResponse.json();
      setLiveDbCounts({
        signals: Number(payload.counts?.signals || 0),
        positions: Number(payload.counts?.positions || 0),
        portfolio_snapshots: Number(payload.counts?.portfolio_snapshots || 0),
        paper_events: Number(payload.counts?.paper_events || 0)
      });
      setSyncStatus({ ok: true, data: statusPayload });
      setSyncModalOpen(false);
      setSyncPhrase("");
      message.success("Disha artifacts synced");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Disha sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const filterQuery = () => {
    const params = new URLSearchParams({ limit: "500" });
    if (dailyFilter.event_date) params.set("event_date", dailyFilter.event_date);
    if (dailyFilter.session) params.set("session", dailyFilter.session);
    return params.toString();
  };

  const refreshPaperDerivedState = async () => {
    setDerivedRefreshing(true);
    try {
      const query = filterQuery();
      const [healthResponse, milestonesResponse, closeoutResponse, gapResponse, scannerSuggestionResponse] = await Promise.all([
        fetch(`${API_BASE}/api/db/paper/session-health?${query}`),
        fetch(`${API_BASE}/api/db/paper/milestones?limit=5000`),
        fetch(`${API_BASE}/api/db/paper/day-closeout?${query}`),
        fetch(`${API_BASE}/api/db/paper/workflow-gap-suggestion?${query}`),
        fetch(`${API_BASE}/api/db/scanner/reconciliation-suggestion`)
      ]);
      if (!healthResponse.ok) throw new Error(`Health refresh failed: ${healthResponse.status}`);
      if (!milestonesResponse.ok) throw new Error(`Milestone refresh failed: ${milestonesResponse.status}`);
      if (!closeoutResponse.ok) throw new Error(`Closeout refresh failed: ${closeoutResponse.status}`);
      if (!gapResponse.ok) throw new Error(`Workflow gap refresh failed: ${gapResponse.status}`);
      if (!scannerSuggestionResponse.ok) throw new Error(`Scanner suggestion refresh failed: ${scannerSuggestionResponse.status}`);
      const [healthPayload, milestonesPayload, closeoutPayload, gapPayload, scannerSuggestionPayload] = await Promise.all([
        healthResponse.json(),
        milestonesResponse.json(),
        closeoutResponse.json(),
        gapResponse.json(),
        scannerSuggestionResponse.json()
      ]);
      setPaperHealthState({ ok: true, data: healthPayload });
      setPaperMilestonesState({ ok: true, data: milestonesPayload });
      setPaperDayCloseoutState({ ok: true, data: closeoutPayload });
      setPaperWorkflowGapState({ ok: true, data: gapPayload });
      setScannerSuggestionState({ ok: true, data: scannerSuggestionPayload });
      setLastScopedRefreshAt(new Date().toLocaleTimeString("en-IN", { hour12: false }));
    } finally {
      setDerivedRefreshing(false);
    }
  };

  const appendWorkflowEvent = async () => {
    setWorkflowSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/db/paper/workflow-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session: workflowForm.session,
          event_date: workflowForm.event_date,
          workflow_type: workflowForm.workflow_type,
          status: workflowForm.status,
          symbol: workflowForm.symbol || null,
          notes: workflowForm.notes
        })
      });
      if (!response.ok) throw new Error(`Workflow save failed: ${response.status}`);
      const payload = await response.json();
      setWorkflowRows((rows) => [{ key: payload.event.workflow_event_id, ...payload.event }, ...rows]);
      setWorkflowForm((current) => ({ ...current, symbol: "", notes: "" }));
      await refreshPaperDerivedState();
      message.success("Paper workflow note appended");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Workflow save failed");
    } finally {
      setWorkflowSaving(false);
    }
  };

  const applyScannerSuggestion = () => {
    setWorkflowForm((current) => ({
      ...current,
      session: Number(scannerSuggestionPayload.session || current.session),
      event_date: text(scannerSuggestionPayload.event_date || current.event_date),
      workflow_type: text(scannerSuggestionPayload.workflow_type || "scanner_reconciliation"),
      status: text(scannerSuggestionPayload.status || "pending"),
      symbol: text(scannerSuggestionPayload.symbol || ""),
      notes: text(scannerSuggestionPayload.notes || "")
    }));
    message.info("Scanner suggestion copied into workflow form for review");
  };

  const applyWorkflowGapSuggestion = () => {
    setWorkflowForm((current) => ({
      ...current,
      session: Number(workflowGapPayload.session || current.session),
      event_date: text(workflowGapPayload.event_date || current.event_date),
      workflow_type: text(workflowGapPayload.workflow_type || current.workflow_type),
      status: text(workflowGapPayload.status || "pending"),
      symbol: text(workflowGapPayload.symbol || ""),
      notes: text(workflowGapPayload.notes || "")
    }));
    message.info("Workflow gap suggestion copied into workflow form for review");
  };

  const applyDailyFilter = async () => {
    setFilterLoading(true);
    try {
      const query = filterQuery();
      const [workflowResponse, healthResponse, closeoutResponse, gapResponse] = await Promise.all([
        fetch(`${API_BASE}/api/db/paper/workflow-events?${query}`),
        fetch(`${API_BASE}/api/db/paper/session-health?${query}`),
        fetch(`${API_BASE}/api/db/paper/day-closeout?${query}`),
        fetch(`${API_BASE}/api/db/paper/workflow-gap-suggestion?${query}`)
      ]);
      if (!workflowResponse.ok) throw new Error(`Workflow filter failed: ${workflowResponse.status}`);
      if (!healthResponse.ok) throw new Error(`Health filter failed: ${healthResponse.status}`);
      if (!closeoutResponse.ok) throw new Error(`Closeout filter failed: ${closeoutResponse.status}`);
      if (!gapResponse.ok) throw new Error(`Workflow gap filter failed: ${gapResponse.status}`);
      const workflowPayload = await workflowResponse.json();
      const healthPayload = await healthResponse.json();
      const closeoutPayload = await closeoutResponse.json();
      const gapPayload = await gapResponse.json();
      setWorkflowRows((workflowPayload.events || []).map((row: Record<string, unknown>, index: number) => ({ key: String(row.workflow_event_id || index), ...row })));
      setPaperHealthState({ ok: true, data: healthPayload });
      setPaperDayCloseoutState({ ok: true, data: closeoutPayload });
      setPaperWorkflowGapState({ ok: true, data: gapPayload });
      setLastScopedRefreshAt(new Date().toLocaleTimeString("en-IN", { hour12: false }));
      message.success("Paper session filter applied");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Paper session filter failed");
    } finally {
      setFilterLoading(false);
    }
  };

  const scopedExportQuery = filterQuery();

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div className="topbar">
        <div>
          <h1 className="title">Disha</h1>
          <p className="subtitle">Read-only operating dashboard for the locked three-sleeve setup.</p>
        </div>
        <Badge status={paper.ready ? "success" : "warning"} text={paper.ready ? "Paper ready" : "Paper pending"} />
      </div>

      {hasCriticalError ? (
        <Alert
          type="warning"
          showIcon
          message="Some Disha API artifacts are not available"
          description={[rulesResult, backtestResult, regimeResult].filter((item) => !item.ok).map((item) => (item.ok ? "" : item.error)).join(" | ")}
        />
      ) : null}

      <Alert
        type={operatorBoundary.live_trading_enabled || operatorBoundary.orders_enabled ? "error" : "info"}
        showIcon
        message={operatorBoundary.live_trading_enabled || operatorBoundary.orders_enabled ? "Live trading controls enabled" : "Live trading disabled"}
        description={`Environment: ${text(operatorBoundary.environment)}. This dashboard is read-only by default; the only allowlisted mutation is local artifact sync and it has no trading effect.`}
      />

      <Card title="Paper Operations Status" size="small">
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Statistic
              title="Closeout"
              value={text(paperDayCloseout.verdict)}
              valueStyle={{ color: paperDayCloseout.verdict === "CLOSED" ? "#16713f" : paperDayCloseout.verdict === "NO_GO" ? "#b42318" : "#b45309" }}
            />
          </Col>
          <Col xs={24} md={6}>
            <Typography.Text type="secondary">Active Scope</Typography.Text>
            <Typography.Paragraph style={{ marginBottom: 0 }}>{activeReviewScope}</Typography.Paragraph>
          </Col>
          <Col xs={24} md={6}>
            <Typography.Text type="secondary">Last Scoped Refresh</Typography.Text>
            <Typography.Paragraph style={{ marginBottom: 0 }}>{derivedRefreshing ? "Refreshing" : lastScopedRefreshAt || "Initial load"}</Typography.Paragraph>
          </Col>
          <Col xs={24} md={6}>
            <Typography.Text type="secondary">Next Workflow</Typography.Text>
            <Typography.Paragraph style={{ marginBottom: 0 }}>{text(workflowGapPayload.workflow_type || "n/a")}</Typography.Paragraph>
          </Col>
        </Row>
        <Alert
          style={{ marginTop: 12 }}
          type={paperDayCloseout.verdict === "CLOSED" ? "success" : paperDayCloseout.verdict === "NO_GO" ? "error" : "warning"}
          showIcon
          message={nextOperatorAction}
          description="Compact paper-day command center. Use the workflow assistants below to prefill notes, then review before appending."
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} xl={6}>
          <Card size="small"><Statistic title="Production CAGR" value={text(backtest.portfolio?.cagr)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card size="small"><Statistic title="Max DD" value={text(backtest.portfolio?.max_dd)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card size="small"><Statistic title="Sharpe" value={text(backtest.portfolio?.sharpe)} /></Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card size="small"><Statistic title="Signals Today" value={signals.count || 0} /></Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card title="Locked Architecture" size="small">
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Portfolio">{text(rules.portfolio?.name)}</Descriptions.Item>
              <Descriptions.Item label="Status">{text(rules.portfolio?.status)}</Descriptions.Item>
              <Descriptions.Item label="Initial capital">{money(rules.portfolio?.initial_capital)}</Descriptions.Item>
              <Descriptions.Item label="V4b allocation">{percent(allocations.v4b_mean_reversion)}</Descriptions.Item>
              <Descriptions.Item label="VCP allocation">{percent(allocations.vcp_breakout)}</Descriptions.Item>
              <Descriptions.Item label="Idle yield">{text(rules.idle_yield_proxy?.net_post_tax_yield)}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="Latest Market Regime" size="small">
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              <Tag color={text(regime.latest?.regime_label) === "UPTREND" ? "green" : text(regime.latest?.regime_label) === "DOWNTREND" ? "red" : "gold"}>
                {text(regime.latest?.regime_label)}
              </Tag>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Session">{text(regime.latest?.session_date)}</Descriptions.Item>
                <Descriptions.Item label="Nifty close">{text(regime.latest?.nifty_close)}</Descriptions.Item>
                <Descriptions.Item label="Trend strength">{text(regime.latest?.adx)}</Descriptions.Item>
                <Descriptions.Item label="Total sessions">{text(regime.total_sessions)}</Descriptions.Item>
              </Descriptions>
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card title="Scanner Output" size="small">
            {signalRows.length ? (
              <Table
                size="small"
                pagination={false}
                dataSource={signalRows}
                columns={[
                  { title: "Date", dataIndex: "scan_date" },
                  { title: "Symbol", dataIndex: "symbol" },
                  { title: "V4b", dataIndex: "v4b_entry_signal", render: (value) => (value ? <Tag color="blue">YES</Tag> : "-") },
                  { title: "VCP", dataIndex: "vcp_entry_signal", render: (value) => (value ? <Tag color="green">YES</Tag> : "-") },
                  { title: "Regime", dataIndex: "market_regime" },
                  { title: "Close", dataIndex: "close" }
                ]}
              />
            ) : (
              <Empty description="No actionable signals in the latest scanner artifact." />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="Regime Distribution" size="small">
            <Table
              size="small"
              pagination={false}
              dataSource={distributionRows}
              columns={[
                { title: "Regime", dataIndex: "regime" },
                { title: "Sessions", dataIndex: "sessions" },
                { title: "Pct", dataIndex: "pct" }
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Paper Trading Readiness" size="small">
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Sessions logged">{text(paper.sessions_logged)}</Descriptions.Item>
              <Descriptions.Item label="Scanner reconciliations">{text(paper.scanner_reconciliations)}</Descriptions.Item>
              <Descriptions.Item label="MF sweep events">{text(paper.mf_sweep_events)}</Descriptions.Item>
              <Descriptions.Item label="Fill checks">{text(paper.fill_checks)}</Descriptions.Item>
              <Descriptions.Item label="Open positions logged">{text(paper.open_positions_logged)}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="DB Sync State" size="small">
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Signals">{db.signals.ok ? text(liveDbCounts.signals) : db.signals.error}</Descriptions.Item>
              <Descriptions.Item label="Positions">{db.positions.ok ? text(liveDbCounts.positions) : db.positions.error}</Descriptions.Item>
              <Descriptions.Item label="Snapshots">{db.snapshots.ok ? text(liveDbCounts.portfolio_snapshots) : db.snapshots.error}</Descriptions.Item>
              <Descriptions.Item label="Paper events">{db.events.ok ? text(liveDbCounts.paper_events) : db.events.error}</Descriptions.Item>
              <Descriptions.Item label="Open notional">{money(portfolio.open_notional)}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <Card title="Environment Readiness" size="small">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Space wrap>
            <HealthBadge label="Artifacts" status={readinessResult.ok ? readiness.status : "degraded"} />
            <HealthBadge label="Paper" status={readiness.paper?.ready ? "ok" : "degraded"} />
            <HealthBadge label="DB" status={dbReadinessResult.ok ? dbReadiness.status : "degraded"} />
            <HealthBadge label="Migration" status={dbReadiness.migration?.status} />
          </Space>
          <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
            <Descriptions.Item label="Alembic current">{dbReadinessResult.ok ? text(dbReadiness.migration?.current) : dbReadinessResult.error}</Descriptions.Item>
            <Descriptions.Item label="Alembic expected">{text(dbReadiness.migration?.expected)}</Descriptions.Item>
            <Descriptions.Item label="Scanner rows">{text(readiness.scanner?.latest_rows)}</Descriptions.Item>
            <Descriptions.Item label="Artifact files">
              {readinessResult.ok ? `${Object.values(readiness.artifact_checks || {}).filter((item) => item.exists).length}/${Object.keys(readiness.artifact_checks || {}).length}` : readinessResult.error}
            </Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card title="Operator Boundary" size="small">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Space wrap>
            <HealthBadge label="Live trading" status={operatorBoundary.live_trading_enabled ? "bad" : "ok"} />
            <HealthBadge label="Orders" status={operatorBoundary.orders_enabled ? "bad" : "ok"} />
            <HealthBadge label="Default mode" status={operatorBoundary.read_only_default ? "ok" : "degraded"} />
          </Space>
          <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
            <Descriptions.Item label="Environment">{text(operatorBoundary.environment)}</Descriptions.Item>
            <Descriptions.Item label="Allowlisted mutations">{text(operatorBoundary.mutation_allowlist?.length || 0)}</Descriptions.Item>
            <Descriptions.Item label="Sync confirmation phrase">{requiredSyncPhrase}</Descriptions.Item>
            <Descriptions.Item label="Disabled actions">{text((operatorBoundary.disabled_actions || []).join(", "))}</Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card
        title="Operator Sync"
        size="small"
        extra={
          <Button icon={<ReloadOutlined />} loading={syncing} onClick={() => setSyncModalOpen(true)}>
            Sync Artifacts
          </Button>
        }
      >
        <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
          <Descriptions.Item label="Last sync">{syncStatus.ok ? text(syncStatus.data.latest_sync_at) : syncStatus.error}</Descriptions.Item>
          <Descriptions.Item label="Action scope">Scanner, paper logs, positions, snapshots</Descriptions.Item>
          <Descriptions.Item label="Signals">{liveDbCounts.signals}</Descriptions.Item>
          <Descriptions.Item label="Positions">{liveDbCounts.positions}</Descriptions.Item>
          <Descriptions.Item label="Snapshots">{liveDbCounts.portfolio_snapshots}</Descriptions.Item>
          <Descriptions.Item label="Paper events">{liveDbCounts.paper_events}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Modal
        title="Confirm artifact sync"
        open={syncModalOpen}
        okText="Sync artifacts"
        cancelText="Cancel"
        confirmLoading={syncing}
        okButtonProps={{ disabled: syncPhrase !== requiredSyncPhrase }}
        onCancel={() => {
          setSyncModalOpen(false);
          setSyncPhrase("");
        }}
        onOk={runManualSync}
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message="Sync-only action"
            description="This updates local Disha app tables from scanner and paper-trading artifacts. It does not place orders, redeem funds, or change the approved setup."
          />
          <Typography.Text>Type {requiredSyncPhrase} to continue.</Typography.Text>
          <Input value={syncPhrase} onChange={(event) => setSyncPhrase(event.target.value)} placeholder={requiredSyncPhrase} autoFocus />
        </Space>
      </Modal>

      <Card title="Paper Day Workflow Capture" size="small">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message="Paper workflow only"
            description="These notes are append-only operating records for scanner reconciliation, MF sweep checks, and fill-quality tracking. They do not place orders or alter artifacts."
          />
          <Row gutter={[12, 12]}>
            <Col xs={24} md={4}>
              <Typography.Text type="secondary">Session</Typography.Text>
              <InputNumber min={0} value={workflowForm.session} onChange={(value) => setWorkflowForm((current) => ({ ...current, session: Number(value || 0) }))} style={{ width: "100%" }} />
            </Col>
            <Col xs={24} md={5}>
              <Typography.Text type="secondary">Date</Typography.Text>
              <Input value={workflowForm.event_date} onChange={(event) => setWorkflowForm((current) => ({ ...current, event_date: event.target.value }))} />
            </Col>
            <Col xs={24} md={6}>
              <Typography.Text type="secondary">Workflow</Typography.Text>
              <Select
                value={workflowForm.workflow_type}
                onChange={(value) => setWorkflowForm((current) => ({ ...current, workflow_type: value }))}
                style={{ width: "100%" }}
                options={[
                  { value: "session_checklist", label: "Session checklist" },
                  { value: "scanner_reconciliation", label: "Scanner reconciliation" },
                  { value: "mf_sweep", label: "MF sweep" },
                  { value: "fill_quality", label: "09:15 fill quality" }
                ]}
              />
            </Col>
            <Col xs={24} md={5}>
              <Typography.Text type="secondary">Status</Typography.Text>
              <Select
                value={workflowForm.status}
                onChange={(value) => setWorkflowForm((current) => ({ ...current, status: value }))}
                style={{ width: "100%" }}
                options={[
                  { value: "complete", label: "Complete" },
                  { value: "pending", label: "Pending" },
                  { value: "blocked", label: "Blocked" },
                  { value: "mismatch", label: "Mismatch" },
                  { value: "not_applicable", label: "Not applicable" }
                ]}
              />
            </Col>
            <Col xs={24} md={4}>
              <Typography.Text type="secondary">Symbol</Typography.Text>
              <Input value={workflowForm.symbol} onChange={(event) => setWorkflowForm((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))} placeholder="Optional" />
            </Col>
            <Col xs={24}>
              <Typography.Text type="secondary">Notes</Typography.Text>
              <Input.TextArea rows={3} value={workflowForm.notes} onChange={(event) => setWorkflowForm((current) => ({ ...current, notes: event.target.value }))} />
            </Col>
            <Col xs={24}>
              <Button type="primary" loading={workflowSaving || derivedRefreshing} disabled={!workflowForm.notes.trim()} onClick={appendWorkflowEvent}>
                Append Workflow Note
              </Button>
            </Col>
          </Row>
          <Table
            size="small"
            pagination={{ pageSize: 5 }}
            dataSource={workflowRows}
            columns={[
              { title: "Time", dataIndex: "event_time" },
              { title: "Session", dataIndex: "session" },
              { title: "Type", dataIndex: "workflow_type" },
              { title: "Status", dataIndex: "status", render: (value) => <Tag color={value === "blocked" || value === "mismatch" ? "gold" : "blue"}>{text(value)}</Tag> },
              { title: "Symbol", dataIndex: "symbol" },
              { title: "Notes", dataIndex: "notes" }
            ]}
            locale={{ emptyText: <Empty description={paperWorkflowResult.ok ? "No workflow notes yet." : paperWorkflowResult.error} /> }}
          />
        </Space>
      </Card>

      <Card title="Day 1 Launch Checklist" size="small">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}>
              <Statistic
                title="Launch Verdict"
                value={text(paperDay1Launch.verdict)}
                valueStyle={{ color: paperDay1Launch.verdict === "READY" ? "#16713f" : paperDay1Launch.verdict === "NO_GO" ? "#b42318" : "#b45309" }}
              />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Ready" value={Number(paperDay1Launch.ready_count || 0)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Review" value={Number(paperDay1Launch.review_count || 0)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Blocked" value={Number(paperDay1Launch.blocked_count || 0)} />
            </Col>
          </Row>
          <Alert
            type="info"
            showIcon
            message="Guided paper launch only"
            description="This checklist coordinates scanner, workflow notes, session health, exports, and milestone tracking. It does not place trades, redeem funds, or change the approved setup."
          />
          <Table
            size="small"
            pagination={false}
            dataSource={(paperDay1Launch.steps || []).map((row, index) => ({ key: index, ...row }))}
            columns={[
              { title: "Step", dataIndex: "label" },
              { title: "Status", dataIndex: "status", render: (value) => <Tag color={value === "ready" ? "green" : value === "blocked" ? "red" : "gold"}>{text(value)}</Tag> },
              { title: "Evidence", dataIndex: "evidence" }
            ]}
            locale={{ emptyText: <Empty description={paperDay1LaunchResult.ok ? "No launch checklist evidence yet." : paperDay1LaunchResult.error} /> }}
          />
          <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
            <Descriptions.Item label="Operator flow">{(paperDay1Launch.operator_flow || []).join(" | ") || "n/a"}</Descriptions.Item>
            <Descriptions.Item label="Guardrails">{(paperDay1Launch.guardrails || []).join(" | ") || "n/a"}</Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card
        title="Scanner Readiness Remediation"
        size="small"
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => setSyncModalOpen(true)}>
            Open Guarded Sync
          </Button>
        }
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}>
              <Statistic
                title="Scanner Status"
                value={text(scannerRemediation.status)}
                valueStyle={{ color: scannerRemediation.status === "READY" ? "#16713f" : scannerRemediation.status === "NO_GO" ? "#b42318" : "#b45309" }}
              />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Artifact Rows" value={Number(scannerRemediation.artifact?.signal_rows || 0)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="DB Signal Rows" value={Number(scannerRemediation.database?.synced_signal_rows || 0)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Primary Gap" value={text(scannerRemediation.primary_gap)} />
            </Col>
          </Row>
          <Alert
            type={scannerRemediation.status === "READY" ? "success" : scannerRemediation.status === "NO_GO" ? "error" : "warning"}
            showIcon
            message={text(scannerRemediation.next_action)}
            description="Use this panel to resolve scanner readiness only. Guarded sync updates local app tables from artifacts; it does not place orders or change the approved setup."
          />
          <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
            <Descriptions.Item label="Signals file">{text(scannerRemediation.artifact?.signals_file)}</Descriptions.Item>
            <Descriptions.Item label="Artifact modified">{text(scannerRemediation.artifact?.modified_at)}</Descriptions.Item>
            <Descriptions.Item label="Latest sync">{text(scannerRemediation.database?.latest_sync_at)}</Descriptions.Item>
            <Descriptions.Item label="Disabled actions">{(scannerRemediation.disabled_actions || []).join(", ") || "n/a"}</Descriptions.Item>
            <Descriptions.Item label="Safe actions">{(scannerRemediation.safe_actions || []).join(" | ") || "n/a"}</Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card title="Scanner Rerun Runbook" size="small">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}>
              <Statistic
                title="Runbook Status"
                value={text(scannerRerunRunbook.status)}
                valueStyle={{ color: scannerRerunRunbook.status === "READY" ? "#16713f" : "#b45309" }}
              />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Runbook File" value={scannerRerunRunbook.runbook_exists ? "Present" : "Missing"} />
            </Col>
            <Col xs={24} md={12}>
              <Typography.Text type="secondary">Working directory</Typography.Text>
              <Typography.Paragraph copyable style={{ marginBottom: 0 }}>
                {text(scannerRerunRunbook.working_directory)}
              </Typography.Paragraph>
            </Col>
          </Row>
          <Alert
            type="info"
            showIcon
            message="Existing scanner command"
            description="Run this outside the dashboard when scanner artifacts need regeneration. This panel is read-only and does not execute the scanner."
          />
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Primary command">
              <Typography.Text code copyable>
                {text(scannerRerunRunbook.primary_command)}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Research override">
              <Typography.Text code copyable>
                {text(scannerRerunRunbook.research_override_command)}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Expected outputs">{(scannerRerunRunbook.expected_outputs || []).join(" | ") || "n/a"}</Descriptions.Item>
            <Descriptions.Item label="Post-run checks">{(scannerRerunRunbook.post_run_checks || []).join(" | ") || "n/a"}</Descriptions.Item>
            <Descriptions.Item label="Workflow capture">
              {`type=${text(scannerRerunRunbook.workflow_capture?.workflow_type)}, zero-signal=${text(scannerRerunRunbook.workflow_capture?.zero_signal_status)}, blocked=${text(scannerRerunRunbook.workflow_capture?.blocked_status)}`}
            </Descriptions.Item>
            <Descriptions.Item label="Guardrails">{(scannerRerunRunbook.guardrails || []).join(" | ") || "n/a"}</Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card
        title="Scanner Reconciliation Assistant"
        size="small"
        extra={
          <Button onClick={applyScannerSuggestion} disabled={!scannerSuggestionState.ok || !scannerSuggestionPayload.notes}>
            Prefill Workflow Note
          </Button>
        }
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message={text(scannerReconciliationSuggestion.review_action)}
            description="This assistant only prepares a suggested workflow note. Review it in Paper Day Workflow Capture before appending."
          />
          <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
            <Descriptions.Item label="Workflow">{text(scannerSuggestionPayload.workflow_type)}</Descriptions.Item>
            <Descriptions.Item label="Suggested status">{text(scannerSuggestionPayload.status)}</Descriptions.Item>
            <Descriptions.Item label="Session">{text(scannerSuggestionPayload.session)}</Descriptions.Item>
            <Descriptions.Item label="Event date">{text(scannerSuggestionPayload.event_date)}</Descriptions.Item>
            <Descriptions.Item label="Suggested notes">{text(scannerSuggestionPayload.notes)}</Descriptions.Item>
            <Descriptions.Item label="Guardrails">{(scannerReconciliationSuggestion.guardrails || []).join(" | ") || "n/a"}</Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card title="Daily Review Controls" size="small">
        <Row gutter={[12, 12]} align="bottom">
          <Col xs={24} md={6}>
            <Typography.Text type="secondary">Review date</Typography.Text>
            <Input value={dailyFilter.event_date} onChange={(event) => setDailyFilter((current) => ({ ...current, event_date: event.target.value }))} placeholder="YYYY-MM-DD" />
          </Col>
          <Col xs={24} md={6}>
            <Typography.Text type="secondary">Session</Typography.Text>
            <InputNumber min={0} value={dailyFilter.session ? Number(dailyFilter.session) : null} onChange={(value) => setDailyFilter((current) => ({ ...current, session: value === null ? "" : String(value) }))} style={{ width: "100%" }} />
          </Col>
          <Col xs={24} md={12}>
            <Space wrap>
              <Button loading={filterLoading || derivedRefreshing} onClick={applyDailyFilter}>Apply Filter</Button>
              <Button onClick={() => setDailyFilter({ event_date: "", session: "" })}>Clear</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card title="Paper Day Closeout" size="small">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}>
              <Statistic
                title="Closeout Verdict"
                value={text(paperDayCloseout.verdict)}
                valueStyle={{ color: paperDayCloseout.verdict === "CLOSED" ? "#16713f" : paperDayCloseout.verdict === "NO_GO" ? "#b42318" : "#b45309" }}
              />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Session Health" value={text(paperDayCloseout.session_health?.verdict)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Scanner Note" value={text(paperDayCloseout.scanner_suggestion?.suggested_payload?.status)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Blockers" value={(paperDayCloseout.blockers || []).length} />
            </Col>
          </Row>
          <Alert
            type={paperDayCloseout.verdict === "CLOSED" ? "success" : paperDayCloseout.verdict === "NO_GO" ? "error" : "warning"}
            showIcon
            message={derivedRefreshing ? "Refreshing closeout evidence..." : (paperDayCloseout.blockers || []).length ? (paperDayCloseout.blockers || []).join(" ") : "Closeout evidence is ready for operator review."}
            description="This closeout view combines paper evidence only. It does not execute scanner, order, or MF actions."
          />
          <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
            <Descriptions.Item label="Milestone verdict">{text(paperDayCloseout.milestones?.verdict)}</Descriptions.Item>
            <Descriptions.Item label="Review counts">
              {`workflow=${text(paperDayCloseout.review_counts?.workflow_count)}, paper=${text(paperDayCloseout.review_counts?.paper_event_count)}, audit=${text(paperDayCloseout.review_counts?.audit_event_count)}`}
            </Descriptions.Item>
            <Descriptions.Item label="Closeout steps">{(paperDayCloseout.operator_closeout_steps || []).join(" | ") || "n/a"}</Descriptions.Item>
            <Descriptions.Item label="Guardrails">{(paperDayCloseout.guardrails || []).join(" | ") || "n/a"}</Descriptions.Item>
          </Descriptions>
          <Space wrap>
            <Button icon={<DownloadOutlined />} href={`${API_BASE}${paperDayCloseout.export_links?.workflow_csv || `/api/db/paper/workflow-events/export.csv?${scopedExportQuery}`}`}>
              Closeout Workflow CSV
            </Button>
            <Button icon={<DownloadOutlined />} href={`${API_BASE}${paperDayCloseout.export_links?.audit_csv || "/api/db/audit/trail/export.csv?limit=500"}`}>
              Closeout Audit CSV
            </Button>
            <Button icon={<DownloadOutlined />} href={`${API_BASE}${paperDayCloseout.export_links?.review_packet_md || `/api/db/paper/review-packet.md?${scopedExportQuery}`}`}>
              Closeout Review Packet
            </Button>
          </Space>
        </Space>
      </Card>

      <Card
        title="Paper Workflow Gap Assistant"
        size="small"
        extra={
          <Button onClick={applyWorkflowGapSuggestion} disabled={!paperWorkflowGapState.ok || !workflowGapPayload.notes}>
            Prefill Missing Workflow
          </Button>
        }
      >
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Alert
            type={paperWorkflowGapSuggestion.status === "complete" ? "success" : "warning"}
            showIcon
            message={text(paperWorkflowGapSuggestion.review_action)}
            description="This assistant suggests one missing closeout workflow note at a time. Review the note in Paper Day Workflow Capture before appending."
          />
          <Row gutter={[16, 16]}>
            <Col xs={24} md={6}>
              <Statistic title="Gap Status" value={text(paperWorkflowGapSuggestion.status)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Missing" value={(paperWorkflowGapSuggestion.missing_workflows || []).length} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Next Workflow" value={text(workflowGapPayload.workflow_type)} />
            </Col>
            <Col xs={24} md={6}>
              <Statistic title="Suggested Status" value={text(workflowGapPayload.status)} />
            </Col>
          </Row>
          <Descriptions column={{ xs: 1, md: 2 }} size="small" bordered>
            <Descriptions.Item label="Missing workflows">{(paperWorkflowGapSuggestion.missing_workflows || []).join(", ") || "none"}</Descriptions.Item>
            <Descriptions.Item label="Suggested notes">{text(workflowGapPayload.notes)}</Descriptions.Item>
            <Descriptions.Item label="Guardrails">{(paperWorkflowGapSuggestion.guardrails || []).join(" | ") || "n/a"}</Descriptions.Item>
          </Descriptions>
        </Space>
      </Card>

      <Card title="Paper Session Health" size="small">
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Statistic
              title="Readiness Verdict"
              value={text(paperSessionHealth.verdict)}
              valueStyle={{ color: paperSessionHealth.verdict === "GO" ? "#16713f" : paperSessionHealth.verdict === "NO_GO" ? "#b42318" : "#b45309" }}
            />
          </Col>
          <Col xs={24} md={6}>
            <Statistic title="Completion" value={Number(paperSessionHealth.completion_pct || 0)} suffix="%" />
          </Col>
          <Col xs={24} md={6}>
            <Statistic title="Missing Checks" value={(paperSessionHealth.missing_workflows || []).length} />
          </Col>
          <Col xs={24} md={6}>
            <Statistic title="Blocked/Mismatch" value={(paperSessionHealth.unresolved_items || []).length} />
          </Col>
        </Row>
        <Table
          size="small"
          pagination={false}
          style={{ marginTop: 16 }}
          dataSource={(paperSessionHealth.checks || []).map((row, index) => ({ key: index, ...row }))}
          columns={[
            { title: "Workflow", dataIndex: "workflow_type" },
            { title: "Status", dataIndex: "status", render: (value) => <Tag color={value === "complete" || value === "not_applicable" ? "green" : value === "missing" ? "gold" : "red"}>{text(value)}</Tag> },
            { title: "Latest note", dataIndex: "notes" }
          ]}
          locale={{ emptyText: <Empty description={paperHealthState.ok ? "No session health checks yet." : paperHealthState.error} /> }}
        />
      </Card>

      <Card title="Paper Milestone Tracker" size="small">
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Statistic
              title="Final Readiness"
              value={text(paperMilestones.verdict)}
              valueStyle={{ color: paperMilestones.verdict === "GO" ? "#16713f" : paperMilestones.verdict === "NO_GO" ? "#b42318" : "#b45309" }}
            />
          </Col>
          <Col xs={24} md={6}>
            <Statistic title="Sessions Logged" value={Number(paperMilestones.sessions_logged || 0)} suffix="/ 30" />
          </Col>
          <Col xs={24} md={6}>
            <Statistic title="Latest Session" value={text(paperMilestones.latest_session)} />
          </Col>
          <Col xs={24} md={6}>
            <Statistic title="Unresolved" value={(paperMilestones.unresolved_items || []).length} />
          </Col>
        </Row>
        <Table
          size="small"
          pagination={false}
          style={{ marginTop: 16 }}
          dataSource={(paperMilestones.milestones || []).map((row, index) => ({ key: index, ...row }))}
          columns={[
            { title: "Milestone", dataIndex: "milestone" },
            { title: "Sessions", dataIndex: "session_range" },
            { title: "Progress", dataIndex: "completion_pct", render: (value) => <Progress percent={Number(value || 0)} size="small" /> },
            { title: "Done", dataIndex: "completed_sessions", render: (value, row: TableRow) => `${text(value)} / ${text(row.target)}` },
            { title: "Status", dataIndex: "status", render: (value) => <Tag color={value === "complete" ? "green" : value === "not_started" ? "gold" : "blue"}>{text(value)}</Tag> }
          ]}
          locale={{ emptyText: <Empty description={paperMilestonesState.ok ? "No milestone evidence yet." : paperMilestonesState.error} /> }}
        />
      </Card>

      <Card title="Paper Review Exports" size="small">
        <Space wrap>
          <Button icon={<DownloadOutlined />} href={`${API_BASE}/api/db/paper/workflow-events/export.csv?${scopedExportQuery}`}>
            Workflow CSV
          </Button>
          <Button icon={<DownloadOutlined />} href={`${API_BASE}/api/db/audit/trail/export.csv?limit=500`}>
            Audit CSV
          </Button>
          <Button icon={<DownloadOutlined />} href={`${API_BASE}/api/db/paper/review-packet.md?${scopedExportQuery}`}>
            Review Packet
          </Button>
        </Space>
      </Card>

      <Card title="Drilldowns" size="small">
        <Tabs
          items={[
            {
              key: "signals",
              label: "Signals",
              children: (
                <Table
                  size="small"
                  pagination={{ pageSize: 8 }}
                  dataSource={dbSignalRows.length ? dbSignalRows : signalRows}
                  columns={[
                    { title: "Date", dataIndex: "scan_date" },
                    { title: "Symbol", dataIndex: "symbol" },
                    { title: "Sleeve", dataIndex: "sleeve", render: (value, row) => text(value || (row.v4b_entry_signal ? "V4B" : row.vcp_entry_signal ? "VCP" : "")) },
                    { title: "Signal", dataIndex: "signal_type" },
                    { title: "Regime", dataIndex: "market_regime" },
                    { title: "Close", dataIndex: "close_price", render: (value, row) => text(value || row.close) }
                  ]}
                  locale={{ emptyText: <Empty description="No synced or scanner signal rows yet." /> }}
                />
              )
            },
            {
              key: "events",
              label: "Paper Events",
              children: (
                <Table
                  size="small"
                  pagination={{ pageSize: 8 }}
                  dataSource={dbEventRows}
                  columns={[
                    { title: "Date", dataIndex: "event_date" },
                    { title: "Session", dataIndex: "session" },
                    { title: "Type", dataIndex: "event_type" },
                    { title: "Symbol", dataIndex: "symbol" },
                    { title: "Action", dataIndex: "action" },
                    { title: "Status", dataIndex: "status" }
                  ]}
                  locale={{ emptyText: <Empty description="No DB paper events yet. Run /api/db/sync after migration 015 is applied." /> }}
                />
              )
            },
            {
              key: "positions",
              label: "Positions",
              children: (
                <Table
                  size="small"
                  pagination={{ pageSize: 8 }}
                  dataSource={dbPositionRows}
                  columns={[
                    { title: "Symbol", dataIndex: "symbol" },
                    { title: "Sleeve", dataIndex: "sleeve" },
                    { title: "Entry", dataIndex: "entry_date" },
                    { title: "Shares", dataIndex: "shares" },
                    { title: "Entry Price", dataIndex: "entry_price" },
                    { title: "Stop", dataIndex: "stop_loss" },
                    { title: "Status", dataIndex: "status" }
                  ]}
                  locale={{ emptyText: <Empty description="No synced positions yet." /> }}
                />
              )
            },
            {
              key: "snapshots",
              label: "Snapshots",
              children: (
                <Table
                  size="small"
                  pagination={{ pageSize: 8 }}
                  dataSource={dbSnapshotRows}
                  columns={[
                    { title: "Date", dataIndex: "snapshot_date" },
                    { title: "Ready", dataIndex: "ready", render: (value) => (value ? <Tag color="green">YES</Tag> : <Tag color="gold">NO</Tag>) },
                    { title: "Sessions", dataIndex: "sessions_logged" },
                    { title: "Scanner Checks", dataIndex: "scanner_reconciliations" },
                    { title: "MF Events", dataIndex: "mf_sweep_events" },
                    { title: "Fill Checks", dataIndex: "fill_checks" }
                  ]}
                  locale={{ emptyText: <Empty description="No synced portfolio snapshots yet." /> }}
                />
              )
            }
          ]}
        />
      </Card>

      <Card title="Operational Audit Trail" size="small">
        <Table
          size="small"
          pagination={{ pageSize: 8 }}
          dataSource={auditRows}
          columns={[
            { title: "Time", dataIndex: "event_time" },
            { title: "Type", dataIndex: "event_type" },
            { title: "Severity", dataIndex: "severity", render: (value) => <Tag color={value === "warning" ? "gold" : value === "error" ? "red" : "blue"}>{text(value)}</Tag> },
            { title: "Summary", dataIndex: "summary" }
          ]}
          locale={{ emptyText: <Empty description={auditResult.ok ? "No audit events yet." : auditResult.error} /> }}
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="Regime Mix" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {Object.entries(regime.distribution || {}).map(([label, item]) => (
                <MiniBar
                  key={label}
                  label={label}
                  value={pctNumber(item.pct)}
                  tone={label === "UPTREND" ? "ok" : label === "DOWNTREND" ? "bad" : "warn"}
                />
              ))}
            </Space>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="Paper Validation Progress" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {readinessItems.map((item) => (
                <div key={item.label}>
                  <div className="progress-label"><span>{item.label}</span><span>{item.value}/{item.target}</span></div>
                  <Progress percent={Math.min(100, Math.round((item.value / item.target) * 100))} size="small" />
                </div>
              ))}
            </Space>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="DB Sync Volume" size="small">
            <Space direction="vertical" style={{ width: "100%" }}>
              {dbCounts.map((item) => (
                <MiniBar key={item.label} label={item.label} value={(item.value / maxDbCount) * 100} />
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      <Card title="Open Caveats" size="small">
        {(backtest.open_caveats || []).length ? (
          <ul>
            {(backtest.open_caveats || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
        ) : (
          <Typography.Text type="secondary">No caveats were found in the research closure artifact.</Typography.Text>
        )}
      </Card>
    </Space>
  );
}
