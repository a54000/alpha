"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

type PipelineRunResponse = {
  status: string;
  pid: number;
  business_date: string;
  log_path: string;
  summary_path: string;
  command: string[];
  what_this_does: string[];
  safety: Record<string, boolean>;
};

type PipelineRunPayload = {
  business_date: string;
  portfolio_id: number;
  portfolio_size: number;
  max_candidate_rank: number;
  dry_run: boolean;
  sync_dry_run: boolean;
  rebalance_paper: boolean;
  resume: boolean;
  from_step: string;
};

const steps = [
  "",
  "angel_data_sync",
  "market_data_validation",
  "daily_bar_refresh",
  "feature_generation",
  "swing_v2_1_scoring",
  "recommendation_generation",
  "decision_journal_capture",
  "paper_portfolio_update",
  "monitoring_report_generation"
];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function PipelineRunPanel() {
  const [form, setForm] = useState<PipelineRunPayload>({
    business_date: todayIso(),
    portfolio_id: 1,
    portfolio_size: 10,
    max_candidate_rank: 5,
    dry_run: false,
    sync_dry_run: false,
    rebalance_paper: true,
    resume: false,
    from_step: ""
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PipelineRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function setField<K extends keyof PipelineRunPayload>(key: K, value: PipelineRunPayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function runPipeline() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await apiPost<PipelineRunResponse>("/pipeline/run", form);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start pipeline");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel" style={{ marginTop: 16 }}>
      <div className="section-heading">
        <div>
          <h2>Run Daily Pipeline</h2>
          <p className="subtitle">
            Starts the same controlled script used by the scheduled task. It syncs market data, rebuilds pilot artifacts,
            generates recommendations, and updates the paper portfolio. It does not place broker orders.
          </p>
        </div>
      </div>

      <div className="form-grid">
        <label>
          Business date
          <input type="date" value={form.business_date} onChange={(event) => setField("business_date", event.target.value)} />
        </label>
        <label>
          Portfolio ID
          <input type="number" min={1} value={form.portfolio_id} onChange={(event) => setField("portfolio_id", Number(event.target.value))} />
        </label>
        <label>
          Portfolio slots
          <input type="number" min={1} max={50} value={form.portfolio_size} onChange={(event) => setField("portfolio_size", Number(event.target.value))} />
        </label>
        <label>
          Max candidate rank
          <input type="number" min={1} max={50} value={form.max_candidate_rank} onChange={(event) => setField("max_candidate_rank", Number(event.target.value))} />
        </label>
        <label>
          Start from step
          <select value={form.from_step} onChange={(event) => setField("from_step", event.target.value)}>
            {steps.map((step) => <option key={step || "all"} value={step}>{step || "Run all steps"}</option>)}
          </select>
        </label>
      </div>

      <div className="checkbox-row">
        <label><input type="checkbox" checked={form.dry_run} onChange={(event) => setField("dry_run", event.target.checked)} /> Dry run</label>
        <label><input type="checkbox" checked={form.sync_dry_run} onChange={(event) => setField("sync_dry_run", event.target.checked)} /> Sync dry run</label>
        <label><input type="checkbox" checked={form.rebalance_paper} onChange={(event) => setField("rebalance_paper", event.target.checked)} /> Update paper portfolio</label>
        <label><input type="checkbox" checked={form.resume} onChange={(event) => setField("resume", event.target.checked)} /> Resume completed steps</label>
      </div>

      <div className="explain-box">
        <strong>What this does:</strong>
        <ul>
          <li>Fetches only missing Angel 15-minute candles.</li>
          <li>Refreshes daily bars, features, scores, recommendations, and recommendation journal.</li>
          <li>Updates paper portfolio only when “Update paper portfolio” is selected.</li>
          <li>Writes logs under <code>logs/daily_pipeline</code> and summary JSON under <code>reports</code>.</li>
        </ul>
      </div>

      <button className="primary-button" type="button" onClick={runPipeline} disabled={loading}>
        {loading ? "Starting..." : "Start Pipeline"}
      </button>

      {error ? <div className="error-banner" style={{ marginTop: 12 }}>{error}</div> : null}
      {result ? (
        <div className="success-box" style={{ marginTop: 12 }}>
          <strong>Pipeline started.</strong>
          <dl>
            <dt>Process ID</dt><dd>{result.pid}</dd>
            <dt>Business date</dt><dd>{result.business_date}</dd>
            <dt>Log file</dt><dd>{result.log_path}</dd>
            <dt>Summary file</dt><dd>{result.summary_path}</dd>
          </dl>
          <p className="subtitle">Refresh this page after a minute to see step progress in the table below.</p>
        </div>
      ) : null}
    </section>
  );
}
