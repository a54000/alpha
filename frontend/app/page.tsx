import { MetricCard } from "@/components/MetricCard";
import { DashboardRecommendations } from "@/components/DashboardRecommendations";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { money, pct, safeApiGet } from "@/lib/api";
import Link from "next/link";

type DashboardPayload = {
  portfolio?: Record<string, unknown>;
  risk?: Record<string, unknown>;
  benchmark?: Record<string, unknown>;
  system_health?: Record<string, unknown>;
};

type Rec = {
  rank: number;
  symbol: string;
  score?: number;
  sector?: string;
  adx_points?: number;
  sector_points?: number;
};

type RecommendationsPayload = {
  date: string | null;
  recommendations: Rec[];
};

type PipelinePayload = {
  summary?: Record<string, unknown>;
  steps?: Array<{ business_date?: string | null; status?: string | null }>;
};

type ResearchMetricsPayload = {
  sector_1m3m?: {
    metrics?: Record<string, unknown> | null;
    monte_carlo?: Record<string, unknown> | null;
  };
  cash_sweep_overlay?: {
    method?: string | null;
    assumptions?: Record<string, unknown> | null;
    scenario?: Record<string, unknown> | null;
    source?: string;
  };
};

type MarketBreadthPayload = {
  as_of?: string | null;
  summary?: {
    total_symbols?: number;
    symbols_with_current_bar?: number;
    current_bar_coverage_pct?: number | null;
    advancing?: number;
    declining?: number;
    advancer_pct?: number | null;
    pct_above_50dma?: number | null;
    pct_above_50dma_count?: number;
    pct_above_50dma_denominator?: number;
    pct_above_200dma?: number | null;
    pct_above_200dma_count?: number;
    pct_above_200dma_denominator?: number;
    composite?: {
      status?: string;
    };
    market_lens?: {
      lens?: string;
      raw_lens?: string;
      benchmark_used?: string;
      benchmark_note?: string;
      bias_modifiers?: string[];
      instruction?: string;
      persistence?: {
        pending?: boolean;
        pending_lens?: string | null;
        pending_days?: number;
        days_needed?: number;
      };
      signals?: {
        breadth_50ema?: number | null;
        nifty_3m_return?: number | null;
        atr_pct?: number | null;
      };
    };
  };
};

const model = "sector_rotation_adx_1m3m";

function dateOnly(value: unknown) {
  return String(value ?? "").match(/\d{4}-\d{2}-\d{2}/)?.[0] ?? null;
}

function trustCopy(data: DashboardPayload, recommendations: RecommendationsPayload | undefined, pipeline: PipelinePayload | undefined) {
  const recommendationDate = recommendations?.date || dateOnly(data.system_health?.latest_recommendation_date);
  const marketDate = dateOnly(data.system_health?.latest_candle_at);
  const status = String(pipeline?.summary?.status ?? data.system_health?.status ?? "unknown").toLowerCase();
  const currentDate = recommendationDate || marketDate;
  if (status.includes("fail") || status.includes("error")) {
    return { tone: "bad", label: "Needs review", text: `System data needs attention${currentDate ? `; latest usable close is ${currentDate}` : ""}.` };
  }
  if (status.includes("stale") || status.includes("delayed")) {
    return { tone: "warn", label: "Stale", text: `Recommendations may be stale${currentDate ? `; latest close is ${currentDate}` : ""}.` };
  }
  if (currentDate) {
    return { tone: "ok", label: "Up to date", text: `Data current as of ${currentDate} close.` };
  }
  return { tone: "warn", label: "Unknown", text: "Data currentness is not available yet." };
}

function benchmarkHint(data: DashboardPayload) {
  const startDate = dateOnly(data.benchmark?.return_start_date);
  const latestAvailable = dateOnly(data.benchmark?.latest_available_date);
  if (data.benchmark?.return === null || data.benchmark?.return === undefined) {
    return latestAvailable ? `Index data through ${latestAvailable}` : "Index data unavailable";
  }
  return startDate ? `Since first trade on ${startDate}` : "Since first trade";
}

