import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { API_BASE, money, pct } from "@/lib/api";
import { strategyLabel } from "@/lib/strategyNames";
import styles from "./rolling-portfolio.module.css";

export const dynamic = "force-dynamic";

type Recommendation = {
  rank: number;
  symbol: string;
  sector?: string;
  score?: number;
  ema200_extension?: number;
  prior_20d_return?: number;
};

type WeeklyLog = {
  week_number: number;
  signal_date: string;
  entry_date?: string;
  recommendations: Recommendation[];
  entered: { symbol: string; entry_price: number; entry_value: number }[];
  skipped: {
    symbol: string;
    reason: string;
    entry_price?: number;
    reference_vwap?: number;
    entry_vs_reference_vwap_pct?: number;
  }[];
};

type Position = {
  symbol: string;
  sector?: string;
  entry_date: string;
  entry_value: number;
  planned_exit_date: string;
  rank: number;
  market_value?: number;
  unrealized_pnl?: number;
};

type ClosedTrade = {
  trade_id: number;
  symbol: string;
  sector?: string;
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  holding_days?: number;
  entry_value: number;
  exit_value: number;
  net_pnl: number;
  net_return_pct: number;
  charges: number;
  exit_reason?: string;
  status?: string;
};

type FinancialYearReturn = {
  financial_year: string;
  start_date: string;
  end_date: string;
  start_equity: number;
  end_equity: number;
  return_pct?: number | null;
};

type SimulationResponse = {
  status: string;
  message?: string;
  parameters: {
    requested_start_date?: string;
    effective_start_date?: string;
    weeks: number;
    initial_capital: number;
    recommendation_model?: string;
  };
  summary: {
    mark_date?: string;
    cash?: number;
    market_value?: number;
    equity?: number;
    cash_pct?: number;
    open_positions?: number;
    closed_trades?: number;
    portfolio_size?: number;
    max_candidate_rank?: number;
    holding_period?: number;
    recommendation_model?: string;
    entry_time?: string;
    vwap_skip_threshold?: number | null;
  };
  weekly_log: WeeklyLog[];
  positions: Position[];
  trades: ClosedTrade[];
  financial_year_returns?: FinancialYearReturn[];
};

type DefaultsResponse = {
  default_start_date?: string | null;
  earliest_recommendation_date?: string | null;
  latest_recommendation_date?: string | null;
  recommendation_dates?: number;
  recommendation_rows?: number;
  source?: string;
};

type PageProps = {
  searchParams?: {
    start_date?: string;
    weeks?: string;
    initial_capital?: string;
    run?: string;
  };
};

function clampWeeks(value: string | undefined): number {
  const parsed = Number(value || "1");
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(260, Math.max(1, Math.trunc(parsed)));
}

function positiveCapital(value: string | undefined): number {
  const parsed = Number(value || "1000000");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1000000;
}

function skippedText(item: WeeklyLog["skipped"][number], entryDate?: string): string {
  if (item.reason === "entry_gt_prevday_vwap_threshold") {
    const detail = item.entry_vs_reference_vwap_pct === undefined
      ? ""
      : ` because entry was ${pct(item.entry_vs_reference_vwap_pct)} above previous-day VWAP`;
    const prices = item.entry_price !== undefined && item.reference_vwap !== undefined
      ? ` (entry ${money(item.entry_price)}, VWAP ${money(item.reference_vwap)})`
      : "";
    return `${item.symbol}: skipped on ${entryDate || "entry date"}${detail}${prices}`;
  }
  return `${item.symbol}: skipped on ${entryDate || "entry date"} - ${item.reason}`;
}

function simulationHref(startDate: string, weeks: number, capital: number, recommendationModel: string): string {
  const params = new URLSearchParams({
    start_date: startDate,
    weeks: String(weeks),
    initial_capital: String(capital),
    recommendation_model: recommendationModel,
    run: "1"
  });
  return `/research/rolling-portfolio?${params.toString()}`;
}

