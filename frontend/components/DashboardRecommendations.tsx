"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { apiGet, money, pct, relativePoints } from "@/lib/api";
import { EmptyState, ErrorState } from "@/components/StatePanel";

type Rec = {
  rank: number;
  symbol: string;
  score?: number;
  sector?: string;
  adx_points?: number;
  sector_points?: number;
};

type StockDashboard = {
  symbol: string;
  recent_bars: Array<{ date: string; close?: number | null; volume?: number | null }>;
  summary: Record<string, unknown>;
};

function numberValue(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatNumber(value: unknown, digits = 2): string {
  const parsed = numberValue(value);
  if (parsed === null) return "n/a";
  return parsed.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function MiniCloseChart({ bars }: { bars: StockDashboard["recent_bars"] }) {
  const closes = bars.map((bar) => numberValue(bar.close)).filter((value): value is number => value !== null);
  if (closes.length < 2) return <EmptyState message="Not enough recent bars to draw the price line." />;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const width = 520;
  const height = 150;
  const margin = { left: 46, right: 12, top: 12, bottom: 24 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const range = max - min || 1;
  const points = closes
    .map((close, index) => {
      const x = margin.left + (index / (closes.length - 1)) * plotWidth;
      const y = margin.top + plotHeight - ((close - min) / range) * plotHeight;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const yTicks = [max, (min + max) / 2, min];
  const xLabels = [bars[0]?.date, bars[Math.floor((bars.length - 1) / 2)]?.date, bars[bars.length - 1]?.date];
  return (
    <svg className="stock-chart" viewBox="0 0 520 150" role="img" aria-label="Recent close price line">
      {yTicks.map((tick, index) => {
        const y = margin.top + (index / 2) * plotHeight;
        return (
          <g key={tick.toFixed(2)}>
            <line x1={margin.left} x2={width - margin.right} y1={y} y2={y} className="chart-gridline" />
            <text x={margin.left - 8} y={y + 4} className="chart-axis-label" textAnchor="end">{formatNumber(tick, 0)}</text>
          </g>
        );
      })}
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="3" />
      {xLabels.map((label, index) => (
        <text key={`${label}-${index}`} x={margin.left + (index / 2) * plotWidth} y={height - 5} className="chart-axis-label" textAnchor={index === 0 ? "start" : index === 2 ? "end" : "middle"}>
          {String(label || "n/a")}
        </text>
      ))}
    </svg>
  );
}

export function DashboardRecommendations({ items }: { items: Rec[] }) {
  const [selected, setSelected] = useState<Rec | null>(null);
  const [data, setData] = useState<StockDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function openStock(item: Rec) {
    setSelected(item);
    setData(null);
    setError(null);
    setLoading(true);
    try {
      const payload = await apiGet<StockDashboard>(`/stock-analysis/${encodeURIComponent(item.symbol)}`);
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stock analysis failed");
    } finally {
      setLoading(false);
    }
  }

  function closeModal() {
    setSelected(null);
    setData(null);
    setError(null);
    setLoading(false);
  }

  const summary = data?.summary || {};

  return (
    <>
      <div className="action-grid">
        {items.length ? items.map((item) => (
          <button className="action-card action-card-button" type="button" onClick={() => openStock(item)} key={`${item.rank}-${item.symbol}`}>
            <span>Open analysis</span>
            <strong>{item.symbol}</strong>
            <small>{item.sector || "Sector n/a"}{item.adx_points !== undefined ? `, trend score ${item.adx_points}` : ""}</small>
          </button>
        )) : (
          <div className="action-card">
            <span>Hold</span>
            <strong>No action queued</strong>
            <small>Open Recommendations for the full ranked list.</small>
          </div>
        )}
      </div>

      {selected ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label={`${selected.symbol} stock analysis`}>
          <section className="panel stock-modal">
            <button className="modal-close" type="button" onClick={closeModal} aria-label="Close stock analysis">
              <X size={18} aria-hidden="true" />
            </button>
            <div className="stock-hero modal-stock-hero">
              <div>
                <div className="eyebrow">Stock Analysis</div>
                <h2>{selected.symbol}</h2>
                <p className="subtitle">{String(summary.sector || selected.sector || "Sector n/a")} · latest data {String(summary.latest_date || "loading")}</p>
              </div>
              <div className="decision-badges">
                {summary.above_ema200 !== undefined ? (
                  <span className={summary.above_ema200 ? "status-pill ok" : "status-pill warn"}>
                    {summary.above_ema200 ? "Above long-term trend" : "Below long-term trend"}
                  </span>
                ) : null}
                <span className="status-pill ok">Current shortlist</span>
              </div>
            </div>

            {loading ? <EmptyState message={`Loading ${selected.symbol} analysis...`} /> : null}
            {error ? <ErrorState message={error} /> : null}
            {data ? (
              <>
                <div className="grid cols-4">
                  <section className="panel"><div className="metric-label">Close</div><div className="metric-value">{money(summary.close)}</div></section>
                  <section className="panel"><div className="metric-label">Trend Strength</div><div className="metric-value">{formatNumber(summary.adx_14)}</div></section>
                  <section className="panel"><div className="metric-label">Relative Strength vs Nifty</div><div className="metric-value">{relativePoints(summary.rs_score_vs_nifty50_66d)}</div></section>
                  <section className="panel"><div className="metric-label">Recent Return</div><div className="metric-value">{pct(summary.prior_20d_return)}</div></section>
                </div>
                <div className="grid cols-2 modal-stock-grid">
                  <section className="panel">
                    <h2>Recent Price</h2>
                    <MiniCloseChart bars={data.recent_bars || []} />
                  </section>
                  <section className="panel">
                    <h2>Recommendation Context</h2>
                    <table>
                      <tbody>
                        <tr><td>Last recommendation date</td><td>{String(summary.last_recommended_date || "n/a")}</td></tr>
                        <tr><td>Last rank</td><td>{String(summary.last_rank || selected.rank || "n/a")}</td></tr>
                        <tr><td>Last score</td><td>{formatNumber(summary.last_score ?? selected.score)}</td></tr>
                        <tr><td>Sector position</td><td>{String(summary.sector_rank_3m || "n/a")}</td></tr>
                        <tr><td>Long-term average</td><td>{money(summary.ema_200)}</td></tr>
                      </tbody>
                    </table>
                  </section>
                </div>
              </>
            ) : null}
          </section>
        </div>
      ) : null}
    </>
  );
}
