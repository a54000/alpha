import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { safeApiGet } from "@/lib/api";

type Payload = {
  summary: Record<string, unknown>;
  steps: Array<Record<string, unknown>>;
  monitoring_reports: Array<Record<string, unknown>>;
};

export default async function OperationsPage() {
  const result = await safeApiGet<Payload>("/pipeline/status");
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Operations" subtitle="Pipeline execution status, failures, and data freshness." />
        <ErrorState message={result.error} />
      </>
    );
  }
  const data = result.data;
  return (
    <>
      <PageHeader title="Operations" subtitle="Pipeline execution status, failures, and data freshness." />
      <div className="grid cols-4">
        <MetricCard label="Status" value={String(data.summary.status ?? "unknown")} tone={data.summary.status === "failed" ? "bad" : "ok"} />
        <MetricCard label="Failed Steps" value={String(data.summary.failed_steps ?? 0)} />
        <MetricCard label="Latest Candle" value={String(data.summary.latest_candle_at ?? "n/a")} />
        <MetricCard label="Latest Recs" value={String(data.summary.latest_recommendation_date ?? "n/a")} />
      </div>
      {!data.steps.length ? <EmptyState message="No pipeline run rows were returned by the API." /> : null}
      <section className="panel table-wrap" style={{ marginTop: 16 }}>
        <h2>Pipeline Steps</h2>
        <table>
          <thead><tr><th>Business Date</th><th>Step</th><th>Status</th><th>Started</th><th>Completed</th><th>Error</th></tr></thead>
          <tbody>
            {data.steps.map((row, index) => (
              <tr key={`${row.step_name}-${index}`}>
                <td>{String(row.business_date || "n/a")}</td><td>{String(row.step_name)}</td><td>{String(row.status)}</td>
                <td>{String(row.started_at || "n/a")}</td><td>{String(row.completed_at || "n/a")}</td><td>{String(row.error_message || "")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel table-wrap" style={{ marginTop: 16 }}>
        <h2>Monitoring Reports</h2>
        {!data.monitoring_reports.length ? <p className="subtitle">No monitoring reports found.</p> : null}
        <table>
          <thead><tr><th>Name</th><th>Modified</th></tr></thead>
          <tbody>
            {data.monitoring_reports.map((row) => (
              <tr key={String(row.name)}><td>{String(row.name)}</td><td>{String(row.modified_at)}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
