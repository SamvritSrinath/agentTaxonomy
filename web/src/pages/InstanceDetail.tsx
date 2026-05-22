import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { bootstrapWorkbench, generateForInstance, getInstance, listPrompts } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { ModelSelect } from "../components/ModelSelect";
import { PromptSelect } from "../components/PromptSelect";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function InstanceDetailPage() {
  const { instanceId = "" } = useParams();
  const instance = useAsyncResource(() => getInstance(instanceId), [instanceId]);
  const prompts = useAsyncResource(() => listPrompts({ instance_id: instanceId }), [instanceId]);
  const [model, setModel] = useState("moonshotai/kimi-k2.5");
  const [promptId, setPromptId] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const first = prompts.data?.[0]?.id ?? "";
    setPromptId((current) => current || first);
  }, [prompts.data]);

  async function generate() {
    if (!instanceId || instance.data?.task_mode === "repo_task") return;
    const job = await generateForInstance(instanceId, {
      model,
      prompt_id: promptId || undefined
    });
    setStatus(`Queued job ${job.job_id}`);
  }

  const isRepoTask = instance.data?.task_mode === "repo_task";

  return (
    <div className="page instance-detail-page">
      <header className="page-header">
        <Link to="/instances">← Instances</Link>
        <h2>{instanceId}</h2>
      </header>
      <LoadingNotice loading={instance.loading} error={instance.error} />
      {instance.data ? (
        <>
          <dl className="meta-dl">
            <dt>Task mode</dt>
            <dd>{instance.data.task_mode}</dd>
            <dt>Skill level</dt>
            <dd>{instance.data.skill_level}</dd>
            <dt>Subject area</dt>
            <dd>{instance.data.subject_area}</dd>
          </dl>
          {instance.data.agent_prompt ? (
            <pre className="prompt-body">{instance.data.agent_prompt}</pre>
          ) : (
            <div className="empty-state">
              <p>No catalog prompt loaded.</p>
              <button type="button" onClick={() => bootstrapWorkbench().then(() => instance.reload())}>
                Run bootstrap
              </button>
            </div>
          )}
          <div className="toolbar-actions">
            <PromptSelect
              label="Prompt variant"
              prompts={prompts.data ?? []}
              value={promptId}
              onChange={setPromptId}
              disabled={isRepoTask}
            />
            <ModelSelect label="Model" value={model} onChange={setModel} disabled={isRepoTask} />
            <button
              type="button"
              disabled={isRepoTask}
              title={isRepoTask ? "repo_task generate not supported in UI; use catt experiment run" : undefined}
              onClick={() => void generate()}
            >
              Generate
            </button>
          </div>
          {status ? <p className="toolbar-phase">{status}</p> : null}
        </>
      ) : null}
    </div>
  );
}
