import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { safeApiGet } from "@/lib/api";
import { strategyLabel } from "@/lib/strategyNames";
import Link from "next/link";

type Rec = { rank: number; symbol: string; score?: number; sector?: string; adx_points?: number; sector_points?: number };
type Payload = { date: string | null; source: string; recommendations: Rec[] };

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
  return (
    <>
      <PageHeader title="Recommendations" subtitle={`Ranked ${label} list from ${data.date || "n/a"}.`} />
      {!data.recommendations.length ? (
        <EmptyState message={`No ${label} recommendations were returned by the API.`} />
      ) : null}
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr><th>Date</th><th>Rank</th><th>Symbol</th><th>Score</th><th>Sector</th><th>ADX Points</th><th>Sector Points</th></tr>
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