async function runSimulation(startDate: string, weeks: number, initialCapital: number, recommendationModel: string): Promise<{ data?: SimulationResponse; error?: string }> {
  try {
    const response = await fetch(`${API_BASE}/research/rolling-portfolio/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_date: startDate,
        weeks,
        initial_capital: initialCapital,
        recommendation_model: recommendationModel
      }),
      cache: "no-store"
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      return { error: payload?.detail ? String(payload.detail) : `API request failed: ${response.status}` };
    }
    return { data: (await response.json()) as SimulationResponse };
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Rolling portfolio simulation failed" };
  }
}

async function loadDefaults(recommendationModel: string): Promise<DefaultsResponse> {
  try {
    const response = await fetch(`${API_BASE}/research/rolling-portfolio/defaults?recommendation_model=${encodeURIComponent(recommendationModel)}`, { cache: "no-store" });
    if (!response.ok) return {};
    return (await response.json()) as DefaultsResponse;
  } catch {
    return {};
  }
}

export default async function RollingPortfolioPage({ searchParams }: PageProps) {
  const recommendationModel = "sector_rotation_adx_1m3m";
  const defaults = await loadDefaults(recommendationModel);
  const startDate = searchParams?.start_date || defaults.default_start_date || "2026-05-04";
  const weeks = clampWeeks(searchParams?.weeks);
  const initialCapital = positiveCapital(searchParams?.initial_capital);
  const shouldRun = searchParams?.run === "1";
  const result = shouldRun ? await runSimulation(startDate, weeks, initialCapital, recommendationModel) : {};
  const data = result.data;
  const toDate = data?.summary.mark_date || "";
  const returnOnEquity = data?.summary.equity !== undefined ? (Number(data.summary.equity) - initialCapital) / initialCapital : null;

  return (
    <>
      <PageHeader
        title="Rolling Portfolio Backtest"
        subtitle="Step through Sector Rotation ADX recommendation cohorts using the preferred 10-slot construction."
      />

      <section className="panel">
        <form className="form-grid" action="/research/rolling-portfolio" method="get">
          <input type="hidden" name="run" value="1" />
          <input type="hidden" name="recommendation_model" value={recommendationModel} />
          <label>
            <span>Strategy</span>
            <input value={strategyLabel(recommendationModel)} readOnly />
          </label>
          <label>
            <span>Start date</span>
            <input
              type="date"
              name="start_date"
              defaultValue={startDate}
              min={defaults.earliest_recommendation_date || undefined}
              max={defaults.latest_recommendation_date || undefined}
            />
          </label>
          {data ? (
            <label>
              <span>To date</span>
              <input type="date" value={toDate} readOnly />
            </label>
          ) : null}
          <label>
            <span>Capital</span>
            <input inputMode="numeric" name="initial_capital" defaultValue={String(initialCapital)} />
          </label>
          <label>
            <span>Weeks included</span>
            <input type="number" min="1" max="260" name="weeks" defaultValue={String(weeks)} />
          </label>
          <button className="primary-button" type="submit">Run From Date</button>
          {data ? (
            <Link className="secondary-button" href={simulationHref(startDate, weeks + 1, initialCapital, recommendationModel)}>Next Week</Link>
          ) : (
            <span className="secondary-button disabled-link">Next Week</span>
          )}
          <Link className="secondary-button" href="/research/rolling-portfolio">Reset</Link>
        </form>
      </section>

      <p className="helper-text">
        Any date can be selected. The simulation uses the first available recommendation week on or after the selected date.
        Signal model: {strategyLabel(recommendationModel)}. Available recommendations: {defaults.earliest_recommendation_date || "n/a"} to {defaults.latest_recommendation_date || "n/a"}.
      </p>

      {result.error ? <div style={{ marginTop: 16 }}><ErrorState message={result.error} /></div> : null}

      {!data && !result.error ? (
        <div style={{ marginTop: 16 }}>
          <EmptyState message="Select any start date and run the simulation. Use Next Week to add one recommendation cohort at a time." />
        </div>
      ) : null}

      {data ? (
        <div className={styles.resultLayout}>
          <div className={styles.mainStack}>
          <section className="panel">
            <div className="data-status-head">
              <div>
                <h2>Portfolio State</h2>
                <p className="subtitle">
                  Effective start {data.parameters.effective_start_date || data.parameters.requested_start_date}; marked on {data.summary.mark_date || "n/a"}
                  {" "}· {strategyLabel(data.summary.recommendation_model || data.parameters.recommendation_model)}
                </p>
              </div>
              <span className="status-pill ok">{data.summary.open_positions ?? 0}/{data.summary.portfolio_size ?? 10} slots</span>
            </div>
            <div className={styles.portfolioMetrics} style={{ marginTop: 16 }}>
              <div><div className="metric-label">Equity</div><div className="metric-value">{money(data.summary.equity)}</div></div>
              <div><div className="metric-label">Cash</div><div className="metric-value">{money(data.summary.cash)}</div></div>
              <div><div className="metric-label">Market Value</div><div className="metric-value">{money(data.summary.market_value)}</div></div>
              <div><div className="metric-label">Cash %</div><div className="metric-value">{pct(data.summary.cash_pct)}</div></div>
              <div><div className="metric-label">Return on Equity</div><div className="metric-value">{returnOnEquity === null ? "n/a" : pct(returnOnEquity)}</div></div>
            </div>
            <table style={{ marginTop: 16 }}>
              <tbody>
                <tr><td>Weekly candidate cap</td><td>Top {data.summary.max_candidate_rank ?? 5}</td></tr>
                <tr><td>Entry rule</td><td>{data.summary.entry_time === "10:30:00" ? "10:30 candle open" : data.summary.entry_time || "daily open"}</td></tr>
                <tr><td>VWAP skip</td><td>{data.summary.vwap_skip_threshold === null || data.summary.vwap_skip_threshold === undefined ? "n/a" : `Skip above previous-day VWAP + ${(data.summary.vwap_skip_threshold * 100).toFixed(1)}%`}</td></tr>
                <tr><td>Holding period</td><td>{data.summary.holding_period ?? 20} trading days</td></tr>
                <tr><td>Closed trades so far</td><td>{data.summary.closed_trades ?? 0}</td></tr>
              </tbody>
            </table>
          </section>

          <section className="panel" style={{ marginTop: 16 }}>
            <h2>Weekly Recommendation Log</h2>
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>Week</th>
                    <th>Signal</th>
                    <th>Entry</th>
                    <th>Recommendations</th>
                    <th>Entered</th>
                    <th>Skipped</th>
                  </tr>
                </thead>
                <tbody>
                  {data.weekly_log.map((week) => (
                    <tr key={`${week.week_number}-${week.signal_date}`}>
                      <td>{week.week_number}</td>
                      <td>{week.signal_date}</td>
                      <td>{week.entry_date || "n/a"}</td>
                      <td>{week.recommendations.map((item) => `${item.rank}. ${item.symbol} (${Number(item.score ?? 0).toFixed(1)})`).join(", ") || "none"}</td>
                      <td>{week.entered.map((item) => item.symbol).join(", ") || "none"}</td>
                      <td>
                        {week.skipped.length ? (
                          <div className={styles.skipList}>
                            {week.skipped.map((item) => (
                              <div key={`${week.signal_date}-${item.symbol}-${item.reason}`}>{skippedText(item, week.entry_date)}</div>
                            ))}
                          </div>
                        ) : "none"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel" style={{ marginTop: 16 }}>
            <h2>Open Positions</h2>
            {data.positions.length ? (
              <div className="table-wrap" style={{ marginTop: 12 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Sector</th>
                      <th>Rank</th>
                      <th>Entry</th>
                      <th>Planned Exit</th>
                      <th>Entry Value</th>
                      <th>Market Value</th>
                      <th>Unrealized PnL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.positions.map((position) => (
                      <tr key={`${position.symbol}-${position.entry_date}`}>
                        <td>{position.symbol}</td>
                        <td>{position.sector || "n/a"}</td>
                        <td>{position.rank}</td>
                        <td>{position.entry_date}</td>
                        <td>{position.planned_exit_date}</td>
                        <td>{money(position.entry_value)}</td>
                        <td>{money(position.market_value)}</td>
                        <td>{money(position.unrealized_pnl)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="No open positions for the selected step." />
            )}
          </section>

          <section className="panel" style={{ marginTop: 16 }}>
            <h2>Closed Trades</h2>
            {data.trades.length ? (
              <div className="table-wrap" style={{ marginTop: 12 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Symbol</th>
                      <th>Sector</th>
                      <th>Entry</th>
                      <th>Exit</th>
                      <th>Holding Days</th>
                      <th>Entry Value</th>
                      <th>Exit Value</th>
                      <th>Charges</th>
                      <th>Net PnL</th>
                      <th>Net Return</th>
                      <th>Exit Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.trades.map((trade) => (
                      <tr className="closed-trade-row" key={`${trade.trade_id}-${trade.symbol}-${trade.exit_date}`}>
                        <td><span className="status-pill closed">Closed</span></td>
                        <td>{trade.symbol}</td>
                        <td>{trade.sector || "n/a"}</td>
                        <td>{trade.entry_date}</td>
                        <td>{trade.exit_date}</td>
                        <td>{trade.holding_days ?? "n/a"}</td>
                        <td>{money(trade.entry_value)}</td>
                        <td>{money(trade.exit_value)}</td>
                        <td>{money(trade.charges)}</td>
                        <td>{money(trade.net_pnl)}</td>
                        <td>{pct(trade.net_return_pct)}</td>
                        <td>{trade.exit_reason || "planned_exit"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="No positions have completed the 20-trading-day planned holding period yet." />
            )}
          </section>
          </div>
        </div>
      ) : null}
    </>
  );
}
