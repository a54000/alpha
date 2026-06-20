import { AlertTriangle } from "lucide-react";
import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { pct, safeApiGet } from "@/lib/api";

type BreadthPoint = {
  date: string;
  nifty_close?: number | null;
  pct_above_50dma?: number | null;
};

type Payload = {
  as_of: string | null;
  summary?: {
    total_symbols?: number;
    advancing?: number;
    declining?: number;
    unchanged?: number;
    advancer_pct?: number | null;
    pct_above_50dma?: number | null;
    pct_below_50dma?: number | null;
    pct_above_200dma?: number | null;
    pct_above_50dma_count?: number;
    pct_above_50dma_denominator?: number;
    pct_above_200dma_count?: number;
    pct_above_200dma_denominator?: number;
    new_52w_highs?: number;
    new_52w_lows?: number;
    nifty_close?: number | null;
    nifty_sma_50?: number | null;
    nifty_sma_200?: number | null;
    divergence?: {
      status?: string;
      message?: string;
    };
    composite?: {
      status?: string;
      weighted_score?: number;
      capped_by_divergence?: boolean;
      previous_status?: string;
      persistence_note?: string;
      method?: string;
      votes?: Array<{ metric: string; band: string; weight: number }>;
    };
  };
  chart?: BreadthPoint[];
  cache?: {
    hit?: boolean;
    ttl_seconds?: number;
    generated_at?: string;
  };
};