export default async function DashboardPage() {
  const [result, pipelineResult, recommendationsResult, researchResult, breadthResult] = await Promise.all([
    safeApiGet<DashboardPayload>("/dashboard"),
    safeApiGet<PipelinePayload>("/pipeline/status"),
    safeApiGet<RecommendationsPayload>(`/recommendations/latest?model=${encodeURIComponent(model)}&limit=2`),
    safeApiGet<ResearchMetricsPayload>("/research/metrics"),
    safeApiGet<MarketBreadthPayload>("/market-breadth")
  ]);
  if (!result.ok) {
    return (
      <div className="morning-brief">
        <section className="morning-head">
          <h1>Good morning</h1>
          <p>Dashboard data needs attention.</p>
        </section>
        <ErrorState message={result.error} />
      </div>
    );
  }
  const data = result.data;
  const pipeline = pipelineResult.ok ? pipelineResult.data : undefined;
  const recommendations = recommendationsResult.ok ? recommendationsResult.data : undefined;
  const research = researchResult.ok ? researchResult.data : undefined;
  const breadth = breadthResult.ok ? breadthResult.data : undefined;
  const breadthSummary = breadth?.summary;
  const backtest = research?.sector_1m3m?.metrics;
  const monteCarlo = research?.sector_1m3m?.monte_carlo;
  const trust = trustCopy(data, recommendations, pipeline);
  const reviewItems = recommendations?.recommendations ?? [];
  const hasData = Boolean(
    Object.keys(data.portfolio || {}).length ||
    Object.keys(data.system_health || {}).length ||
    Object.keys(data.risk || {}).length
  );
  return (
    <div className="morning-brief">
      <section className="morning-head">
        <div>
          <h1>Good morning</h1>
          <p>{trust.text}</p>
        </div>
        <span className={`status-pill ${trust.tone}`}>{trust.label}</span>
      </section>
      {!hasData ? (
        <EmptyState message="The API responded, but no dashboard metrics are available yet." />
      ) : null}

      <section className={`action-brief ${reviewItems.length ? "" : "quiet"}`}>
        <h2>{reviewItems.length ? "Today's Recommendation" : "No recommendation today"}</h2>
        <DashboardRecommendations items={reviewItems} />
      </section>

      <div className="grid cols-4 dashboard-kpis">
        <MetricCard label="Portfolio value" value={money(data.portfolio?.nav ?? data.portfolio?.current_nav)} hint={`NAV return ${pct(data.benchmark?.nav_return)}`} />
        <MetricCard label="Open positions" value={String(data.portfolio?.open_positions ?? "n/a")} hint={`${pct(data.risk?.exposure)} of capital deployed`} />
        <MetricCard label="Drawdown from peak" value={pct(data.risk?.drawdown)} tone={Number(data.risk?.drawdown ?? 0) < -0.1 ? "bad" : undefined} />
        <MetricCard label="NIFTY 500 return" value={pct(data.benchmark?.return)} hint={benchmarkHint(data)} />
      </div>

      <section className="panel validation-snapshot">
        <div className="section-head">
          <div>
            <h2>Market Breadth</h2>
            <p className="subtitle">
              Layer 1 Market Lens: {breadthSummary?.market_lens?.lens || "n/a"}.
              {" "}{breadthSummary?.market_lens?.instruction || `Expanded universe participation as of ${breadth?.as_of || "latest close"}.`}
            </p>
            {breadthSummary?.market_lens?.benchmark_note ? (
              <p className="fine-print">Benchmark: {breadthSummary.market_lens.benchmark_used || "n/a"}. {breadthSummary.market_lens.benchmark_note}</p>
            ) : null}
            {breadthSummary?.market_lens?.bias_modifiers?.length ? (
              <p className="fine-print">Bias modifiers: {breadthSummary.market_lens.bias_modifiers.join("; ")}</p>
            ) : null}
            {breadthSummary?.market_lens?.persistence?.pending ? (
              <p className="fine-print">
                Raw lens is {breadthSummary.market_lens.raw_lens || breadthSummary.market_lens.persistence.pending_lens}; waiting {breadthSummary.market_lens.persistence.days_needed} more session(s) before confirming.
              </p>
            ) : null}
          </div>
          <Link className="secondary-button" href="/market-breadth">Details</Link>
        </div>
        <div className="grid cols-4">
          <MetricCard
            label="Universe tracked"
            value={String(breadthSummary?.total_symbols ?? "n/a")}
            hint={`${breadthSummary?.symbols_with_current_bar ?? "n/a"} current-date bars · ${pct(breadthSummary?.current_bar_coverage_pct)}`}
          />
          <MetricCard label="Advancing / declining" value={`${breadthSummary?.advancing ?? "n/a"} / ${breadthSummary?.declining ?? "n/a"}`} hint={pct(breadthSummary?.advancer_pct)} />
          <MetricCard
            label="Above 50-day average"
            value={pct(breadthSummary?.pct_above_50dma)}
            hint={`${breadthSummary?.pct_above_50dma_count ?? "n/a"} / ${breadthSummary?.pct_above_50dma_denominator ?? "n/a"}`}
          />
          <MetricCard
            label="Above 200-day average"
            value={pct(breadthSummary?.pct_above_200dma)}
            hint={`${breadthSummary?.pct_above_200dma_count ?? "n/a"} / ${breadthSummary?.pct_above_200dma_denominator ?? "n/a"} · ${breadthSummary?.composite?.status ?? "n/a"}`}
          />
        </div>
        <div className="grid cols-3" style={{ marginTop: 14 }}>
          <MetricCard label="Market Lens" value={String(breadthSummary?.market_lens?.lens || "n/a")} hint={String(breadthSummary?.market_lens?.benchmark_used || "Read-only context")} />
          <MetricCard label="Breadth above 50 EMA" value={pct(breadthSummary?.market_lens?.signals?.breadth_50ema)} />
          <MetricCard label="Nifty 3M / ATR" value={pct(breadthSummary?.market_lens?.signals?.nifty_3m_return)} hint={`ATR ${pct(breadthSummary?.market_lens?.signals?.atr_pct)}`} />
        </div>
      </section>

      <section className="panel validation-snapshot">
        <div className="section-head">
          <div>
            <h2>Validation snapshot</h2>
            <p className="subtitle">Pure backtest evidence for SectorEdge 10.</p>
          </div>
          <Link className="secondary-button" href="/research">Research</Link>
        </div>
        <div className="grid cols-5">
          <MetricCard label="Backtest CAGR" value={pct(backtest?.cagr)} />
          <MetricCard label="Max drawdown" value={pct(backtest?.max_drawdown)} tone="warn" />
          <MetricCard label="Sharpe" value={backtest?.sharpe_ratio === undefined ? "n/a" : Number(backtest.sharpe_ratio).toFixed(2)} />
          <MetricCard label="Win rate" value={pct(backtest?.win_rate)} />
          <MetricCard label="Monte Carlo median CAGR" value={pct(monteCarlo?.median_cagr)} />
        </div>
      </section>

      <details className="ops-details">
        <summary>System and pipeline status</summary>
        <div className="grid cols-2 dashboard-detail">
          <section className="panel">
            <div className="section-head">
              <h2>System health</h2>
              <span className="chip">{String(data.system_health?.status ?? "unknown")}</span>
            </div>
            <table>
              <tbody>
                <tr><td>Latest candle</td><td>{String(data.system_health?.latest_candle_at ?? "n/a")}</td></tr>
                <tr><td>Latest features</td><td>{String(data.system_health?.latest_feature_date ?? "n/a")}</td></tr>
                <tr><td>Latest recommendations</td><td>{String(data.system_health?.latest_recommendation_date ?? "n/a")}</td></tr>
                <tr><td>Pipeline summary</td><td>{String(pipeline?.summary?.status ?? "n/a")}</td></tr>
              </tbody>
            </table>
          </section>
          <section className="panel">
            <div className="section-head">
              <h2>Exposure</h2>
              <Link className="secondary-button" href="/operations">Operations</Link>
            </div>
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
      </details>
    </div>
  );
}
