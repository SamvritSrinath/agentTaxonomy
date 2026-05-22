import { Link } from "react-router-dom";
import { listJobs } from "../api/client";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function JobsPage() {
  const jobs = useAsyncResource(() => listJobs({ limit: 100 }), []);

  return (
    <div className="page jobs-page">
      <header className="page-header">
        <h2>Jobs</h2>
        <p>Async workbench queue (generate, judge, ingest, bootstrap).</p>
      </header>
      <table className="data-table">
        <thead>
          <tr>
            <th>Kind</th>
            <th>Status</th>
            <th>Phase</th>
            <th>Run</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {(jobs.data ?? []).map((job) => {
            const runId = (job.metadata_json?.run_id as string | undefined) ?? null;
            return (
              <tr key={job.id}>
                <td>{job.kind}</td>
                <td>{job.status}</td>
                <td>{job.phase ?? "—"}</td>
                <td>{runId ? <Link to={`/runs/${runId}`}>{runId.slice(0, 8)}…</Link> : "—"}</td>
                <td>{job.created_at ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
