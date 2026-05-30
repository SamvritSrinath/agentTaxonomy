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
            <dt>Variant</dt>
            <dd>{formatVariant(instance.data.task_variant)}</dd>
            <dt>Skill level</dt>
            <dd>{instance.data.skill_level}</dd>
            <dt>Subject area</dt>
            <dd>{instance.data.subject_area}</dd>
            <dt>Risk class</dt>
            <dd>{instance.data.consequence_class ?? "—"}</dd>
          </dl>
          {instance.data.task_mode === "repo_task" ? <InstanceSafetyPanel instance={instance.data} /> : null}
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

function InstanceSafetyPanel({ instance }: { instance: NonNullable<Awaited<ReturnType<typeof getInstance>>> }) {
  const safety = instance.repo_safety;
  const allowedPaths = safety?.allowed_paths ?? [];
  const forbiddenPaths = safety?.forbidden_paths ?? [];
  return (
    <section className="panel repo-safety-panel">
      <h3>Repo Safety Contract</h3>
      <dl className="meta-dl">
        <dt>Confirmation required</dt>
        <dd>{instance.confirmation_required ? "Yes" : "No"}</dd>
        <dt>Sandbox profile</dt>
        <dd>{instance.sandbox_profile ?? "—"}</dd>
        <dt>Repo fixture</dt>
        <dd>{instance.repo_fixture_path ?? "—"}</dd>
        <dt>Allowed paths</dt>
        <dd>{allowedPaths.length ? allowedPaths.join(", ") : "—"}</dd>
        <dt>Forbidden paths</dt>
        <dd>{forbiddenPaths.length ? forbiddenPaths.join(", ") : "—"}</dd>
        <dt>Expected behavior</dt>
        <dd>{safety?.expected_behavior ?? "—"}</dd>
      </dl>
      {(instance.expected_repo_outcomes ?? []).length ? (
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>Expected action</th>
              <th>Path</th>
              <th>Modify?</th>
            </tr>
          </thead>
          <tbody>
            {(instance.expected_repo_outcomes ?? []).map((outcome) => (
              <tr key={outcome.id}>
                <td>{outcome.expected_action.replaceAll("_", " ")}</td>
                <td>{outcome.path ?? "—"}</td>
                <td>{outcome.should_modify ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

function formatVariant(variant: string | null | undefined) {
  if (!variant) return "—";
  return variant.replaceAll("_", " ");
}
