import {
  BacktestSummary,
  AuditTrailPayload,
  DbReadinessPayload,
  DbCount,
  DishaDashboard,
  LockedRules,
  MarketRegime,
  OperatorBoundaryPayload,
  PaperDay1LaunchPayload,
  PaperDayCloseoutPayload,
  PaperMilestonesPayload,
  PaperWorkflowGapSuggestionPayload,
  PaperSessionHealthPayload,
  PaperWorkflowEventsPayload,
  PaperStatus,
  PortfolioSummary,
  ReadinessPayload,
  ScannerReconciliationSuggestionPayload,
  ScannerRemediationPayload,
  ScannerRerunRunbookPayload,
  SignalsToday,
  SyncStatus
} from "@/components/DishaDashboard";
import { safeApiGet } from "@/lib/api";

export default async function DishaPage() {
  const [rulesResult, backtestResult, regimeResult, signalsResult, paperResult, portfolioResult, readinessResult, dbReadinessResult, auditResult, operatorBoundaryResult, paperWorkflowResult, paperSessionHealthResult, paperMilestonesResult, paperDay1LaunchResult, scannerRemediationResult, scannerRerunRunbookResult, scannerReconciliationSuggestionResult, paperDayCloseoutResult, paperWorkflowGapSuggestionResult, signals, positions, snapshots, events, syncStatus] = await Promise.all([
    safeApiGet<LockedRules>("/api/rules/locked"),
    safeApiGet<BacktestSummary>("/api/backtest/summary"),
    safeApiGet<MarketRegime>("/api/market/regime"),
    safeApiGet<SignalsToday>("/api/signals/today"),
    safeApiGet<PaperStatus>("/api/paper/status"),
    safeApiGet<PortfolioSummary>("/api/portfolio/summary"),
    safeApiGet<ReadinessPayload>("/api/readiness"),
    safeApiGet<DbReadinessPayload>("/api/db/readiness"),
    safeApiGet<AuditTrailPayload>("/api/db/audit/trail?limit=50"),
    safeApiGet<OperatorBoundaryPayload>("/api/operator/boundary"),
    safeApiGet<PaperWorkflowEventsPayload>("/api/db/paper/workflow-events?limit=50"),
    safeApiGet<PaperSessionHealthPayload>("/api/db/paper/session-health?limit=50"),
    safeApiGet<PaperMilestonesPayload>("/api/db/paper/milestones?limit=5000"),
    safeApiGet<PaperDay1LaunchPayload>("/api/db/paper/day1-launch-checklist?limit=5000"),
    safeApiGet<ScannerRemediationPayload>("/api/db/scanner/remediation"),
    safeApiGet<ScannerRerunRunbookPayload>("/api/db/scanner/rerun-runbook"),
    safeApiGet<ScannerReconciliationSuggestionPayload>("/api/db/scanner/reconciliation-suggestion"),
    safeApiGet<PaperDayCloseoutPayload>("/api/db/paper/day-closeout?limit=500"),
    safeApiGet<PaperWorkflowGapSuggestionPayload>("/api/db/paper/workflow-gap-suggestion?limit=500"),
    safeApiGet<DbCount>("/api/db/signals?limit=50"),
    safeApiGet<DbCount>("/api/db/positions?limit=50"),
    safeApiGet<DbCount>("/api/db/portfolio/snapshots?limit=50"),
    safeApiGet<DbCount>("/api/db/paper/events?limit=50"),
    safeApiGet<SyncStatus>("/api/db/sync/status")
  ]);

  return (
    <DishaDashboard
      rulesResult={rulesResult}
      backtestResult={backtestResult}
      regimeResult={regimeResult}
      signalsResult={signalsResult}
      paperResult={paperResult}
      portfolioResult={portfolioResult}
      readinessResult={readinessResult}
      dbReadinessResult={dbReadinessResult}
      auditResult={auditResult}
      operatorBoundaryResult={operatorBoundaryResult}
      paperWorkflowResult={paperWorkflowResult}
      paperSessionHealthResult={paperSessionHealthResult}
      paperMilestonesResult={paperMilestonesResult}
      paperDay1LaunchResult={paperDay1LaunchResult}
      scannerRemediationResult={scannerRemediationResult}
      scannerRerunRunbookResult={scannerRerunRunbookResult}
      scannerReconciliationSuggestionResult={scannerReconciliationSuggestionResult}
      paperDayCloseoutResult={paperDayCloseoutResult}
      paperWorkflowGapSuggestionResult={paperWorkflowGapSuggestionResult}
      db={{ signals, positions, snapshots, events, syncStatus }}
    />
  );
}
