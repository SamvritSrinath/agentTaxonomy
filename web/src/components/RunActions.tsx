import { useEffect, useState } from "react";
import {
  generateForInstance,
  ingestRun,
  listRepoTargetsForInstance,
  listPrompts,
  rescoreRun,
  runRepoTaskForInstance,
  runJudgePipeline
} from "../api/client";
import type { RepoTaskRunRequest } from "../api/types";
import { DEFAULT_GENERATION_MODEL } from "../config/models";
import { DEFAULT_REPO_AGENT_CMD, type RepoExecutionMethod } from "../config/repoRun";
import { useJobRunner } from "../hooks/useJobRunner";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { parseSkillFromInstanceId } from "../config/skillLevel";
import { FormField } from "./FormField";
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
  const [repoTargetId, setRepoTargetId] = useState("");
  const [manualRepoPath, setManualRepoPath] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [gitRef, setGitRef] = useState("");
  const [refreshClone, setRefreshClone] = useState(false);
  const [repoExecutionMethod, setRepoExecutionMethod] = useState<RepoExecutionMethod>("agent");
  const [agent, setAgent] = useState<"codex" | "opencode" | "command">("codex");
  const [agentCmd, setAgentCmd] = useState("");
  const [profile, setProfile] = useState<"static" | "smoke" | "full">("static");
  const [sandboxProfile, setSandboxProfile] = useState("class_b_repo_edit");
  const [repoOutputDir, setRepoOutputDir] = useState("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [repoFormError, setRepoFormError] = useState<string | null>(null);
  const { busy, phase, error, runJob } = useJobRunner({ onRefresh, navigateOnGenerate });
  const isRepoTask = taskMode === "repo_task";
  const prompts = useAsyncResource(
    () => (instanceId ? listPrompts({ instance_id: instanceId }) : Promise.resolve([])),
    [instanceId]
  );
  const repoTargets = useAsyncResource(
    () => (instanceId && isRepoTask ? listRepoTargetsForInstance(instanceId) : Promise.resolve([])),
    [instanceId, isRepoTask]
  );

  useEffect(() => {
    setPromptId("");
    setRepoTargetId("");
    setManualRepoPath("");
    setGitUrl("");
    setGitRef("");
    setRefreshClone(false);
    setRepoFormError(null);
    setRepoExecutionMethod("agent");
  }, [instanceId]);

  useEffect(() => {
    if (!isRepoTask || repoTargetId || !repoTargets.data?.length) return;
    const defaultTarget = repoTargets.data.find((target) => target.binding?.is_default) ?? repoTargets.data[0];
    setRepoTargetId(defaultTarget.id);
  }, [isRepoTask, repoTargetId, repoTargets.data]);

  const agentCmdPlaceholder =
    agent === "command"
      ? "Required for custom command; supports {prompt_file}, {worktree}, {output_dir}, {instance_id}"
      : `Leave empty to use default: ${DEFAULT_REPO_AGENT_CMD[agent === "opencode" ? "opencode" : "codex"]}`;

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

  async function runRepoTask() {
    if (!instanceId) return;
    const manualPath = manualRepoPath.trim();
    const remoteUrl = gitUrl.trim();
    if (manualPath && remoteUrl) {
      setRepoFormError("Use only one repo source: manual path or git remote, not both.");
      setSuccessMessage(null);
      return;
    }
    if (repoExecutionMethod === "agent" && agent === "command" && !agentCmd.trim()) {
      setRepoFormError("Custom command requires an agent command.");
      setSuccessMessage(null);
      return;
    }
    setRepoFormError(null);
    const request: RepoTaskRunRequest = {
      repo_target_id: manualPath || remoteUrl ? undefined : repoTargetId || undefined,
      repo_path: manualPath || undefined,
      git_url: remoteUrl || undefined,
      git_ref: gitRef.trim() || undefined,
      refresh_clone: refreshClone,
      execution_method: repoExecutionMethod,
      model: repoExecutionMethod === "model" ? model : undefined,
      agent: repoExecutionMethod === "agent" ? agent : undefined,
      agent_cmd: repoExecutionMethod === "agent" ? agentCmd.trim() || undefined : undefined,
      profile,
      sandbox_profile: repoExecutionMethod === "agent" ? sandboxProfile.trim() || undefined : undefined,
      output_dir: repoOutputDir.trim() || undefined,
      prompt_id: promptId || undefined,
      keep_worktree: true
    };
    setSuccessMessage(null);
    await runJob(() => runRepoTaskForInstance(instanceId, request));
    setSuccessMessage("Repo task queued.");
  }

  return (
    <div className={`action-toolbar panel ${busy ? "is-busy" : ""}`}>
      {busy ? (
        <div className="job-overlay" aria-live="polite">
          <Spinner label={phase ? `Phase: ${phase}` : "Working…"} />
        </div>
      ) : null}

      <div className="action-toolbar-grid">
        {instanceId && !isRepoTask ? (
          <section className="action-group action-group-generate" aria-labelledby="generate-heading">
            <h4 id="generate-heading">Generate</h4>
            <div className="action-group-fields">
              <PromptSelect
                label="Prompt"
                prompts={prompts.data ?? []}
                value={promptId}
                onChange={setPromptId}
                disabled={busy}
                catalogSkillLevel={parseSkillFromInstanceId(instanceId)}
              />
              <ModelSelect label="Model" value={model} onChange={setModel} disabled={busy} />
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={busy}
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

        {instanceId && isRepoTask ? (
          <section className="action-group action-group-generate" aria-labelledby="repo-run-heading">
            <h4 id="repo-run-heading">Repo Run</h4>
            <p className="action-group-desc">
              Both methods clone the repository and run the same harness (diff, tests, oracles, ingest). Only{" "}
              <strong>generation</strong> differs: OpenRouter edits via fenced file blocks, or a local CLI runs in the
              worktree. Evaluation uses the worktree diff; <code>agent_output.md</code> holds the model transcript.
            </p>

            <div className="repo-run-subsection">
              <h5 className="repo-run-subheading">Repository</h5>
              <p className="action-group-desc">
                Where the harness materializes code from. Unchanged when you switch Model vs Agent.
              </p>
              <div className="action-group-fields">
                <div className="form-field prompt-select-field wide-field">
                  <PromptSelect
                    label="Prompt"
                    prompts={prompts.data ?? []}
                    value={promptId}
                    onChange={setPromptId}
                    disabled={busy}
                    catalogSkillLevel={parseSkillFromInstanceId(instanceId)}
                  />
                  <p className="field-hint">
                    Filesystem catalog prompt (level markdown from bootstrap) or a saved variant override.
                  </p>
                </div>
                <FormField
                  label="Repo target"
                  hint='Catalog binding to a fixture or clone. "Default binding" uses the instance&apos;s is_default target from ingest.'
                >
                  <select
                    value={repoTargetId}
                    disabled={busy || Boolean(manualRepoPath.trim()) || Boolean(gitUrl.trim())}
                    onChange={(event) => setRepoTargetId(event.target.value)}
                  >
                    <option value="">Default binding</option>
                    {(repoTargets.data ?? []).map((target) => (
                      <option key={target.id} value={target.id}>
                        {target.binding?.is_default ? "Default: " : ""}
                        {target.name}
                      </option>
                    ))}
                  </select>
                </FormField>
                <FormField
                  label="Manual repo path"
                  hint="Path on the API server. Disables repo target and git remote."
                >
                  <input
                    value={manualRepoPath}
                    disabled={busy || Boolean(gitUrl.trim())}
                    placeholder="/absolute/path/or/project-relative"
                    onChange={(event) => setManualRepoPath(event.target.value)}
                  />
                </FormField>
                <FormField
                  label="Git remote (SSH/HTTPS)"
                  hint="Clone on the server. Disables repo target and manual path."
                >
                  <input
                    value={gitUrl}
                    disabled={busy || Boolean(manualRepoPath.trim())}
                    placeholder="git@github.com:org/repo.git"
                    onChange={(event) => setGitUrl(event.target.value)}
                  />
                </FormField>
                <FormField
                  label="Git ref"
                  hint="Branch, tag, or commit after clone. Only used with git remote."
                >
                  <input
                    value={gitRef}
                    disabled={busy || !gitUrl.trim()}
                    placeholder="main, v1.0.0, or commit sha"
                    onChange={(event) => setGitRef(event.target.value)}
                  />
                </FormField>
                <FormField
                  label="Refresh clone"
                  hint="Run git fetch before checkout when reusing a cached clone."
                  className="checkbox-field"
                >
                  <label className="checkbox-inline">
                    <input
                      type="checkbox"
                      checked={refreshClone}
                      disabled={busy || !gitUrl.trim()}
                      onChange={(event) => setRefreshClone(event.target.checked)}
                    />
                    git fetch before checkout
                  </label>
                </FormField>
              </div>
            </div>

            <div className="repo-run-subsection">
              <h5 className="repo-run-subheading">Generation</h5>
              <FormField
                label="Execution method"
                hint={
                  repoExecutionMethod === "model"
                    ? "OpenRouter completion; fenced blocks with paths (e.g. ```python app.py) are written into the worktree."
                    : "Codex, OpenCode, or a custom shell command in the sandboxed worktree."
                }
                className="wide-field"
              >
                <div className="run-method-toggle" role="group" aria-label="Execution method">
                  <button
                    type="button"
                    className={repoExecutionMethod === "model" ? "run-method-btn is-active" : "run-method-btn"}
                    disabled={busy}
                    onClick={() => setRepoExecutionMethod("model")}
                  >
                    Model (OpenRouter)
                  </button>
                  <button
                    type="button"
                    className={repoExecutionMethod === "agent" ? "run-method-btn is-active" : "run-method-btn"}
                    disabled={busy}
                    onClick={() => setRepoExecutionMethod("agent")}
                  >
                    Agent (CLI)
                  </button>
                </div>
              </FormField>
              <div className="action-group-fields">
                {repoExecutionMethod === "model" ? (
                  <ModelSelect
                    label="Model"
                    value={model}
                    onChange={setModel}
                    disabled={busy}
                    hint="Requires OPENROUTER_API_KEY on the API server."
                  />
                ) : (
                  <>
                    <FormField
                      label="Agent"
                      hint="Local CLI when agent command is left empty (Codex/OpenCode defaults)."
                    >
                      <select
                        value={agent}
                        disabled={busy}
                        onChange={(event) => setAgent(event.target.value as "codex" | "opencode" | "command")}
                      >
                        <option value="codex">Codex</option>
                        <option value="opencode">OpenCode</option>
                        <option value="command">Custom command</option>
                      </select>
                    </FormField>
                    <FormField
                      label="Profile"
                      hint="Harness depth and agent CLI time limit (static ~10m, smoke 2m, full longer). OpenCode/Codex need static or smoke; 90s is too short for real repos."
                    >
                      <select
                        value={profile}
                        disabled={busy}
                        onChange={(event) => setProfile(event.target.value as "static" | "smoke" | "full")}
                      >
                        <option value="static">Static</option>
                        <option value="smoke">Smoke</option>
                        <option value="full">Full</option>
                      </select>
                    </FormField>
                    <FormField
                      label="Sandbox"
                      hint="Command isolation policy for CLI runs (network, blocked paths, logged commands). Ignored for model runs."
                    >
                      <input
                        value={sandboxProfile}
                        disabled={busy}
                        onChange={(event) => setSandboxProfile(event.target.value)}
                      />
                    </FormField>
                    <FormField
                      label="Agent command"
                      hint="Shell command in the worktree. Matches CLI --agent-cmd when set."
                      className="wide-field"
                    >
                      <textarea
                        value={agentCmd}
                        disabled={busy}
                        placeholder={agentCmdPlaceholder}
                        onChange={(event) => setAgentCmd(event.target.value)}
                      />
                    </FormField>
                  </>
                )}
                <FormField
                  label="Output directory"
                  hint="Run artifacts directory. Auto-generated under runs/ when omitted."
                >
                  <input
                    value={repoOutputDir}
                    disabled={busy}
                    placeholder="Optional"
                    onChange={(event) => setRepoOutputDir(event.target.value)}
                  />
                </FormField>
              </div>
            </div>

            {repoTargets.error ? <span className="error-inline">{repoTargets.error}</span> : null}
            {repoFormError ? <span className="error-inline">{repoFormError}</span> : null}
            <button
              type="button"
              className="btn-primary"
              disabled={busy || (repoExecutionMethod === "agent" && agent === "command" && !agentCmd.trim())}
              onClick={() => void runRepoTask()}
            >
              {repoExecutionMethod === "model" ? "Run repo task (model)" : "Run repo task (agent)"}
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
