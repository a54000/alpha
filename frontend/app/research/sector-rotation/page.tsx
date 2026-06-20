import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanel";
import { pct, safeApiGet } from "@/lib/api";

type SectorRow = {
  sector: string;
  as_of: string;
  constituents: number;
  sector_return_1w: number | null;
  sector_return_1m: number | null;
  sector_return_3m: number | null;
  relative_strength_1w: number | null;
  relative_strength_1m: number | null;
  relative_strength_3m: number | null;
  rs_ratio: number | null;
  rs_momentum: number | null;
  tail?: Array<{ date: string; rs_ratio: number; rs_momentum: number }>;
  quadrant: "leading" | "weakening" | "lagging" | "improving" | "unknown";
  tail_direction?: "right" | "left" | "flat" | "unknown";
  layer2_action?: string;
  layer2_bias?: "long" | "short" | "watch_long" | "watch_turn" | "caution" | "avoid" | "wait";
  layer2_priority?: number;
  layer2_interpretation?: string;
  long_eligible?: boolean;
  short_eligible?: boolean;
  classification_confidence?: "clear" | "moderate" | "borderline" | "insufficient";
  turnover_ratio: number | null;
  bullish_pct_today: number | null;
  bullish_pct_1w: number | null;
  bullish_pct_1m: number | null;
  rotation_score: number;
  interpretation: string;
};

type IndustryRow = {
  as_of: string;
  sector: string;
  industry: string;
  stock_count: number;
  breadth_pct: number | null;
  relative_strength: number | null;
  volume_trend: number | null;
  structure_pct: number | null;
  composite: number | null;
  status: "Strong" | "Moderate" | "Weak" | "Avoid";
};

type Payload = {
  as_of: string | null;
  benchmark: string;
  summary?: {
    leading_count?: number;
    improving_count?: number;
    weakening_count?: number;
    lagging_count?: number;
    top_leading?: string[];
    top_improving?: string[];
    top_weakening?: string[];
    top_lagging?: string[];
  };
  diagnostics?: {
    rs_ratio_min?: number | null;
    rs_ratio_max?: number | null;
    rs_ratio_spread?: number | null;
    rs_momentum_spread?: number | null;
    borderline_sectors?: string[];
    caution?: string | null;
  };
  sectors: SectorRow[];
};

type IndustryPayload = {
  as_of: string | null;
  sector?: string | null;
  industries: IndustryRow[];
};

