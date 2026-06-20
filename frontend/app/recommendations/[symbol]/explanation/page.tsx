import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { pct, safeApiGet } from "@/lib/api";
import { strategyLabel } from "@/lib/strategyNames";
import Link from "next/link";

type Payload = {
  source: string;
  business_date: string | null;
  symbol: string;
  rank?: number;
  score?: number;
  recommendation_type: string;
  sector?: string;
  feature_snapshot: Record<string, unknown>;
  created_at?: string | null;
};

function displayNumber(value: unknown, digits = 2): string {
  if (value === null || value === undefined || value === "") return "n/a";
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return number.toFixed(digits);
}

function toneForExtension(value: unknown): "ok" | "warn" | "bad" | undefined {
  const number = Number(value);
  if (Number.isNaN(number)) return undefined;
  if (number > 0.25) return "bad";
  if (number < 0) return "warn";
  return "ok";
}

function toneForMomentum(value: unknown): "ok" | "warn" | undefined {
  const number = Number(value);
  if (Number.isNaN(number)) return undefined;
  return number >= 0 ? "ok" : "warn";
}

export default async function RecommendationExplanationPage({
  params
}: {
  params: { symbol: string };
}) {
  const symbol = decodeURIComponent(params.symbol).toUpperCase();
  const model = "sector_rotation_adx_1m3m";
  const modelLabel = strategyLabel(model);
  const result = await safeApiGet<Payload>(`/recommendations/${encodeURIComponent(symbol)}/explanation?recommendation_type=${encodeURIComponent(model)}`);
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Recommendation Explanation" subtitle={`${symbol} decision snapshot.`} />
        <ErrorState message={result.error} />
      </>
    );
  }
  const data = result.data;
  const snapshot = data.feature_snapshot || {};
  const hasSnapshot = Object.keys(snapshot).length > 0;
  const finalScore = snapshot.final_score ?? data.score;

  return (
    <>
      <PageHeader title={`${symbol} Explanation`} subtitle={`${modelLabel} decision snapshot from ${data.business_date || "n/a"}.`} />
      <div className="page-actions">
        <Link className="secondary-button" href="/recommendations">Back to Recommendations</Link>
      </div>

      {!hasSnapshot ? <EmptyState message="No explanation snapshot exists for this symbol yet." /> : null}

      <section className="panel explanation-hero">
        <div>
          <div className="eyebrow">Decision</div>
          <h2>{data.symbol}</h2>
          <p className="subtitle">
            {data.sector || "Unknown sector"} · {modelLabel} · source {data.source}
          </p>
        </div>
        <div className="decision-badges">
          <span className="status-pill ok">Recommended</span>
          <span className="status-pill warn">Paper candidate</span>
        </div>
      </section>

      <div className="grid cols-4">
        <MetricCard label="Rank" value={String(data.rank ?? "n/a")} />
        <MetricCard label="Final Score" value={displayNumber(finalScore)} />
        <MetricCard label="Trend Strength" value={displayNumber(snapshot.adx_14)} />
        <MetricCard label="Sector Position" value={String(snapshot.sector_rank_3m ?? snapshot.sector_rank_used ?? "n/a")} />
      </div>

      <section className="panel factor-panel">
        <div className="section-head">
          <h2>Factor Breakdown</h2>
        </div>
        <div className="factor-grid">
          <div className="factor-row">
            <div>
              <strong>Long-Term Trend Gap</strong>
            </div>
            <span className={toneForExtension(snapshot.ema200_extension)}>{pct(snapshot.ema200_extension)}</span>
          </div>
          <div className="factor-row">
            <div>
              <strong>Recent Momentum</strong>
            </div>
            <span className={toneForMomentum(snapshot.prior_20d_return)}>{pct(snapshot.prior_20d_return)}</span>
          </div>
          <div className="factor-row">
            <div>
              <strong>Long-Term Average</strong>
            </div>
            <span>{displayNumber(snapshot.ema_200)}</span>
          </div>
          <div className="factor-row">
            <div>
              <strong>Sector</strong>
            </div>
            <span>{data.sector || "n/a"}</span>
          </div>
        </div>
      </section>

    </>
  );
}
