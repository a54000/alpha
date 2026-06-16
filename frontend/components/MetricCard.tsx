export function MetricCard({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" | "bad" }) {
  return (
    <section className="panel">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone || ""}`}>{value}</div>
    </section>
  );
}
