import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { safeApiGet } from "@/lib/api";
import { strategyLabel } from "@/lib/strategyNames";
import Link from "next/link";

type Rec = { rank: number; symbol: string; score?: number; sector?: string; adx_points?: number; sector_points?: number };
type PaperUpdate = {
  recommendation_date_used?: string | null;
  price_date_used?: string | null;
  symbols_entered?: string[];
  symbols_skipped?: Array<{ symbol?: string | null; reason?: string | null; message?: string | null }>;
};
type Payload = { date: string | null; source: string; recommendations: Rec[]; paper_update?: PaperUpdate | null };

const model = "sector_rotation_adx_1m3m";

export default async function RecommendationsPage() {
  const label = strategyLabel(model);
  const result = await safeApiGet<Payload>(`/recommendations/latest?model=${encodeURIComponent(model)}&limit=50`);
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Recommendations" subtitle={`Ranked ${label} list.`} />
        <ErrorState message={result.error} />
      </>
    );
  }
  const data = result.data;
  const paperUpdate = data.paper_update;
  const entered = paperUpdate?.symbols_entered || [];
  const skipped = paperUpdate?.symbols_skipped || [];
  return (
    <>
      <PageHeader title="Recommendations" subtitle={`Ranked ${label} list from ${data.date || "n/a"}.`} />
      {!data.recommendations.length ? (
        <EmptyState message={`No ${label} recommendations were returned by the API.`} />
      ) : null}
      {paperUpdate ? (
        <section className="panel recommendation-action-note">
          <div className="section-head">
            <div>
              <h2>Paper Portfolio Action</h2>
              <p className="subtitle">
                Shows what happened when the latest recommendations were checked for paper portfolio entry.
              </p>
            </div>
            <span className={entered.length ? "status-pill ok" : "status-pill warn"}>
              {entered.length ? `${entered.length} entered` : "No new entry"}
            </span>
          </div>
          {entered.length ? (
            <p className="subtitle">Entered: {entered.join(", ")}.</p>
          ) : null}
          {skipped.length ? (
            <div className="skip-note-list">
              {skipped.map((item, index) => (
                <div key={`${item.symbol || "candidate"}-${index}`}>
                  <strong>{item.symbol || "Candidate"}</strong>
                  <span>{item.message || "Not entered."}</span>
                </div>
              ))}
            </div>
          ) : null}
          {!entered.length && !skipped.length ? (
            <p className="subtitle">No entry action has been recorded for this recommendation date yet.</p>
          ) : null}
        </section>
      ) : null}
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr><th>Date</th><th>Rank</th><th>Symbol</th><th>Score</th><th>Sector</th><th>Trend Score</th><th>Sector Score</th></tr>
          </thead>
          <tbody>
            {data.recommendations.map((row) => (
              <tr key={`${row.rank}-${row.symbol}`}>
                <td>{data.date || "n/a"}</td>
                <td>{row.rank}</td>
                <td><Link href={`/recommendations/${encodeURIComponent(row.symbol)}/explanation`}>{row.symbol}</Link></td>
                <td>{row.score ?? "n/a"}</td>
                <td>{row.sector || "n/a"}</td>
                <td>{row.adx_points ?? "n/a"}</td>
                <td>{row.sector_points ?? "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
