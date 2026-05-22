import { Link } from "react-router-dom";
import { listCatalog } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function InstancesPage() {
  const catalog = useAsyncResource(listCatalog, []);

  return (
    <div className="page instances-page">
      <header className="page-header">
        <h2>Instances</h2>
        <p>Benchmark catalog instances.</p>
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
          {(catalog.data ?? []).map((item) => (
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
