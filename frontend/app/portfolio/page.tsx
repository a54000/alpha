import { MetricCard } from "@/components/MetricCard";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { money, pct, safeApiGet } from "@/lib/api";

type Payload = {
  summary: Record<string, unknown>;
  risk: Record<string, unknown>;
  positions: Array<Record<string, unknown>>;
  trades: Array<Record<string, unknown>>;
};

export default async function PortfolioPage() {
  const result = await safeApiGet<Payload>("/portfolio");
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Portfolio" subtitle="Holdings, recent trades, and paper performance." />
        <ErrorState message={result.error} />
      </>
    );
  }
  const data = result.data;
  const hasPortfolio = Object.keys(data.summary || {}).length > 0;
  return (
    <>
      <PageHeader title="Portfolio" subtitle="Holdings, recent trades, and paper performance." />
      {!hasPortfolio ? (
        <EmptyState message="No paper portfolio snapshot is available. Set PAPER_PORTFOLIO_ID or initialize a paper portfolio." />
      ) : null}
      <div className="grid cols-4">
        <MetricCard label="NAV" value={money(data.summary.nav ?? data.summary.current_nav)} />
        <MetricCard label="Cash" value={money(data.summary.cash)} />
        <MetricCard label="Exposure" value={pct(data.risk.exposure)} />
        <MetricCard label="Open Positions" value={String(data.summary.open_positions ?? data.positions.length)} />
      </div>
      {data.summary.latest_paper_update_message ? (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Paper Trading Status</h2>
          <p className="subtitle">{String(data.summary.latest_paper_update_message)}</p>
        </section>
      ) : null}
      <section className="panel table-wrap" style={{ marginTop: 16 }}>
        <h2>Holdings</h2>
        {!data.positions.length ? <p className="subtitle">No holdings returned by the API.</p> : null}
        <table>
          <thead><tr><th>Symbol</th><th>Sector</th><th>Entry</th><th>Market Value</th><th>Unrealized PnL</th><th>Planned Exit</th></tr></thead>
          <tbody>
            {data.positions.map((row) => (
              <tr key={`${row.symbol}-${row.entry_date}`}>
                <td>{String(row.symbol)}</td><td>{String(row.sector || "n/a")}</td><td>{String(row.entry_date || "n/a")}</td>
                <td>{money(row.market_value)}</td><td>{money(row.unrealized_pnl)}</td><td>{String(row.planned_exit_date || "n/a")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel table-wrap" style={{ marginTop: 16 }}>
        <h2>Recent Trades</h2>
        {!data.trades.length ? <p className="subtitle">No recent trades returned by the API.</p> : null}
        <table>
          <thead><tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>Return</th><th>Realized PnL</th><th>Reason</th></tr></thead>
          <tbody>
            {data.trades.map((row) => (
              <tr key={String(row.trade_id)}>
                <td>{String(row.symbol)}</td><td>{String(row.entry_date)}</td><td>{String(row.exit_date)}</td>
                <td>{pct(row.return_pct)}</td><td>{money(row.realized_pnl)}</td><td>{String(row.exit_reason)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
