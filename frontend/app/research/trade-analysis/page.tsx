"use client";

import { useEffect, useState } from "react";
import { Download, Play } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { API_BASE, apiGet, apiPost, money, pct } from "@/lib/api";
import { strategyLabel } from "@/lib/strategyNames";

type Summary = {
  ending_value?: number;
  total_return?: number;
  cagr?: number;
  max_drawdown?: number;
  win_rate?: number;
  total_trades?: number;
  open_positions?: number;
  open_unrealized_pnl?: number;
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

type ModelStatus = {
  model: string;
  source: string;
  recommendation_rows: number;
  recommendation_dates: number;
  first_recommendation_date?: string | null;
  last_recommendation_date?: string | null;
  is_empty: boolean;
};

type FinancialYearReturn = {
  financial_year: string;
  start_date: string;
  end_date: string;
  start_equity: number;
  end_equity: number;
  return_pct: number | null;
  trading_days: number;
  closed_trades?: number;
  winners?: number;
  losers?: number;
  win_rate?: number | null;
};

const artifactLinks = [
  { key: "trades_csv", label: "CSV", artifact: "trades.csv" },
  { key: "open_positions_csv", label: "Open positions CSV", artifact: "open_positions.csv" },
  { key: "summary_md", label: "Markdown summary", artifact: "summary.md" },
  { key: "financial_year_returns_csv", label: "FY returns CSV", artifact: "financial_year_returns.csv" }
];

export default function TradeAnalysisPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const recommendationModel = "sector_rotation_adx_1m3m";
  const strategy = "SECTOR_ROTATION_ADX_ROLLING10";
  const [initialCapital, setInitialCapital] = useState("1000000");
  const [chargeModel, setChargeModel] = useState("ZERODHA_DEFAULT");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TradeAnalysisResponse | null>(null);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadStatus() {
      try {
        const data = await apiGet<ModelStatus>(`/research/trade-analysis/model-status?model=${encodeURIComponent(recommendationModel)}`);
        if (active) {
          setModelStatus(data);
          setStatusError(null);
          if (!startDate) {
            setStartDate(data.first_recommendation_date || "2022-05-25");
          }
          if (!endDate) {
            setEndDate(data.last_recommendation_date || "");
          }
        }
      } catch (caught) {
        if (active) {
          setStatusError(caught instanceof Error ? caught.message : "Unable to load model status");
          if (!startDate) {
            setStartDate("2022-05-25");
          }
          if (!endDate) {
            setEndDate("2026-06-11");
          }
        }
      }
    }
    void loadStatus();
    return () => {
      active = false;
    };
  }, []);

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
      <PageHeader title="Trade Analysis" subtitle="On-demand historical reconstruction for SectorEdge 10." />

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
            <input value="SectorEdge 10" readOnly />
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
          <button className="primary-button" type="button" onClick={runAnalysis} disabled={loading} style={{ justifySelf: "start", padding: "10px 14px", minHeight: 40, fontSize: 14 }}>
            <Play size={16} aria-hidden="true" />
            <span>{loading ? "Generating" : "Generate Trade Analysis"}</span>
          </button>
        </div>
        {statusError ? (
          <div style={{ marginTop: 16 }}>
            <ErrorState message={statusError} />
          </div>
        ) : null}
        {modelStatus?.is_empty ? (
          <div className="empty-state" style={{ marginTop: 16, borderColor: "var(--warning-border, #d6a100)", background: "rgba(214, 161, 0, 0.08)" }}>
            <div className="empty-state-title">Candidate model has no rows yet</div>
            <div className="empty-state-body">
              {recommendationModel} in {modelStatus.source} is empty. Populate it before running trade analysis, or the report will fall back to the older source and may not reflect the candidate model.
            </div>
            <div className="empty-state-body" style={{ marginTop: 6 }}>
              Last checked: {modelStatus.recommendation_rows} rows, {modelStatus.recommendation_dates} dates.
            </div>
          </div>
        ) : null}
      </section>

      {loading ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Generating</h2>
          <p className="subtitle">Reconstructing entries, skipped candidates, trades, FY returns, and report files. A full 2022-2026 run usually takes about a minute.</p>
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
            </div>
          </div>
          <div className="subtitle" style={{ marginTop: 8 }}>
            Range used: {startDate || "n/a"} to {endDate || "n/a"}
          </div>
          {result.inputs?.recommendation_universe_source ? (
            <div className="subtitle" style={{ marginTop: 8 }}>
              Universe source: {String(result.inputs.recommendation_universe_source)}
            </div>
          ) : null}
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
                <tr><td>Closed trades</td><td>{result.summary.total_trades ?? "n/a"}</td></tr>
                <tr><td>Open positions</td><td>{result.summary.open_positions ?? 0}</td></tr>
                <tr><td>Open unrealized PnL</td><td>{money(result.summary.open_unrealized_pnl)}</td></tr>
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
                    <th>Trading Days</th>
                    <th>Closed Trades</th>
                    <th>Win Rate</th>
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
                      <td>{row.closed_trades ?? 0}</td>
                      <td>{pct(row.win_rate)}</td>
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
