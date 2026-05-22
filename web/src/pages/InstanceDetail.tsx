import { Link, useParams } from "react-router-dom";
import { getInstance } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { RunActions } from "../components/RunActions";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function InstanceDetailPage() {
  const { instanceId = "" } = useParams();
  const instance = useAsyncResource(() => getInstance(instanceId), [instanceId]);

  const reloadAll = () => instance.reload();

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
              <p>No catalog prompt loaded. Run bootstrap from the toolbar.</p>
            </div>
          )}
          <RunActions
            instanceId={instanceId}
            runId={null}
            taskMode={instance.data.task_mode}
            runDir={null}
            onRefresh={reloadAll}
            navigateOnGenerate
            scope="instance"
          />
        </>
      ) : null}
    </div>
  );
}
