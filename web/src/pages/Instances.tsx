import { useMemo } from "react";
import { Link } from "react-router-dom";
import { listCatalog } from "../api/client";
import { skillLevelRank } from "../config/skillLevel";
import { LoadingNotice } from "../components/LoadingNotice";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function InstancesPage() {
  const catalog = useAsyncResource(listCatalog, []);

  const sorted = useMemo(() => {
    return [...(catalog.data ?? [])].sort((a, b) => {
      const taskCmp =
        a.task_id.localeCompare(b.task_id) ||
        (a.subject_area ?? "").localeCompare(b.subject_area ?? "");
      if (taskCmp !== 0) return taskCmp;
      const skillCmp = skillLevelRank(a.skill_level) - skillLevelRank(b.skill_level);
      if (skillCmp !== 0) return skillCmp;
      return a.instance_id.localeCompare(b.instance_id);
    });
  }, [catalog.data]);

  return (
    <div className="page instances-page">
      <header className="page-header">
        <h2>Instances</h2>
        <p>Benchmark catalog instances, grouped by task and skill level (beginner → expert).</p>
      </header>
      <LoadingNotice loading={catalog.loading} error={catalog.error} label="Loading catalog…" />
      <table className="data-table">
        <thead>
          <tr>
            <th>Instance</th>
            <th>Task</th>
            <th>Mode</th>
            <th>Level</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item) => (
            <tr key={item.instance_id}>
              <td>
                <Link to={`/instances/${item.instance_id}`}>{item.instance_id}</Link>
              </td>
              <td>{item.task_id}</td>
              <td>{item.task_mode}</td>
              <td>{item.skill_level}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
