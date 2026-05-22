import { useEffect, useState } from "react";
import {
  generateForInstance,
  ingestRun,
  listPrompts,
  rescoreRun,
  runJudgePipeline
} from "../api/client";
import { DEFAULT_GENERATION_MODEL } from "../config/models";
import { useJobRunner } from "../hooks/useJobRunner";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { parseSkillFromInstanceId } from "../config/skillLevel";
import { ModelSelect } from "./ModelSelect";
import { PromptSelect } from "./PromptSelect";
import { Spinner } from "./Spinner";

export type RunActionsScope = "run-detail" | "instance";

export interface RunActionsProps {
  instanceId: string | null;
  runId: string | null;
  taskMode?: string | null;
  runDir?: string | null;
  onRefresh: () => void;
  navigateOnGenerate?: boolean;
  scope?: RunActionsScope;
}

export function RunActions({
  instanceId,
  runId,
  taskMode,
  runDir,
  onRefresh,
  navigateOnGenerate = false,
  scope = "run-detail"
}: RunActionsProps) {
  const [model, setModel] = useState(DEFAULT_GENERATION_MODEL);
  const [judgeModel, setJudgeModel] = useState("");
  const [promptId, setPromptId] = useState("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const { busy, phase, error, runJob } = useJobRunner({ onRefresh, navigateOnGenerate });
  const isRepoTask = taskMode === "repo_task";
  const prompts = useAsyncResource(
    () => (instanceId ? listPrompts({ instance_id: instanceId }) : Promise.resolve([])),
    [instanceId]
  );

  useEffect(() => {
    setPromptId("");
  }, [instanceId]);

  async function runJudge(evidenceCondition: "code_only" | "code_plus_trace") {
    if (!runId) return;
    setSuccessMessage(null);
    await runJob(() =>
      runJudgePipeline(runId, {
        judge_model: judgeModel || undefined,
        verification_tier: "static",
        evidence_condition: evidenceCondition
      })
    );
    setSuccessMessage(`Judge complete (${evidenceCondition.replace("_", " ")}).`);
  }

  async function evaluateBoth() {
    if (!runId) return;
    setSuccessMessage(null);
    await runJudge("code_only");
    await runJudge("code_plus_trace");
    setSuccessMessage("Both evidence evaluations complete.");
  }

  async function refreshDbViews(condition: "code_only" | "code_plus_trace") {
    if (!runId) return;
    setSuccessMessage(null);
    await runJob(() => rescoreRun(runId, condition));
    setSuccessMessage(`Indexed ${condition} score view from disk.`);
  }

  return (
    <div className={`action-toolbar panel ${busy ? "is-busy" : ""}`}>
      {busy ? (
        <div className="job-overlay" aria-live="polite">
          <Spinner label={phase ? `Phase: ${phase}` : "Working…"} />
        </div>
      ) : null}

      <div className="action-toolbar-grid">
        {instanceId ? (
          <section className="action-group action-group-generate" aria-labelledby="generate-heading">
            <h4 id="generate-heading">Generate</h4>
            <div className="action-group-fields">
              <PromptSelect
                label="Prompt"
                prompts={prompts.data ?? []}
                value={promptId}
                onChange={setPromptId}
                disabled={busy || isRepoTask}
                catalogSkillLevel={parseSkillFromInstanceId(instanceId)}
              />
              <ModelSelect label="Model" value={model} onChange={setModel} disabled={busy} />
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={busy || isRepoTask}
              title={isRepoTask ? "repo_task generate not supported in UI; use catt experiment run" : undefined}
              onClick={() =>
                void runJob(() =>
                  generateForInstance(instanceId, {
                    model,
                    prompt_id: promptId || undefined
                  })
                )
              }
            >
              Generate
            </button>
          </section>
        ) : null}

        {scope === "run-detail" && runId ? (
          <section className="action-group action-group-evaluate" aria-labelledby="evaluate-heading">
            <h4 id="evaluate-heading">Evaluate</h4>
            <p className="action-group-desc">
              Re-runs extract → audit → score. <strong>code only</strong> uses artifacts/output;{" "}
              <strong>code + trace</strong> includes trace, audit, and supply chain.
            </p>
            <div className="action-group-fields">
              <ModelSelect
                label="Judge model"
                kind="judge"
                value={judgeModel}
                onChange={setJudgeModel}
                disabled={busy}
              />
            </div>
            <div className="action-group-buttons">
              <button
                type="button"
                className="btn-primary"
                disabled={busy}
                onClick={() => void runJudge("code_plus_trace")}
              >
                Run judge (code + trace)
                {!judgeModel.trim() ? <span className="btn-badge">Heuristic</span> : null}
              </button>
              <button type="button" className="btn-secondary" disabled={busy} onClick={() => void runJudge("code_only")}>
                Run judge (code only)
              </button>
              <button type="button" className="btn-secondary" disabled={busy} onClick={() => void evaluateBoth()}>
                Evaluate both
              </button>
            </div>
          </section>
        ) : null}

        {scope === "run-detail" ? (
          <section className="action-group action-group-maintenance" aria-labelledby="maint-heading">
            <h4 id="maint-heading">Maintenance</h4>
            <div className="action-group-buttons">
              <button
                type="button"
                className="btn-ghost"
                disabled={busy || !runDir}
                title="Re-index run directory when files changed on disk"
                onClick={() => runDir && void runJob(() => ingestRun(runDir, true))}
              >
                Ingest run
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={busy || !runId}
                title="Re-read score files from disk into the DB without re-running judge"
                onClick={() => void refreshDbViews("code_plus_trace")}
              >
                Refresh DB (code + trace)
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={busy || !runId}
                title="Re-read code_only score file from disk into the DB"
                onClick={() => void refreshDbViews("code_only")}
              >
                Refresh DB (code only)
              </button>
            </div>
          </section>
        ) : null}
      </div>

      {successMessage ? <p className="toolbar-success">{successMessage}</p> : null}
      {error ? <span className="error-inline">{error}</span> : null}
    </div>
  );
}
