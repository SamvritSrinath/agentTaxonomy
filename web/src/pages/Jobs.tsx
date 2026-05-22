import { useEffect } from "react";
import { Link } from "react-router-dom";
import { listJobs } from "../api/client";
import { useAsyncResource } from "../hooks/useAsyncResource";

const LLM_JOB_KINDS = new Set(["generate", "judge"]);

export function JobsPage() {
  const jobs = useAsyncResource(() => listJobs({ limit: 100 }), []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void jobs.reload();
      }
    }, 5000);
    return () => window.clearInterval(interval);
  }, [jobs.reload]);

  const filtered = (jobs.data ?? []).filter((job) => LLM_JOB_KINDS.has(job.kind));

  return (
    <div className="page jobs-page">
      <header className="page-header">
        <h2>Jobs</h2>
        <p>LLM generate and judge pipeline jobs (refreshes every 5s).</p>
        <button type="button" className="text-button-inline" onClick={() => void jobs.reload()}>
          Refresh now
        </button>
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
          {filtered.map((job) => {
            const runId =
              (job.metadata_json?.run_id as string | undefined) ??
              ((job.result as Record<string, unknown> | undefined)?.run_id as string | undefined) ??
              null;
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
