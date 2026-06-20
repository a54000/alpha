"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, Search, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { apiGet, money, pct, relativePoints } from "@/lib/api";

type SymbolMatch = {
  symbol: string;
  sector?: string | null;
  latest_date?: string | null;
};

type StockDashboard = {
  symbol: string;
  latest_bar: Record<string, unknown>;
  latest_features: Record<string, unknown>;
  latest_recommendation: Record<string, unknown>;
  recent_bars: Array<{ date: string; close?: number | null; volume?: number | null }>;
  summary: Record<string, unknown>;
};

type Recommendation = {
  symbol: string;
  rank: number;
  score?: number;
  sector?: string;
};

type RecommendationsPayload = {
  date: string | null;
  recommendations: Recommendation[];
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
  const points = useMemo(() => {
    const closes = bars.map((bar) => numberValue(bar.close)).filter((value): value is number => value !== null);
    if (closes.length < 2) return "";
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const width = 520;
    const height = 150;
    const margin = { left: 46, right: 12, top: 12, bottom: 24 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const range = max - min || 1;
    return closes
      .map((close, index) => {
        const x = margin.left + (index / (closes.length - 1)) * plotWidth;
        const y = margin.top + plotHeight - ((close - min) / range) * plotHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [bars]);

  if (!points) return <EmptyState message="Not enough recent bars to draw the price line." />;
  const closes = bars.map((bar) => numberValue(bar.close)).filter((value): value is number => value !== null);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const width = 520;
  const height = 150;
  const margin = { left: 46, right: 12, top: 12, bottom: 24 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
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

export default function StockAnalysisPage() {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<SymbolMatch[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [data, setData] = useState<StockDashboard | null>(null);
  const [recommended, setRecommended] = useState<RecommendationsPayload | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    apiGet<RecommendationsPayload>("/recommendations/latest?model=sector_rotation_adx_1m3m&limit=10")
      .then((payload) => {
        if (active) setRecommended(payload);
      })
      .catch(() => {
        if (active) setRecommended({ date: null, recommendations: [] });
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const term = query.trim().toUpperCase();
    setSearchError(null);
    if (term.length < 3) {
      setMatches([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        setSearching(true);
        const response = await fetch(`/api/stock-analysis/search?q=${encodeURIComponent(term)}&limit=25`, {
          signal: controller.signal,
          cache: "no-store"
        });
        if (!response.ok) throw new Error(`Search failed: ${response.status}`);
        const payload = (await response.json()) as { symbols: SymbolMatch[] };
        setMatches(payload.symbols || []);
      } catch (error) {
        if (!controller.signal.aborted) setSearchError(error instanceof Error ? error.message : "Symbol search failed");
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  async function loadDashboard(symbol: string) {
    const normalized = symbol.trim().toUpperCase();
    if (!normalized) return;
    setSelectedSymbol(normalized);
    setLoading(true);
    setDashboardError(null);
    setData(null);
    try {
      const payload = await apiGet<StockDashboard>(`/stock-analysis/${encodeURIComponent(normalized)}`);
      setData(payload);
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : "Stock dashboard failed");
    } finally {
      setLoading(false);
    }
  }

  const summary = data?.summary || {};
  const term = query.trim();
  const canSearch = term.length >= 3;

  return (
    <>
      <PageHeader
        title="Stock Analysis"
        subtitle="Search any stock to see its latest price context, SectorEdge 10 status, and recent recommendation history."
      />

      <section className="panel stock-search-panel">
        <div className="stock-search-layout">
          <div className="stock-search-primary">
            <div className="stock-search-title">
              <Search size={18} aria-hidden="true" />
              <div>
                <h2>Find a Stock</h2>
                <p className="subtitle">Type at least 3 characters, then choose from the matching symbols.</p>
              </div>
            </div>
            <div className="stock-input-wrap">
              <Search size={18} aria-hidden="true" />
              <input
                aria-label="Stock symbol search"
                value={query}
                onChange={(event) => setQuery(event.target.value.toUpperCase())}
                placeholder="Search symbol, e.g. TAT"
                list="stock-symbols"
              />
            </div>
            <datalist id="stock-symbols">
              {matches.map((match) => (
                <option key={match.symbol} value={match.symbol}>{match.sector || ""}</option>
              ))}
            </datalist>
            {term.length > 0 && !canSearch ? <p className="helper-text">Enter at least 3 characters.</p> : null}
            {searching ? <p className="helper-text">Searching...</p> : null}
            {searchError ? <div style={{ marginTop: 12 }}><ErrorState message={searchError} /></div> : null}
            {canSearch && !searching && !matches.length && !searchError ? <p className="helper-text">No matching symbols found.</p> : null}
            {matches.length ? (
              <div className="stock-match-list">
                {matches.slice(0, 10).map((match) => (
                  <button
                    className={selectedSymbol === match.symbol ? "active" : ""}
                    key={match.symbol}
                    type="button"
                    onClick={() => { setQuery(match.symbol); loadDashboard(match.symbol); }}
                  >
                    <span>
                      <strong>{match.symbol}</strong>
                      <small>{match.sector || "Sector n/a"}</small>
                    </span>
                    <em>{match.latest_date || "n/a"}</em>
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <div className="stock-recommendation-panel">
            <div className="stock-search-title">
              <Sparkles size={18} aria-hidden="true" />
              <div>
                <h2>Current Shortlist</h2>
                <p className="subtitle">{recommended?.date ? `Latest recommendations from ${recommended.date}.` : "Latest recommendations will appear here when available."}</p>
              </div>
            </div>
            {recommended?.recommendations?.length ? (
              <div className="stock-match-list compact">
                {recommended.recommendations.map((item) => (
                  <button
                    className={selectedSymbol === item.symbol ? "active" : ""}
                    key={`${item.rank}-${item.symbol}`}
                    type="button"
                    onClick={() => { setQuery(item.symbol); loadDashboard(item.symbol); }}
                  >
                    <span>
                      <strong>{item.symbol}</strong>
                      <small>{item.sector || "Sector n/a"}</small>
                    </span>
                    <em>#{item.rank}</em>
                  </button>
                ))}
              </div>
            ) : (
              <p className="helper-text">No current shortlist is available.</p>
            )}
          </div>
        </div>
      </section>

      {loading ? <div style={{ marginTop: 16 }}><EmptyState message={`Loading ${selectedSymbol || "stock"} analysis...`} /></div> : null}
      {dashboardError ? <div style={{ marginTop: 16 }}><ErrorState message={dashboardError} /></div> : null}
      {!data && !dashboardError && !loading ? <div style={{ marginTop: 16 }}><EmptyState message="Search for a symbol or choose a current shortlist item to open its stock view." /></div> : null}

      {data ? (
        <>
          <section className="panel stock-hero">
            <div>
              <div className="eyebrow">Stock View</div>
              <h2>{data.symbol}</h2>
              <p className="subtitle">{String(summary.sector || "Sector n/a")} · latest data {String(summary.latest_date || "n/a")}</p>
            </div>
            <div className="decision-badges">
              <span className={summary.above_ema200 ? "status-pill ok" : "status-pill warn"}>
                {summary.above_ema200 ? "Above long-term trend" : "Below long-term trend"}
              </span>
              {summary.last_recommended_date ? <span className="status-pill ok">Recommended before</span> : <span className="status-pill">No recent recommendation</span>}
            </div>
          </section>

          <div className="grid cols-4">
            <section className="panel"><div className="metric-label">Close</div><div className="metric-value">{money(summary.close)}</div></section>
            <section className="panel"><div className="metric-label">Trend Strength</div><div className="metric-value">{formatNumber(summary.adx_14)}</div></section>
            <section className="panel"><div className="metric-label">Relative Strength vs Nifty</div><div className="metric-value">{relativePoints(summary.rs_score_vs_nifty50_66d)}</div></section>
            <section className="panel"><div className="metric-label">Recent Return</div><div className="metric-value">{pct(summary.prior_20d_return)}</div></section>
          </div>

          <div className="grid cols-2" style={{ marginTop: 16 }}>
            <section className="panel">
              <div className="section-head">
                <div>
                  <h2>Recent Price</h2>
                  <p className="subtitle">Last 60 daily closes.</p>
                </div>
                <BarChart3 size={18} aria-hidden="true" />
              </div>
              <MiniCloseChart bars={data.recent_bars} />
            </section>
            <section className="panel">
              <h2>Recommendation Context</h2>
              <table>
                <tbody>
                  <tr><td>Last recommendation date</td><td>{String(summary.last_recommended_date || "n/a")}</td></tr>
                  <tr><td>Last rank</td><td>{String(summary.last_rank || "n/a")}</td></tr>
                  <tr><td>Last score</td><td>{formatNumber(summary.last_score)}</td></tr>
                  <tr><td>Sector position</td><td>{String(summary.sector_rank_3m || "n/a")}</td></tr>
                  <tr><td>Long-term average</td><td>{money(summary.ema_200)}</td></tr>
                </tbody>
              </table>
            </section>
          </div>

          <section className="panel table-wrap" style={{ marginTop: 16 }}>
            <h2>Recent Daily Bars</h2>
            <table>
              <thead>
                <tr><th>Date</th><th>Close</th><th>Volume</th></tr>
              </thead>
              <tbody>
                {data.recent_bars.slice(-10).reverse().map((bar) => (
                  <tr key={bar.date}>
                    <td>{bar.date}</td>
                    <td>{money(bar.close)}</td>
                    <td>{formatNumber(bar.volume, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </>
  );
}
