type PipelineStep = {
  business_date?: string | null;
  status?: string | null;
};

type FreshnessInput = {
  latestMarketDataDate?: unknown;
  latestRecommendationDate?: unknown;
  pipelineStatus?: unknown;
  pipelineSteps?: PipelineStep[];
  pipelineError?: string | null;
};

function dateOnly(value: unknown): string | null {
  if (!value) return null;
  const text = String(value);
  const match = text.match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : null;
}

export function computeFreshnessStatus(input: FreshnessInput): {
  tone: "ok" | "warn" | "bad";
  label: string;
  detail: string;
  latestPipelineRun: string | null;
} {
  const latestMarketDataDate = dateOnly(input.latestMarketDataDate);
  const latestRecommendationDate = dateOnly(input.latestRecommendationDate);
  const latestPipelineRun =
    input.pipelineSteps
      ?.map((step) => dateOnly(step.business_date))
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1) || null;
  const failedStep = input.pipelineSteps?.some((step) => step.status === "failed");

  if (!latestMarketDataDate || !latestRecommendationDate) {
    return {
      tone: "bad",
      label: "Stale data",
      detail: "Market data or recommendations are unavailable.",
      latestPipelineRun
    };
  }

  if (input.pipelineError || failedStep || input.pipelineStatus === "failed") {
    return {
      tone: "warn",
      label: "Pipeline delayed",
      detail: "Pipeline status is failed or unavailable; verify operations before acting.",
      latestPipelineRun
    };
  }

  if (latestPipelineRun && (latestMarketDataDate < latestPipelineRun || latestRecommendationDate < latestPipelineRun)) {
    return {
      tone: "bad",
      label: "Stale data",
      detail: "Market data or recommendations lag the latest pipeline business date.",
      latestPipelineRun
    };
  }

  if (latestMarketDataDate !== latestRecommendationDate) {
    return {
      tone: "warn",
      label: "Pipeline delayed",
      detail: "Market data and recommendations are not aligned to the same date.",
      latestPipelineRun
    };
  }

  return {
    tone: "ok",
    label: "All current",
    detail: "Market data, recommendations, and pipeline status are aligned.",
    latestPipelineRun
  };
}

export function DataStatusCard({
  latestMarketDataDate,
  latestRecommendationDate,
  pipelineStatus,
  pipelineSteps,
  pipelineError
}: FreshnessInput) {
  const status = computeFreshnessStatus({
    latestMarketDataDate,
    latestRecommendationDate,
    pipelineStatus,
    pipelineSteps,
    pipelineError
  });

  return (
    <section className={`panel data-status data-status-${status.tone}`}>
      <div className="data-status-head">
        <h2>Data Status</h2>
        <span className={`status-pill ${status.tone}`}>{status.label}</span>
      </div>
      <p className="subtitle">{status.detail}</p>
      <table>
        <tbody>
          <tr><td>Latest market data date</td><td>{dateOnly(latestMarketDataDate) || "n/a"}</td></tr>
          <tr><td>Latest recommendation date</td><td>{dateOnly(latestRecommendationDate) || "n/a"}</td></tr>
          <tr><td>Latest pipeline run</td><td>{status.latestPipelineRun || "n/a"}</td></tr>
          <tr><td>Freshness status</td><td>{status.label}</td></tr>
        </tbody>
      </table>
    </section>
  );
}
