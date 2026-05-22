import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns } from "../api/client";
import { Combobox } from "../components/Combobox";
import { LoadingNotice } from "../components/LoadingNotice";
import { parseSkillFromInstanceId, skillLevelRank } from "../config/skillLevel";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function RunsPage() {
  const runs = useAsyncResource(listRuns, []);
  const [statusFilter, setStatusFilter] = useState("");
  const [instanceFilter, setInstanceFilter] = useState("");
  const [taskModeFilter, setTaskModeFilter] = useState("");

  const statusOptions = useMemo(() => {
    const values = new Set((runs.data ?? []).map((r) => r.status).filter(Boolean));
    return [...values].sort().map((v) => ({ value: v, label: v }));
  }, [runs.data]);

  const instancePrefixOptions = useMemo(() => {
    const prefixes = new Set<string>();
    for (const run of runs.data ?? []) {
      const id = run.instance_id ?? "";
      if (!id) continue;
      const parts = id.split("__");
      prefixes.add(parts[0]);
      if (parts.length > 1) prefixes.add(`${parts[0]}__`);
    }
    return [...prefixes].sort().map((v) => ({ value: v, label: v }));
  }, [runs.data]);

  const taskModeOptions = useMemo(() => {
    const values = new Set((runs.data ?? []).map((r) => r.task_mode).filter(Boolean) as string[]);
    return [{ value: "", label: "All modes" }, ...[...values].sort().map((v) => ({ value: v, label: v }))];
  }, [runs.data]);

  const filtered = useMemo(() => {
    const rows = (runs.data ?? []).filter((run) => {
      if (statusFilter && run.status !== statusFilter) return false;
      if (instanceFilter && !(run.instance_id ?? "").startsWith(instanceFilter)) return false;
      if (taskModeFilter && run.task_mode !== taskModeFilter) return false;
      return true;
    });
    return rows.sort((a, b) => {
      const skillA = skillLevelRank(parseSkillFromInstanceId(a.instance_id));
      const skillB = skillLevelRank(parseSkillFromInstanceId(b.instance_id));
      if (skillA !== skillB) return skillA - skillB;
      const instCmp = (a.instance_id ?? "").localeCompare(b.instance_id ?? "");
      if (instCmp !== 0) return instCmp;
      const ingestedA = a.ingested_at ?? "";
      const ingestedB = b.ingested_at ?? "";
      return ingestedB.localeCompare(ingestedA);
    });
  }, [runs.data, statusFilter, instanceFilter, taskModeFilter]);

  return (
    <div className="page runs-page">
      <header className="page-header runs-page-header">
        <h2>Runs</h2>
        <p>Filterable table of indexed agent executions. Open a run for generate and judge actions.</p>
      </header>
      <LoadingNotice loading={runs.loading} error={runs.error} label="Loading runs…" />
      <div className="filters-row" aria-label="Run filters">
        <Combobox
          label="Status"
          value={statusFilter}
          options={[{ value: "", label: "All statuses" }, ...statusOptions]}
          onChange={setStatusFilter}
          placeholder="e.g. succeeded"
          allowCustomValue
        />
        <Combobox
          label="Instance prefix"
          value={instanceFilter}
          options={[{ value: "", label: "All instances" }, ...instancePrefixOptions]}
          onChange={setInstanceFilter}
          allowCustomValue
        />
        <Combobox
          label="Task mode"
          value={taskModeFilter}
          options={taskModeOptions}
          onChange={setTaskModeFilter}
        />
      </div>
      {!runs.loading && !runs.error ? (
        <>
          <p className="runs-results-meta">
            Showing {filtered.length} of {(runs.data ?? []).length} run{(runs.data ?? []).length === 1 ? "" : "s"}
          </p>
          <div className="panel runs-table-panel">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Slug</th>
                  <th>Instance</th>
                  <th>Skill</th>
                  <th>Model</th>
                  <th>Status</th>
                  <th>Mode</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      No runs match the current filters.
                    </td>
                  </tr>
                ) : (
                  filtered.map((run) => (
                    <tr key={run.id}>
                      <td>
                        <Link to={`/runs/${run.id}`}>{run.run_slug}</Link>
                      </td>
                      <td>{run.instance_id ?? "—"}</td>
                      <td>{parseSkillFromInstanceId(run.instance_id) ?? "—"}</td>
                      <td>{run.model_name ?? "—"}</td>
                      <td>
                        <span className={`status-badge status-${run.status}`}>{run.status}</span>
                      </td>
                      <td>{run.task_mode ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
