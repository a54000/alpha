import { CheckCircle2, CircleAlert, XCircle } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/StatePanel";
import { pct, safeApiGet } from "@/lib/api";

type Payload = {
  as_of: string | null;
  summary?: {
    market_lens?: {
      lens?: string;
      raw_lens?: string;
      colour?: string;
      benchmark_used?: string;
      benchmark_note?: string;
      instruction?: string;
      long_bias?: number | null;
      short_bias?: number | null;
      bias_modifiers?: string[];
      persistence?: {
        pending?: boolean;
        pending_lens?: string | null;
        pending_days?: number;
        days_needed?: number;
        history?: Array<{
          date?: string;
          raw?: string;
          status?: string;
          confirmed?: string;
        }>;
      };
      signals?: {
        nifty_close_date?: string | null;
        nifty_close?: number | null;
        nifty_ema_50?: number | null;
        nifty_ema_200?: number | null;
        nifty_above_50ema?: boolean;
        nifty_above_200ema?: boolean;
        breadth_50ema?: number | null;
        nifty_3m_return?: number | null;
        atr_pct?: number | null;
      };
    };
  };
};

function number(value: unknown, digits = 2) {
  const item = Number(value);
  if (!Number.isFinite(item)) return "n/a";
  return item.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function valueTone(value: unknown, goodAt = 0) {
  const item = Number(value);
  if (!Number.isFinite(item)) return "neutral";
  if (item > goodAt) return "ok";
  if (item < goodAt) return "bad";
  return "neutral";
}

function pctWhole(value: unknown) {
  const item = Number(value);
  if (!Number.isFinite(item)) return "n/a";
  return `${Math.round(item * 100)}%`;
}

function trendTone(lens?: string) {
  const item = String(lens || "").toLowerCase();
  if (item === "bullish") return "ok";
  if (item === "selective") return "info";
  if (item === "cautious") return "warn";
  if (item === "bearish") return "bad";
  return "";
}

function dateLabel(value?: string) {
  if (!value) return "n/a";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function changePoints(history?: Array<{ date?: string; confirmed?: string }>) {
  const points: Array<{ date?: string; confirmed?: string }> = [];
  let lastConfirmed = "";
  for (const item of history || []) {
    const confirmed = String(item.confirmed || "").trim();
    if (!confirmed) continue;
    if (confirmed !== lastConfirmed) {
      points.push({ date: item.date, confirmed });
      lastConfirmed = confirmed;
    }
  }
  return points.slice(-3);
}

function CheckRow({ label, ok }: { label: string; ok?: boolean }) {
  const Icon = ok ? CheckCircle2 : XCircle;
  return (
    <span className={`lens-check ${ok ? "ok" : "bad"}`}>
      <Icon size={18} aria-hidden="true" />
      {label}
    </span>
  );
}

export default async function MarketLensPage() {
  const result = await safeApiGet<Payload>("/market-breadth", { next: { revalidate: 900 } });
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Market Lens" subtitle="Top-down market condition before sector and stock selection." />
        <ErrorState message={result.error} />
      </>
    );
  }

  const data = result.data;
  const lens = data.summary?.market_lens || {};
  const signals = lens.signals || {};
  const lensClass = String(lens.colour || "cyan").toLowerCase();
  const longBias = Number(lens.long_bias ?? 0);
  const longWidth = Number.isFinite(longBias) ? Math.max(0, Math.min(100, longBias * 100)) : 0;
  const trend = changePoints(lens.persistence?.history);
  const currentLens = String(lens.lens || lens.raw_lens || "unknown").trim().toLowerCase();
  const todayChipLabel = `Today \u00b7 still ${currentLens}`;

  return (
    <>
      <PageHeader
        title="Market Lens"
        subtitle="The first layer of the top-down process: decide whether the market favours longs, shorts, or selectivity."
        actions={
          <div className="refresh-badge">
            <span>Refresh Date</span>
            <strong>{data.as_of || "n/a"}</strong>
          </div>
        }
      />

      <section className={`market-lens-card lens-${lensClass}`}>
        <div className="market-lens-head">
          <span>Market Lens</span>
          <h2 className={`lens-title ${lensClass}`}>{String(lens.lens || "Unknown").toUpperCase()}</h2>
          {trend.length ? (
            <div className="lens-trend-strip" aria-label="Market Lens trend">
              <div className="lens-trend-header">
                <span className="fine-print lens-trend-label">Recent changes</span>
              </div>
              <div className="lens-trend-row">
                {trend.map((point, index) => (
                  <span key={`${point.date}-${point.confirmed}-${index}`} className="lens-trend-step">
                    <span className={`state-chip ${trendTone(point.confirmed)} ${index === trend.length - 1 ? "current" : ""}`}>
                      {dateLabel(point.date)}: {point.confirmed || "Unknown"}
                    </span>
                  </span>
                ))}
                <span className="lens-trend-step">
                  <span className="state-chip ghost current">
                    {todayChipLabel}
                  </span>
                </span>
              </div>
            </div>
          ) : (
            <p className="fine-print" style={{ marginTop: 12 }}>
              Trend history unavailable.
            </p>
          )}
        </div>

        <div className="market-lens-nifty">
          <div>
            <strong>NIFTY 50</strong>
            <div className="nifty-close-value">{number(signals.nifty_close, 0)}</div>
            <p className="fine-print">Close date: {signals.nifty_close_date || data.as_of || "n/a"}</p>
          </div>
          <div>
            <div className="lens-check-row">
              <CheckRow label="Above 200 EMA" ok={signals.nifty_above_200ema} />
              <CheckRow label="Above 50 EMA" ok={signals.nifty_above_50ema} />
            </div>
            <p className="fine-print">
              50 EMA {number(signals.nifty_ema_50)} / 200 EMA {number(signals.nifty_ema_200)}
            </p>
          </div>
        </div>

        <div className="market-lens-grid compact">
          <div className="lens-stat">
            <span>Breadth (% above 50 EMA)</span>
            <strong className={`tone-${valueTone(signals.breadth_50ema, 0.5)}`}>{pct(signals.breadth_50ema)}</strong>
          </div>

          <div className="lens-stat">
            <span>3M Momentum</span>
            <strong className={`tone-${valueTone(signals.nifty_3m_return, 0)}`}>{pct(signals.nifty_3m_return)}</strong>
          </div>

          <div className="lens-stat">
            <span>Long / Short Bias</span>
            <strong>{pctWhole(lens.long_bias)} / {pctWhole(lens.short_bias)}</strong>
            <div className="bias-bar" aria-label={`Long bias ${pctWhole(lens.long_bias)}, short bias ${pctWhole(lens.short_bias)}`}>
              <span className="long" style={{ width: `${longWidth}%` }} />
              <span className="short" style={{ width: `${100 - longWidth}%` }} />
            </div>
          </div>
        </div>

        <div className="market-lens-instruction">
          <strong>Instruction</strong>
          <p>{lens.instruction || "Market instruction is unavailable."}</p>
          {lens.persistence?.pending ? (
            <p className="fine-print">
              Raw lens is {lens.raw_lens || lens.persistence.pending_lens}; waiting {lens.persistence.days_needed} more session(s) before confirming.
            </p>
          ) : null}
          {lens.bias_modifiers?.length ? (
            <p className="fine-print">Bias modifiers: {lens.bias_modifiers.join("; ")}</p>
          ) : null}
          {lens.benchmark_note ? (
            <p className="fine-print">Benchmark: {lens.benchmark_used || "n/a"}. {lens.benchmark_note}</p>
          ) : null}
        </div>
      </section>

      <details className="market-lens-help">
        <summary><CircleAlert size={18} aria-hidden="true" /> How to use this</summary>
        <p>Use Market Lens before sector rotation. It sets the broad long/short posture, while Layer 2 decides which sectors deserve attention.</p>
      </details>
    </>
  );
}
