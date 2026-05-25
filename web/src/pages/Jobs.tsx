import { useEffect } from "react";
import { Link } from "react-router-dom";
import { listJobs } from "../api/client";
import {
  formatJobKind,
  isLlmWorkbenchJob,
  jobDetailLine,
  resolveJobRunId
} from "../config/jobs";
import { useAsyncResource } from "../hooks/useAsyncResource";

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

  const filtered = (jobs.data ?? []).filter(isLlmWorkbenchJob);

  return (
    <div className="page jobs-page">
      <header className="page-header">
        <h2>Jobs</h2>
        <p>
          Generative runs, repo-task generation (model or agent), and judge pipelines. Refreshes every 5s.
        </p>
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
            <th>Detail</th>
            <th>Run</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 ? (
            <tr>
              <td colSpan={6} className="table-empty">
                No LLM jobs yet. Start a generative generate, repo run (model/agent), or judge from a run page.
              </td>
            </tr>
          ) : null}
          {filtered.map((job) => {
            const runId = resolveJobRunId(job);
            const detail = jobDetailLine(job);
            return (
              <tr key={job.id}>
                <td>{formatJobKind(job)}</td>
                <td>
                  {job.status}
                  {job.status === "failed" && job.error ? (
                    <span className="job-error-hint" title={job.error}>
                      {" "}
                      (error)
                    </span>
                  ) : null}
                </td>
                <td>{job.phase ?? "—"}</td>
                <td>{detail ?? "—"}</td>
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