function n(value: unknown, digits = 0) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "n/a";
  return number.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function linePath(values: Array<number | null>, width: number, height: number, min?: number, max?: number, offsetX = 0, offsetY = 0) {
  const valid = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (valid.length < 2) return "";
  const lo = min ?? Math.min(...valid);
  const hi = max ?? Math.max(...valid);
  const range = hi - lo || 1;
  return values
    .map((value, index) => {
      if (value === null || !Number.isFinite(value)) return "";
      const x = offsetX + (index / Math.max(values.length - 1, 1)) * width;
      const y = offsetY + height - ((value - lo) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function BreadthTrendChart({ points }: { points: BreadthPoint[] }) {
  const width = 760;
  const height = 260;
  const margin = { left: 62, right: 54, top: 16, bottom: 30 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const nifty = points.map((point) => (point.nifty_close == null ? null : Number(point.nifty_close)));
  const breadth = points.map((point) => (point.pct_above_50dma == null ? null : Number(point.pct_above_50dma) * 100));
  const niftyValid = nifty.filter((value): value is number => value !== null);
  if (niftyValid.length < 2) return <EmptyState message="Not enough market breadth history to draw the chart." />;
  const min = Math.min(...niftyValid);
  const max = Math.max(...niftyValid);
  const xLabels = [points[0]?.date, points[Math.floor((points.length - 1) / 2)]?.date, points[points.length - 1]?.date];
  const yTicks = [max, (min + max) / 2, min];
  const niftyPath = linePath(nifty, plotWidth, plotHeight, min, max, margin.left, margin.top);
  const breadthPath = linePath(breadth, plotWidth, plotHeight, 0, 100, margin.left, margin.top);
  return (
    <svg className="breadth-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Nifty and breadth trend">
      {yTicks.map((tick, index) => {
        const y = margin.top + (index / 2) * plotHeight;
        return (
          <g key={tick.toFixed(2)}>
            <line x1={margin.left} x2={width - margin.right} y1={y} y2={y} className="chart-gridline" />
            <text x={margin.left - 8} y={y + 4} className="chart-axis-label" textAnchor="end">{n(tick, 0)}</text>
            <text x={width - margin.right + 8} y={y + 4} className="chart-axis-label" textAnchor="start">{index === 0 ? "100%" : index === 1 ? "50%" : "0%"}</text>
          </g>
        );
      })}
      <path d={niftyPath} className="chart-line nifty" />
      <path d={breadthPath} className="chart-line breadth" />
      {xLabels.map((label, index) => (
        <text key={`${label}-${index}`} x={margin.left + (index / 2) * plotWidth} y={height - 8} className="chart-axis-label" textAnchor={index === 0 ? "start" : index === 2 ? "end" : "middle"}>
          {String(label || "n/a")}
        </text>
      ))}
    </svg>
  );
}

export default async function MarketBreadthPage() {
  const result = await safeApiGet<Payload>("/market-breadth", { next: { revalidate: 900 } });
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Market Breadth" subtitle="Top-of-funnel market health before sector and stock selection." />
        <ErrorState message={result.error} />
      </>
    );
  }
  const data = result.data;
  const summary = data.summary || {};
  const divergence = summary.divergence || {};
  const composite = summary.composite || {};
  const isBearish = divergence.status === "bearish";
  const statusClass = String(composite.status || "Sideways").toLowerCase();
  return (
    <>
      <PageHeader
        title="Market Breadth"
        subtitle="A broad market health check before choosing sectors or stocks."
        actions={
          <div className="refresh-badge">
            <span>Refresh Date</span>
            <strong>{data.as_of || "n/a"}</strong>
          </div>
        }
      />

      <section className={`panel market-health ${statusClass}`}>
        <div>
          <span className="eyebrow">Composite market health</span>
          <div className="market-health-title">
            <h2>{composite.status || "Sideways"}</h2>
            <span className={`status-pill ${statusClass === "bullish" ? "ok" : statusClass === "bearish" ? "bad" : "warn"}`}>
              {composite.capped_by_divergence ? "Capped by divergence" : "Latest read"}
            </span>
          </div>
          <p>
            Breadth is being read across participation, trend breadth, daily direction, and new high/new low leadership.
            {composite.capped_by_divergence ? " Bearish divergence has capped the reading to Sideways." : ""}
          </p>
          {composite.persistence_note ? <p className="fine-print">{composite.persistence_note}</p> : null}
        </div>
        <details className="ops-details market-health-details">
          <summary>Market health calculation</summary>
          <div className="vote-list">
            {(composite.votes || []).map((vote) => (
              <div className="vote-row" key={vote.metric}>
                <span>{vote.metric}</span>
                <strong className={`vote-${vote.band}`}>{vote.band}</strong>
              </div>
            ))}
          </div>
        </details>
      </section>

      {isBearish ? (
        <section className="breadth-alert">
          <AlertTriangle size={24} aria-hidden="true" />
          <div>
            <strong>Bearish breadth divergence</strong>
            <p>{divergence.message}</p>
          </div>
        </section>
      ) : null}

      <div className="grid cols-4">
        <MetricCard label="Advancing / Declining" value={`${n(summary.advancing)} / ${n(summary.declining)}`} />
        <MetricCard label="Advancers %" value={pct(summary.advancer_pct)} />
        <MetricCard label="Above 50-day average" value={pct(summary.pct_above_50dma)} />
        <MetricCard label="Above 200-day average" value={pct(summary.pct_above_200dma)} />
      </div>

      <div className="grid cols-4">
        <MetricCard label="50DMA count" value={`${n(summary.pct_above_50dma_count)} / ${n(summary.pct_above_50dma_denominator)}`} />
        <MetricCard label="200DMA count" value={`${n(summary.pct_above_200dma_count)} / ${n(summary.pct_above_200dma_denominator)}`} />
        <MetricCard label="52-week highs / lows" value={`${n(summary.new_52w_highs)} / ${n(summary.new_52w_lows)}`} />
        <MetricCard label="Market health" value={String(composite.status || "Sideways")} />
      </div>

      <div className="grid cols-1">
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Nifty 50 vs 50-DMA Breadth</h2>
              <p className="subtitle">A rising index with falling breadth can warn that fewer stocks are carrying the market.</p>
            </div>
          </div>
          <div className="chart-legend">
            <span className="nifty">Nifty 50</span>
            <span className="breadth">% above 50DMA</span>
          </div>
          <BreadthTrendChart points={data.chart || []} />
        </section>
      </div>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>How to Read This</h2>
            <p className="subtitle">Market Breadth sits above sector selection in the top-down funnel.</p>
          </div>
        </div>
        <div className="funnel-grid">
          <div className="funnel-step"><span>1</span><div><strong>Participation</strong><p>More advancers than decliners means the day is broadly supported.</p></div></div>
          <div className="funnel-step"><span>2</span><div><strong>Trend breadth</strong><p>50DMA shows short-term health; 200DMA shows long-term participation.</p></div></div>
          <div className="funnel-step"><span>3</span><div><strong>Leadership</strong><p>52-week highs versus lows shows whether real leadership is expanding.</p></div></div>
          <div className="funnel-step"><span>4</span><div><strong>Divergence</strong><p>If Nifty rises while breadth falls, position sizing should become more cautious.</p></div></div>
        </div>
      </section>
    </>
  );
}
