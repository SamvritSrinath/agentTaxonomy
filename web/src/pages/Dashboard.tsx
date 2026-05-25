import { useState } from "react";
import { Link } from "react-router-dom";
import { bootstrapWorkbench, ingestCatalog, listJobs, listRuns } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { Spinner } from "../components/Spinner";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { isLlmWorkbenchJob, isRunningJob } from "../config/jobs";
import { useJobRunner } from "../hooks/useJobRunner";

export function DashboardPage() {
  const runs = useAsyncResource(listRuns, []);
  const jobs = useAsyncResource(() => listJobs({ limit: 20 }), []);
  const { busy, phase, error, runJob } = useJobRunner({ onRefresh: () => runs.reload() });
  const [catalogMessage, setCatalogMessage] = useState<string | null>(null);
  const [catalogBusy, setCatalogBusy] = useState(false);
  const recent = (runs.data ?? []).slice(0, 5);
  const runningJobs = (jobs.data ?? []).filter((job) => isLlmWorkbenchJob(job) && isRunningJob(job));
  const failedRuns = (runs.data ?? []).filter((run) => run.status === "failed").slice(0, 5);

  async function ingestCatalogAction() {
    setCatalogBusy(true);
    setCatalogMessage(null);
    try {
      await ingestCatalog();
      setCatalogMessage("Catalog ingested.");
      await runs.reload();
    } catch (err) {
      setCatalogMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setCatalogBusy(false);
    }
  }

  return (
    <div className="page dashboard-page">
      <header className="page-header">
        <h2>Dashboard</h2>
        <p>
          Workbench overview. Index the catalog here, then run generative or repo tasks and judge from Run or Instance
          pages.
        </p>
      </header>
      <div className="dashboard-cards">
        <article className="stat-card">
          <h3>Total runs</h3>
          <p className="stat-value">{runs.data?.length ?? "—"}</p>
        </article>
        <article className="stat-card">
          <h3>LLM jobs running</h3>
          <p className="stat-value">{runningJobs.length}</p>
        </article>
        <article className="stat-card">
          <h3>Recent failures</h3>
          <p className="stat-value">{failedRuns.length}</p>
        </article>
      </div>
      <LoadingNotice loading={runs.loading || jobs.loading} error={runs.error ?? jobs.error} label="Loading dashboard…" />
      <section className="panel dashboard-setup">
        <h3>Setup</h3>
        <p className="score-hint">
          Index catalog and prompt variants before experiments. Browse{" "}
          <Link to="/instances">instances</Link> or <Link to="/prompts">prompts</Link>.
        </p>
        <div className="dashboard-setup-actions">
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void runJob(() => bootstrapWorkbench({}))}>
            Bootstrap workbench
          </button>
          <button type="button" className="btn-secondary" disabled={catalogBusy} onClick={() => void ingestCatalogAction()}>
            Ingest catalog
          </button>
          {busy ? <Spinner label={phase ? `Bootstrap: ${phase}` : "Bootstrap…"} size="sm" /> : null}
          {catalogBusy ? <Spinner label="Ingesting catalog…" size="sm" /> : null}
        </div>
        {error ? <p className="error">{error}</p> : null}
        {catalogMessage ? <p className="toolbar-success">{catalogMessage}</p> : null}
      </section>
      <section className="panel">
        <div className="panel-header-row">
          <h3>Recent runs</h3>
          <Link to="/runs">View all runs →</Link>
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
                <td>
                  {run.instance_id ? <Link to={`/instances/${run.instance_id}`}>{run.instance_id}</Link> : "—"}
                </td>
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
