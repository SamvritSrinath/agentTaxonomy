import { Link } from "react-router-dom";
import { bootstrapWorkbench, ingestCatalog, listJobs, listRuns } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { RunActions } from "../components/RunActions";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function DashboardPage() {
  const runs = useAsyncResource(listRuns, []);
  const jobs = useAsyncResource(() => listJobs({ limit: 20 }), []);
  const recent = (runs.data ?? []).slice(0, 5);
  const runningJobs = (jobs.data ?? []).filter((job) => job.status === "running" || job.status === "queued");
  const failedRuns = (runs.data ?? []).filter((run) => run.status === "failed").slice(0, 5);

  return (
    <div className="page dashboard-page">
      <header className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of runs, jobs, and quick actions.</p>
      </header>
      <div className="dashboard-cards">
        <article className="stat-card">
          <h3>Total runs</h3>
          <p className="stat-value">{runs.data?.length ?? "—"}</p>
        </article>
        <article className="stat-card">
          <h3>Jobs running</h3>
          <p className="stat-value">{runningJobs.length}</p>
        </article>
        <article className="stat-card">
          <h3>Recent failures</h3>
          <p className="stat-value">{failedRuns.length}</p>
        </article>
      </div>
      <LoadingNotice loading={runs.loading || jobs.loading} error={runs.error ?? jobs.error} label="Loading dashboard…" />
      <RunActions instanceId={recent[0]?.instance_id ?? null} runId={recent[0]?.id ?? null} onRefresh={runs.reload} />
      <section className="panel">
        <div className="panel-header-row">
          <h3>Recent runs</h3>
          <button type="button" onClick={() => bootstrapWorkbench().then(runs.reload)}>
            Bootstrap
          </button>
          <button type="button" onClick={() => ingestCatalog().then(runs.reload)}>
            Ingest catalog
          </button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Slug</th>
              <th>Instance</th>
              <th>Status</th>
              <th>Model</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((run) => (
              <tr key={run.id}>
                <td>
                  <Link to={`/runs/${run.id}`}>{run.run_slug}</Link>
                </td>
                <td>{run.instance_id ?? "—"}</td>
                <td>{run.status}</td>
                <td>{run.model_name ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
