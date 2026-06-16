import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { DataStatusCard } from "@/components/DataStatusCard";
import { money, pct, safeApiGet } from "@/lib/api";

type DashboardPayload = {
  portfolio?: Record<string, unknown>;
  risk?: Record<string, unknown>;
  benchmark?: Record<string, unknown>;
  system_health?: Record<string, unknown>;
};

type PipelinePayload = {
  summary?: Record<string, unknown>;
  steps?: Array<{ business_date?: string | null; status?: string | null }>;
};

export default async function DashboardPage() {
  const [result, pipelineResult] = await Promise.all([
    safeApiGet<DashboardPayload>("/dashboard"),
    safeApiGet<PipelinePayload>("/pipeline/status")
  ]);
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Dashboard" subtitle="NAV, PnL, benchmark, and system health for Sector Rotation ADX Rolling 10." />
        <ErrorState message={result.error} />
      </>
    );
  }
  const data = result.data;
  const pipeline = pipelineResult.ok ? pipelineResult.data : undefined;
  const hasData = Boolean(
    Object.keys(data.portfolio || {}).length ||
    Object.keys(data.system_health || {}).length ||
    Object.keys(data.risk || {}).length
  );
  return (
    <>
      <PageHeader title="Dashboard" subtitle="NAV, PnL, benchmark, and system health for Sector Rotation ADX Rolling 10." />
      {!hasData ? (
        <EmptyState message="The API responded, but no dashboard metrics are available yet." />
      ) : null}
      <DataStatusCard
        latestMarketDataDate={data.system_health?.latest_candle_at}
        latestRecommendationDate={data.system_health?.latest_recommendation_date}
        pipelineStatus={pipeline?.summary?.status}
        pipelineSteps={pipeline?.steps}
        pipelineError={pipelineResult.ok ? null : pipelineResult.error}
      />
      <div className="grid cols-4">
        <MetricCard label="NAV" value={money(data.portfolio?.nav ?? data.portfolio?.current_nav)} />
        <MetricCard label="Realized PnL" value={money(data.portfolio?.realized_pnl)} />
        <MetricCard label="Drawdown" value={pct(data.risk?.drawdown)} tone={Number(data.risk?.drawdown ?? 0) < -0.1 ? "bad" : undefined} />
        <MetricCard label="Benchmark Return" value={pct(data.benchmark?.return)} />
      </div>
      {data.portfolio?.latest_paper_update_message ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Paper Trading Status</h2>
          <p className="subtitle">{String(data.portfolio.latest_paper_update_message)}</p>
        </section>
      ) : null}
      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <section className="panel">
          <h2>System Health</h2>
          <table>
            <tbody>
              <tr><td>Status</td><td>{String(data.system_health?.status ?? "unknown")}</td></tr>
              <tr><td>Latest candle</td><td>{String(data.system_health?.latest_candle_at ?? "n/a")}</td></tr>
              <tr><td>Latest features</td><td>{String(data.system_health?.latest_feature_date ?? "n/a")}</td></tr>
              <tr><td>Latest recommendations</td><td>{String(data.system_health?.latest_recommendation_date ?? "n/a")}</td></tr>
            </tbody>
          </table>
        </section>
        <section className="panel">
          <h2>Exposure</h2>
          <table>
            <tbody>
              <tr><td>Invested</td><td>{money(data.portfolio?.market_value)}</td></tr>
              <tr><td>Cash</td><td>{money(data.portfolio?.cash)}</td></tr>
              <tr><td>Exposure</td><td>{pct(data.risk?.exposure)}</td></tr>
              <tr><td>Max sector weight</td><td>{pct(data.risk?.max_sector_weight)}</td></tr>
            </tbody>
          </table>
        </section>
      </div>
    </>
  );
}
