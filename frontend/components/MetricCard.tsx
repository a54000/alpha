import type { ReactNode } from "react";

export function MetricCard({
  icon,
  label,
  value,
  hint,
  tone
}: {
  icon?: ReactNode;
  label: string;
  value: string;
  hint?: string;
  tone?: "ok" | "warn" | "bad";
}) {
  return (
    <section className="panel metric-card">
      <div className="metric-head">
        <div className="metric-label">{label}</div>
        {icon ? <span className="metric-icon">{icon}</span> : null}
      </div>
      <div className={`metric-value metric-value-compact ${tone || ""}`}>{value}</div>
      {hint ? <p className="metric-hint">{hint}</p> : null}
    </section>
  );
}
