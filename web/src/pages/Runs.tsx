import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns } from "../api/client";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function RunsPage() {
  const runs = useAsyncResource(listRuns, []);
  const [statusFilter, setStatusFilter] = useState("");
  const [instanceFilter, setInstanceFilter] = useState("");
  const [taskModeFilter, setTaskModeFilter] = useState("");

  const filtered = useMemo(() => {
    return (runs.data ?? []).filter((run) => {
      if (statusFilter && run.status !== statusFilter) return false;
      if (instanceFilter && !(run.instance_id ?? "").startsWith(instanceFilter)) return false;
      if (taskModeFilter && run.task_mode !== taskModeFilter) return false;
      return true;
    });
  }, [runs.data, statusFilter, instanceFilter, taskModeFilter]);

  return (
    <div className="page runs-page">
      <header className="page-header">
        <h2>Runs</h2>
        <p>Filterable table of indexed agent executions.</p>
      </header>
      <div className="filters-row">
        <label>
          Status
          <input value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} placeholder="e.g. succeeded" />
        </label>
        <label>
          Instance prefix
          <input value={instanceFilter} onChange={(e) => setInstanceFilter(e.target.value)} />
        </label>
        <label>
          Task mode
          <select value={taskModeFilter} onChange={(e) => setTaskModeFilter(e.target.value)}>
            <option value="">All</option>
            <option value="generative_task">generative_task</option>
            <option value="repo_task">repo_task</option>
          </select>
        </label>
      </div>
      {runs.error ? <div className="error">{runs.error}</div> : null}
      <table className="data-table">
        <thead>
          <tr>
            <th>Slug</th>
            <th>Instance</th>
            <th>Model</th>
            <th>Status</th>
            <th>Mode</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((run) => (
            <tr key={run.id}>
              <td>
                <Link to={`/runs/${run.id}`}>{run.run_slug}</Link>
              </td>
              <td>{run.instance_id ?? "—"}</td>
              <td>{run.model_name ?? "—"}</td>
              <td>
                <span className={`status-badge status-${run.status}`}>{run.status}</span>
              </td>
              <td>{run.task_mode ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
