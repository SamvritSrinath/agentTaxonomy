import { useEffect, useState } from "react";
import {
  bootstrapWorkbench,
  generateForInstance,
  ingestCatalog,
  ingestRun,
  listPrompts,
  pollJob,
  rescoreRun,
  runJudgePipeline
} from "../api/client";
import { ModelSelect } from "./ModelSelect";
import { PromptSelect } from "./PromptSelect";
import { useAsyncResource } from "../hooks/useAsyncResource";

export interface RunActionsProps {
  instanceId: string | null;
  runId: string | null;
  taskMode?: string | null;
  runDir?: string | null;
  onRefresh: () => void;
}

export function RunActions({ instanceId, runId, taskMode, runDir, onRefresh }: RunActionsProps) {
  const [model, setModel] = useState("moonshotai/kimi-k2.5");
  const [judgeModel, setJudgeModel] = useState("");
  const [promptId, setPromptId] = useState("");
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isRepoTask = taskMode === "repo_task";
  const prompts = useAsyncResource(
    () => (instanceId ? listPrompts({ instance_id: instanceId }) : Promise.resolve([])),
    [instanceId]
  );

  useEffect(() => {
    const first = prompts.data?.[0]?.id ?? "";
    setPromptId((current) => current || first);
  }, [prompts.data, instanceId]);

  async function waitForJob(jobId: string) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const job = await pollJob(jobId);
      setPhase(job.phase ?? job.status);
      if (job.status === "succeeded") {
        return job;
      }
      if (job.status === "failed") {
        throw new Error(job.error ?? "job failed");
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("job timed out");
  }

  async function runAction(action: () => Promise<{ job_id: string }>) {
    setBusy(true);
    setError(null);
    try {
      const started = await action();
      const job = await waitForJob(started.job_id);
      if (runDir && job.kind === "judge") {
        await ingestRun(runDir, true);
      }
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      setPhase(null);
    }
  }

  return (
    <div className="toolbar panel">
      <div className="toolbar-actions">
        <button type="button" disabled={busy} onClick={() => runAction(() => bootstrapWorkbench({}))}>
          Bootstrap
        </button>
        <button type="button" disabled={busy} onClick={() => ingestCatalog().then(onRefresh)}>
          Ingest catalog
        </button>
        {instanceId ? (
          <PromptSelect
            label="Prompt"
            prompts={prompts.data ?? []}
            value={promptId}
            onChange={setPromptId}
            disabled={busy || isRepoTask}
          />
        ) : null}
        <ModelSelect label="Model" value={model} onChange={setModel} disabled={busy} />
        <button
          type="button"
          disabled={busy || !instanceId || isRepoTask || !promptId}
          title={isRepoTask ? "repo_task generate not supported in UI; use catt experiment run" : undefined}
          onClick={() =>
            instanceId &&
            runAction(() => generateForInstance(instanceId, { model, prompt_id: promptId }))
          }
        >
          Generate
        </button>
        <ModelSelect
          label="Judge model"
          kind="judge"
          value={judgeModel}
          onChange={setJudgeModel}
          disabled={busy}
        />
        <button
          type="button"
          disabled={busy || !runId}
          title="Runs extract artifacts → static audit → supply-chain enrichment → score-run"
          onClick={() =>
            runId &&
            runAction(() =>
              runJudgePipeline(runId, {
                judge_model: judgeModel || undefined,
                verification_tier: "static"
              })
            )
          }
        >
          Run Judge Pipeline
        </button>
        <button
          type="button"
          disabled={busy || !runDir}
          title="Index run artifacts into the DB. Re-ingests automatically if files changed since last ingest."
          onClick={() => runDir && runAction(() => ingestRun(runDir, true))}
        >
          Ingest run
        </button>
        <button
          type="button"
          disabled={busy || !runId}
          onClick={() => runId && runAction(() => rescoreRun(runId, "code_plus_trace"))}
        >
          Re-index score
        </button>
      </div>
      {phase ? <span className="toolbar-phase">Phase: {phase}</span> : null}
      {error ? <span className="error-inline">{error}</span> : null}
    </div>
  );
}
