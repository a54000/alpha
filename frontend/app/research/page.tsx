import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { safeApiGet } from "@/lib/api";
import Link from "next/link";
import styles from "./research.module.css";

type MetricBlock = Record<string, unknown>;

type VariantBlock = {
  config?: Record<string, unknown>;
  metrics?: MetricBlock;
  closed_trade_count?: number;
};

type Payload = {
  summary: Record<string, unknown>;
  portfolio_metrics?: {
    generated_on?: string;
    date_range?: { start?: string; end?: string };
    methodology?: Record<string, unknown>;
    variants?: Record<string, VariantBlock>;
  };
  walk_forward?: {
    stability_summary?: Record<string, Record<string, unknown>>;
  };
  paper_replay?: Record<string, {
    paper_metrics?: MetricBlock;
    phase2e_metrics?: MetricBlock;
    trade_matching?: Record<string, unknown>;
    first_divergence?: Record<string, unknown>;
    root_cause_classification?: Array<Record<string, unknown>>;
  }>;
};

function asNumber(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatPct(value: unknown, digits = 2): string {
  const number = asNumber(value);
  if (number === null) return "n/a";
  return `${(number * 100).toFixed(digits)}%`;
}

function formatNumber(value: unknown, digits = 2): string {
  const number = asNumber(value);
  if (number === null) return "n/a";
  return number.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function formatDateRange(start?: string, end?: string): string {
  if (!start && !end) return "n/a";
  return `${start || "n/a"} to ${end || "n/a"}`;
}

function VariantMetricCard({ title, variant }: { title: string; variant?: VariantBlock }) {
  const metrics = variant?.metrics || {};
  return (
    <section className="panel">
      <div className="metric-label">{title}</div>
      <div className="metric-value">{formatPct(metrics.cagr)}</div>
      <div className={styles.metricGrid}>
        <span>Total return</span><strong>{formatPct(metrics.total_return)}</strong>
        <span>Max drawdown</span><strong>{formatPct(metrics.max_drawdown)}</strong>
        <span>Sharpe</span><strong>{formatNumber(metrics.sharpe_ratio)}</strong>
        <span>Profit factor</span><strong>{formatNumber(metrics.profit_factor)}</strong>
        <span>Win rate</span><strong>{formatPct(metrics.win_rate)}</strong>
        <span>Closed trades</span><strong>{formatNumber(metrics.closed_trades ?? variant?.closed_trade_count, 0)}</strong>
      </div>
    </section>
  );
}

function EvidenceRow({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" | "bad" }) {
  return (
    <div className={styles.evidenceRow}>
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

export default async function ResearchPage() {
  const result = await safeApiGet<Payload>("/research/metrics");
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Research" subtitle="Evidence behind the Sector Rotation ADX Rolling 10 strategy." />
        <ErrorState message={result.error} />
      </>
    );
  }

  const data = result.data;
  const variants = data.portfolio_metrics?.variants || {};
  const top5 = variants.top5_weekly;
  const top10 = variants.top10_weekly;
  const sectorCap = variants.top10_weekly_max2_sector;
  const range = data.portfolio_metrics?.date_range || {};
  const top5WalkForward = data.walk_forward?.stability_summary?.top5_weekly || {};
  const top10WalkForward = data.walk_forward?.stability_summary?.top10_weekly || {};
  const top10Paper = data.paper_replay?.top10_weekly;
  const hasStudies = Object.keys(data.summary || {}).length > 0;

  return (
    <>
      <PageHeader
        title="Research"
        subtitle="Validation evidence, robustness checks, and analysis tools for Sector Rotation ADX Rolling 10."
      />

      {!hasStudies ? <EmptyState message="No research metrics were returned by the API." /> : null}

      <section className={`panel ${styles.verdict}`}>
        <div>
          <div className="metric-label">Current research decision</div>
          <h2>Rolling 10 remains the preferred construction for paper observation.</h2>
          <p className="subtitle">
            The long-history evidence is positive, but deployment still depends on live paper tracking,
            fill behavior, data freshness, and drawdown discipline.
          </p>
        </div>
        <div className={styles.verdictStats}>
          <EvidenceRow label="Validation window" value={formatDateRange(range.start, range.end)} />
          <EvidenceRow label="Latest research refresh" value={data.portfolio_metrics?.generated_on || "n/a"} />
          <EvidenceRow label="Strategy state" value="Frozen" tone="ok" />
        </div>
      </section>

      <div className={styles.topGrid}>
        <VariantMetricCard title="Top 5 Weekly" variant={top5} />
        <VariantMetricCard title="Top 10 Weekly" variant={top10} />
        <VariantMetricCard title="Top 10 + Sector Cap" variant={sectorCap} />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <section className="panel">
          <h2>Walk-Forward Stability</h2>
          <div className={styles.copy}>
            <p>
              This checks whether the edge survives independent time segments instead of being driven by
              one lucky window.
            </p>
          </div>
          <div className={styles.metricGrid}>
            <span>Top 5 positive CAGR periods</span><strong>{formatNumber(top5WalkForward.positive_cagr_periods, 0)}</strong>
            <span>Top 5 worst drawdown</span><strong>{formatPct(top5WalkForward.max_drawdown_worst)}</strong>
            <span>Top 5 edge disappears</span><strong className={top5WalkForward.edge_disappears ? "bad" : "ok"}>{String(top5WalkForward.edge_disappears ?? "n/a")}</strong>
            <span>Top 10 positive CAGR periods</span><strong>{formatNumber(top10WalkForward.positive_cagr_periods, 0)}</strong>
            <span>Top 10 worst drawdown</span><strong>{formatPct(top10WalkForward.max_drawdown_worst)}</strong>
            <span>Top 10 edge disappears</span><strong className={top10WalkForward.edge_disappears ? "bad" : "ok"}>{String(top10WalkForward.edge_disappears ?? "n/a")}</strong>
          </div>
        </section>

        <section className="panel">
          <h2>Paper Replay Reconciliation</h2>
          <div className={styles.copy}>
            <p>
              This compares the paper engine with the historical backtest so operational accounting does
              not drift away from the validated method.
            </p>
          </div>
          <div className={styles.metricGrid}>
            <span>Top 10 paper CAGR</span><strong>{formatPct(top10Paper?.paper_metrics?.cagr)}</strong>
            <span>Top 10 backtest CAGR</span><strong>{formatPct(top10Paper?.phase2e_metrics?.cagr)}</strong>
            <span>Matched trades</span><strong>{formatNumber(top10Paper?.trade_matching?.matched_trades, 0)}</strong>
            <span>Price mismatches</span><strong className="ok">{formatNumber(top10Paper?.trade_matching?.price_mismatch_count, 0)}</strong>
            <span>First divergence</span><strong>{String(top10Paper?.first_divergence?.date || "n/a")}</strong>
            <span>Open reconciliation items</span><strong className="warn">{formatNumber(top10Paper?.root_cause_classification?.length, 0)}</strong>
          </div>
        </section>
      </div>

      <section className="panel" style={{ marginTop: 16 }}>
        <h2>What Still Needs Attention</h2>
        <div className={styles.calloutGrid}>
          <div>
            <strong>2025 weakness</strong>
            <p className="subtitle">Recent period returns were weaker than the 2022-2024 trend and need live observation.</p>
          </div>
          <div>
            <strong>Concentration risk</strong>
            <p className="subtitle">Strong results were helped by sector momentum bursts, especially around 2024.</p>
          </div>
          <div>
            <strong>Operational parity</strong>
            <p className="subtitle">Paper trading must keep matching the frozen recommendation and holding-period rules.</p>
          </div>
        </div>
      </section>

      <section className="panel" style={{ marginTop: 16 }}>
        <h2>Research Tools</h2>
        <div className="download-row" style={{ marginTop: 12 }}>
          <Link className="download-link" href="/research/rolling-portfolio">Rolling Portfolio</Link>
          <Link className="download-link" href="/research/trade-analysis">Trade Analysis</Link>
        </div>
      </section>
    </>
  );
}