function n(value: unknown, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "n/a";
  return number.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

function quadrantLabel(value: SectorRow["quadrant"]) {
  return value === "leading"
    ? "Leading"
    : value === "weakening"
      ? "Weakening"
      : value === "improving"
        ? "Improving"
        : value === "lagging"
          ? "Lagging"
          : "Unknown";
}

function toneFor(value: SectorRow["quadrant"]) {
  if (value === "leading") return "ok";
  if (value === "improving") return "info";
  if (value === "weakening") return "warn";
  if (value === "lagging") return "bad";
  return "";
}

function actionLabel(value?: string) {
  const labels: Record<string, string> = {
    fresh_long_candidate: "Fresh Long",
    hold_or_tighten_longs: "Hold / Tighten",
    early_long_watch: "Watch Long",
    watch_short: "Watch Short",
    avoid_trap_risk: "Avoid",
    short_candidate: "Short",
    wait_not_confirmed: "Wait",
    fresh_short_candidate: "Fresh Short",
    cover_or_watch_turn: "Cover / Watch",
    wait: "Wait"
  };
  return labels[value || ""] || "Wait";
}

function biasTone(value?: SectorRow["layer2_bias"]) {
  if (value === "long") return "ok";
  if (value === "watch_long" || value === "watch_turn") return "info";
  if (value === "short") return "bad";
  if (value === "caution" || value === "wait") return "warn";
  return "";
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function sectorCode(name: string) {
  const map: Record<string, string> = {
    "AUTOMOBILE": "AUTO",
    "CEMENT & CEMENT PRODUCTS": "CEM",
    "CHEMICALS": "CHEM",
    "CONSTRUCTION": "CSTR",
    "CONSUMER GOODS": "CGDS",
    "ENERGY": "ENRG",
    "FERTILISERS & PESTICIDES": "FERT",
    "FINANCIAL SERVICES": "FIN",
    "HEALTHCARE SERVICES": "HLTH",
    "INDUSTRIAL MANUFACTURING": "INDM",
    "IT": "IT",
    "MEDIA & ENTERTAINMENT": "MED",
    "METALS": "METL",
    "PHARMA": "PHAR",
    "SERVICES": "SERV",
    "TELECOM": "TEL",
    "TEXTILES": "TEXT"
  };
  return map[name] || name.split(/\s+/).map((part) => part[0]).join("").slice(0, 4);
}

function RrgPlot({ sectors }: { sectors: SectorRow[] }) {
  const usable = sectors.filter((sector) => sector.rs_ratio !== null && sector.rs_momentum !== null);
  if (!usable.length) return <EmptyState message="Not enough sector history to draw the rotation map." />;
  return (
    <div className="rrg-plot" aria-label="Relative rotation graph">
      <div className="rrg-axis horizontal" />
      <div className="rrg-axis vertical" />
      <span className="rrg-label top-left">Improving</span>
      <span className="rrg-label top-right">Leading</span>
      <span className="rrg-label bottom-left">Lagging</span>
      <span className="rrg-label bottom-right">Weakening</span>
      <span className="rrg-axis-number x left">95</span>
      <span className="rrg-axis-number x mid">100 RS-Ratio</span>
      <span className="rrg-axis-number x right">105</span>
      <span className="rrg-axis-number y top">105</span>
      <span className="rrg-axis-number y mid">100 RS-Momentum</span>
      <span className="rrg-axis-number y bottom">95</span>
      {usable.map((sector) => {
        const tail = sector.tail?.length ? sector.tail : [];
        if (!tail.length) return null;
        const points = tail.map((point) => ({
          date: point.date,
          x: clamp(50 + (Number(point.rs_ratio) - 100) * 4.6, 4, 96),
          y: clamp(50 - (Number(point.rs_momentum) - 100) * 4.6, 4, 96)
        }));
        const latest = points[points.length - 1];
        return (
          <div key={sector.sector}>
            {points.slice(0, -1).map((point, index) => (
              <span
                key={`${sector.sector}-${point.date}`}
                className={`rrg-tail ${sector.quadrant}`}
                style={{ left: `${point.x}%`, top: `${point.y}%`, opacity: 0.18 + index / Math.max(points.length, 1) * 0.45 }}
                title={`${sector.sector} ${point.date}`}
              />
            ))}
            <div
              className={`rrg-dot ${sector.quadrant}`}
              style={{ left: `${latest.x}%`, top: `${latest.y}%` }}
              title={`${sector.sector}: ${quadrantLabel(sector.quadrant)} | RS-Ratio ${n(sector.rs_ratio)} | RS-Momentum ${n(sector.rs_momentum)}`}
            >
              <span>{sectorCode(sector.sector)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SummaryList({ title, values }: { title: string; values?: string[] }) {
  return (
    <div className="rotation-summary-list">
      <span>{title}</span>
      <strong>{values?.length ? values.join(", ") : "None"}</strong>
    </div>
  );
}

function topDownFunnel(sectors: SectorRow[]) {
  const breadthOk = (sector: SectorRow) => Number(sector.bullish_pct_1w ?? 0) >= 0.55;
  const turnoverOk = (sector: SectorRow) => Number(sector.turnover_ratio ?? 0) >= 1;
  const notBorderline = (sector: SectorRow) => sector.classification_confidence !== "borderline";
  const preferred = sectors
    .filter((sector) => sector.layer2_bias === "long" && turnoverOk(sector) && breadthOk(sector) && notBorderline(sector))
    .sort((a, b) => Number(a.layer2_priority ?? 9) - Number(b.layer2_priority ?? 9));
  const watchlist = sectors
    .filter(
      (sector) =>
        sector.layer2_bias === "watch_long" ||
        sector.layer2_bias === "watch_turn" ||
        (sector.layer2_bias === "long" && (!turnoverOk(sector) || !notBorderline(sector)))
    )
    .sort((a, b) => Number(b.rs_momentum ?? 0) - Number(a.rs_momentum ?? 0));
  const avoid = sectors
    .filter((sector) => sector.layer2_bias === "avoid" || sector.layer2_bias === "short")
    .sort((a, b) => Number(a.rs_momentum ?? 0) - Number(b.rs_momentum ?? 0));
  const shorts = sectors
    .filter((sector) => sector.layer2_bias === "short")
    .sort((a, b) => Number(a.layer2_priority ?? 9) - Number(b.layer2_priority ?? 9));
  return { preferred, watchlist, avoid, shorts };
}

function SectorPills({ sectors, empty }: { sectors: SectorRow[]; empty: string }) {
  if (!sectors.length) return <span className="funnel-empty">{empty}</span>;
  return (
    <div className="funnel-pills">
      {sectors.slice(0, 6).map((sector) => (
        <span key={sector.sector} title={`${sector.sector}: ${quadrantLabel(sector.quadrant)}`}>
          {sector.sector}
        </span>
      ))}
    </div>
  );
}

export default async function SectorRotationPage() {
  const [result, industryResult] = await Promise.all([
    safeApiGet<Payload>("/research/sector-rotation/insights"),
    safeApiGet<IndustryPayload>("/research/sector-rotation/industry-confirmation"),
  ]);
  if (!result.ok) {
    return (
      <>
        <PageHeader title="Sector Rotation" subtitle="See which sectors are gaining or losing leadership versus the market." />
        <ErrorState message={result.error} />
      </>
    );
  }

  const data = result.data;
  const sectors = data.sectors || [];
  const industries = industryResult.ok ? industryResult.data.industries || [] : [];
  const leading = sectors.filter((row) => row.quadrant === "leading");
  const improving = sectors.filter((row) => row.quadrant === "improving");
  const weakening = sectors.filter((row) => row.quadrant === "weakening");
  const lagging = sectors.filter((row) => row.quadrant === "lagging");
  const funnel = topDownFunnel(sectors);

  return (
    <>
      <PageHeader
        title="Sector Rotation"
        subtitle="Track sector leadership using relative strength, momentum, breadth trend, and turnover flow."
        actions={
          <div className="refresh-badge">
            <span>Refresh Date</span>
            <strong>{data.as_of || "n/a"}</strong>
          </div>
        }
      />

      {!sectors.length ? <EmptyState message="No sector rotation data is available yet." /> : null}

      <section className="panel rotation-hero">
        <div>
          <div className="metric-label">Market map</div>
          <h2>Which sectors are rotating in or fading out?</h2>
          <p className="subtitle">
            The view compares each synthetic sector basket with {data.benchmark || "NIFTY50"} and normalizes the relationship around 100.
            A quadrant is a directional map, so confirm it with actual 1W / 1M / 3M relative returns, turnover, and breadth.
          </p>
        </div>
        <div className="rotation-kpis">
          <div><span>Leading</span><strong>{leading.length}</strong></div>
          <div><span>Improving</span><strong>{improving.length}</strong></div>
          <div><span>Weakening</span><strong>{weakening.length}</strong></div>
          <div><span>Lagging</span><strong>{lagging.length}</strong></div>
        </div>
      </section>

      {data.diagnostics?.caution ? (
        <section className="panel rotation-caution">
          <strong>Interpretation caution</strong>
          <span>{data.diagnostics.caution}</span>
          <small>
            RS-Ratio range: {n(data.diagnostics.rs_ratio_min)} to {n(data.diagnostics.rs_ratio_max)}
            {" "}({n(data.diagnostics.rs_ratio_spread)} points).
            Borderline: {data.diagnostics.borderline_sectors?.length ? data.diagnostics.borderline_sectors.join(", ") : "none"}.
          </small>
        </section>
      ) : null}

      {industryResult.ok ? (
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Industry Confirmation</h2>
              <p className="subtitle">
                Layer 3 narrows each sector into its strongest industries using breadth, RS versus sector, volume trend, and structure.
              </p>
            </div>
            <span className="status-pill">Latest</span>
          </div>
          {!industries.length ? (
            <EmptyState message="No industry confirmation rows are available yet." />
          ) : (
            <div className="industry-grid">
              {industries.slice(0, 8).map((industry) => (
                <div key={`${industry.sector}-${industry.industry}`} className="industry-card">
                  <div className="industry-card-head">
                    <strong>{industry.industry}</strong>
                    <span className={`state-chip ${industry.status === "Strong" ? "ok" : industry.status === "Moderate" ? "info" : industry.status === "Weak" ? "warn" : "bad"}`}>
                      {industry.status}
                    </span>
                  </div>
                  <p>{industry.sector}</p>
                  <div className="industry-metrics">
                    <span>Breath {n(industry.breadth_pct)}%</span>
                    <span>RS {n(industry.relative_strength)}</span>
                    <span>Vol {n(industry.volume_trend)}</span>
                    <span>Struct {n(industry.structure_pct)}%</span>
                  </div>
                  <div className="industry-score">Score {n(industry.composite)}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="panel">
          <ErrorState message={industryResult.error} />
        </section>
      )}

      <section className="panel top-down-funnel">
        <div className="section-head">
          <div>
            <h2>Top-Down Funnel</h2>
            <p className="subtitle">
              Start broad, then narrow: market context, sector leadership, confirmation, shortlist, then entry plan.
            </p>
          </div>
          <span className="status-pill">Decision aid</span>
        </div>
        <div className="funnel-grid">
          <div className="funnel-step">
            <span>1</span>
            <div>
              <strong>Market lens</strong>
              <p>Selective. Favor confirmed leadership and avoid forcing trades from weak sectors.</p>
            </div>
          </div>
          <div className="funnel-step">
            <span>2</span>
            <div>
              <strong>Primary sectors</strong>
              <p>Fresh long sectors where quadrant, tail direction, flow, and breadth agree.</p>
              <SectorPills sectors={funnel.preferred} empty="No fully confirmed primary sector today." />
            </div>
          </div>
          <div className="funnel-step">
            <span>3</span>
            <div>
              <strong>Watchlist sectors</strong>
              <p>Early long, turn, or fading leadership states that need confirmation.</p>
              <SectorPills sectors={funnel.watchlist} empty="No watchlist sector today." />
            </div>
          </div>
          <div className="funnel-step">
            <span>4</span>
            <div>
              <strong>Avoid for fresh longs</strong>
              <p>Avoid fresh longs where Layer 2 is weak, short-biased, or trap-risk.</p>
              <SectorPills sectors={funnel.avoid} empty="No lagging sectors today." />
            </div>
          </div>
          <div className="funnel-step">
            <span>5</span>
            <div>
              <strong>Short candidates</strong>
              <p>Weakening or lagging sectors with tail direction still moving left.</p>
              <SectorPills sectors={funnel.shorts} empty="No confirmed short sector today." />
            </div>
          </div>
        </div>
        <div className="rotation-note">
          Use this as a filter before stock selection. A stock inside a lagging sector can still bounce, but it should carry a higher burden of proof.
        </div>
      </section>

      <div className="grid cols-2">
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Relative Rotation Map</h2>
              <p className="subtitle">
                Right side means relative strength is above its recent smoothed trend. Upper side means that relative strength is improving.
              </p>
            </div>
            <span className="status-pill">As of {data.as_of || "n/a"}</span>
          </div>
          <RrgPlot sectors={sectors} />
        </section>

        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Rotation Readout</h2>
              <p className="subtitle">A quick separation of leadership, recovery, and risk of fading.</p>
            </div>
          </div>
          <div className="rotation-summary-stack">
            <SummaryList title="Leading now" values={data.summary?.top_leading} />
            <SummaryList title="Improving watchlist" values={data.summary?.top_improving} />
            <SummaryList title="Weakening watchlist" values={data.summary?.top_weakening} />
            <SummaryList title="Lagging" values={data.summary?.top_lagging} />
          </div>
          <div className="rotation-note">
            Today's bullish percentage is shown beside 1-week and 1-month breadth so a one-day spike does not masquerade as a rotation signal.
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Sector Rotation Table</h2>
            <p className="subtitle">
              RS 1W / 1M / 3M show actual return comparison. RS-Ratio and RS-Momentum are smoothed RRG measures centered around 100.
            </p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Sector</th>
                <th>State</th>
                <th>Tail</th>
                <th>Layer 2 Action</th>
                <th>RS 1W</th>
                <th>RS 1M</th>
                <th>RS 3M</th>
                <th>RS-Ratio</th>
                <th>RS-Momentum</th>
                <th>Breadth Today</th>
                <th>Breadth 1W</th>
                <th>Breadth 1M</th>
                <th>Turnover</th>
                <th>Confidence</th>
                <th>Read</th>
              </tr>
            </thead>
            <tbody>
              {sectors.map((sector) => (
                <tr key={sector.sector}>
                  <td><strong>{sector.sector}</strong><br /><small>{sector.constituents} stocks</small></td>
                  <td><span className={`state-chip ${toneFor(sector.quadrant)}`}>{quadrantLabel(sector.quadrant)}</span></td>
                  <td>{sector.tail_direction || "n/a"}</td>
                  <td><span className={`state-chip ${biasTone(sector.layer2_bias)}`}>{actionLabel(sector.layer2_action)}</span></td>
                  <td>{pct(sector.relative_strength_1w)}</td>
                  <td>{pct(sector.relative_strength_1m)}</td>
                  <td>{pct(sector.relative_strength_3m)}</td>
                  <td>{n(sector.rs_ratio)}</td>
                  <td>{n(sector.rs_momentum)}</td>
                  <td>{pct(sector.bullish_pct_today)}</td>
                  <td>{pct(sector.bullish_pct_1w)}</td>
                  <td>{pct(sector.bullish_pct_1m)}</td>
                  <td>{n(sector.turnover_ratio)}x</td>
                  <td>{sector.classification_confidence || "n/a"}</td>
                  <td>{sector.layer2_interpretation || sector.interpretation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
