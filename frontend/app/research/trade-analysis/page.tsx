"use client";

import { useState } from "react";
import { Download, Play } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { API_BASE, apiPost, money, pct } from "@/lib/api";
import { strategyLabel } from "@/lib/strategyNames";

type Summary = {
  ending_value?: number;
  total_return?: number;
  cagr?: number;
  max_drawdown?: number;
  win_rate?: number;
  total_trades?: number;
  total_charges?: number;
  financial_year_returns?: FinancialYearReturn[];
  recommendation_model?: string;
};

type TradeAnalysisResponse = {
  report_id: string;
  status: string;
  cache_hit?: boolean;
  summary: Summary;
  artifacts: Record<string, string>;
  inputs?: Record<string, unknown>;
};

type FinancialYearReturn = {
  financial_year: string;
  start_date: string;
  end_date: string;
  start_equity: number;
  end_equity: number;
  return_pct: number | null;
  trading_days: number;
};

const artifactLinks = [
  { key: "trades_csv", label: "CSV", artifact: "trades.csv" },
  { key: "summary_md", label: "Markdown summary", artifact: "summary.md" },
  { key: "financial_year_returns_csv", label: "FY returns CSV", artifact: "financial_year_returns.csv" }
];

export default function TradeAnalysisPage() {
  const [startDate, setStartDate] = useState("2022-05-25");
  const [endDate, setEndDate] = useState("2026-06-11");
  const recommendationModel = "sector_rotation_adx_1m3m";
  const strategy = "SECTOR_ROTATION_ADX_ROLLING10";
  const [initialCapital, setInitialCapital] = useState("1000000");
  const [chargeModel, setChargeModel] = useState("ZERODHA_DEFAULT");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TradeAnalysisResponse | null>(null);

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload = {
        start_date: startDate,
        end_date: endDate,
        recommendation_model: recommendationModel,
        strategy,
        initial_capital: Number(initialCapital),
        charge_model: chargeModel
      };
      const response = await apiPost<TradeAnalysisResponse>("/research/trade-analysis/run", payload);
      setResult(response);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Trade analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader title="Trade Analysis" subtitle="On-demand historical reconstruction for Sector Rotation ADX Rolling 10." />

      <section className="panel">
        <div className="form-grid">
          <label>
            <span>Date range start</span>
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label>
            <span>Date range end</span>
            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </label>
          <label>
            <span>Strategy</span>
            <input value="Sector Rotation ADX Rolling 10" readOnly />
          </label>
          <label>
            <span>Capital</span>
            <input inputMode="numeric" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} />
          </label>
          <label>
            <span>Charges</span>
            <select value={chargeModel} onChange={(event) => setChargeModel(event.target.value)}>
              <option value="ZERODHA_DEFAULT">Zerodha default</option>
              <option value="CUSTOM" disabled>Custom</option>
            </select>
          </label>
          <button className="primary-button" type="button" onClick={runAnalysis} disabled={loading}>
            <Play size={16} aria-hidden="true" />
            <span>{loading ? "Generating" : "Generate Trade Analysis"}</span>
          </button>
        </div>
      </section>

      {loading ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Generating</h2>
          <p className="subtitle">Reconstructing 10:30 entries, VWAP skips, trades, FY returns, and report files. A full 2022-2026 run usually takes about a minute.</p>
        </section>
      ) : null}

      {error ? <div style={{ marginTop: 16 }}><ErrorState message={error} /></div> : null}

      {!loading && !error && !result ? (
        <div style={{ marginTop: 16 }}>
          <EmptyState message="Run an analysis to generate trade ledger and summary artifacts." />
        </div>
      ) : null}

      {result ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <div className="data-status-head">
            <div>
              <h2>Results</h2>
              <p className="subtitle">
                {strategyLabel(result.summary.recommendation_model || recommendationModel)}
              </p>
            </div>
            <span className="status-pill ok">{result.cache_hit ? "cached" : result.status}</span>
          </div>
          <div className="grid cols-4" style={{ marginTop: 16 }}>
            <div>
              <div className="metric-label">Total Return</div>
              <div className="metric-value">{pct(result.summary.total_return)}</div>
            </div>
            <div>
              <div className="metric-label">CAGR</div>
              <div className="metric-value">{pct(result.summary.cagr)}</div>
            </div>
            <div>
              <div className="metric-label">Max Drawdown</div>
              <div className="metric-value">{pct(result.summary.max_drawdown)}</div>
            </div>
            <div>
              <div className="metric-label">Win Rate</div>
              <div className="metric-value">{pct(result.summary.win_rate)}</div>
            </div>
          </div>
          <div className="grid cols-2" style={{ marginTop: 16 }}>
            <table>
              <tbody>
                <tr><td>Total trades</td><td>{result.summary.total_trades ?? "n/a"}</td></tr>
                <tr><td>Total charges</td><td>{money(result.summary.total_charges)}</td></tr>
                <tr><td>Ending value</td><td>{money(result.summary.ending_value)}</td></tr>
              </tbody>
            </table>
            <div className="download-row">
              {artifactLinks.map((link) => (
                <a
                  key={link.key}
                  className="download-link"
                  href={`${API_BASE}/research/trade-analysis/${encodeURIComponent(result.report_id)}/artifact/${link.artifact}`}
                >
                  <Download size={16} aria-hidden="true" />
                  <span>{link.label}</span>
                </a>
              ))}
            </div>
          </div>
          <div style={{ marginTop: 20 }}>
            <h3>Financial Year Returns</h3>
            {result.summary.financial_year_returns?.length ? (
              <table>
                <thead>
                  <tr>
                    <th>FY</th>
                    <th>Period</th>
                    <th>Start Equity</th>
                    <th>End Equity</th>
                    <th>Return</th>
                    <th>Days</th>
                  </tr>
                </thead>
                <tbody>
                  {result.summary.financial_year_returns.map((row) => (
                    <tr key={row.financial_year}>
                      <td>{row.financial_year}</td>
                      <td>{row.start_date} to {row.end_date}</td>
                      <td>{money(row.start_equity)}</td>
                      <td>{money(row.end_equity)}</td>
                      <td>{pct(row.return_pct)}</td>
                      <td>{row.trading_days}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="subtitle">FY-wise returns will appear after a report is generated.</p>
            )}
          </div>
        </section>
      ) : null}
    </>
  );
}
