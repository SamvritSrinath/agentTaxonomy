import { useState } from "react";
import { exportTable } from "../api/client";

const EXPORTS = [
  {
    name: "runs",
    label: "Runs CSV",
    description: "One row per indexed run (slug, instance, model, status, paths)."
  },
  {
    name: "findings",
    label: "Findings CSV",
    description: "Security and quality findings linked to runs and evaluations."
  },
  {
    name: "evaluations",
    label: "Evaluations CSV",
    description: "Evaluation records (outcomes, evidence conditions, adjudication fields)."
  },
  {
    name: "wide",
    label: "Analysis wide CSV",
    description: "Joined run + evaluation + score + instance columns for notebooks (written as analysis.csv)."
  }
] as const;

export function ExportsPage() {
  const [lastPath, setLastPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runExport(name: string) {
    setError(null);
    try {
      const result = await exportTable(name);
      setLastPath(result.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="page exports-page">
      <header className="page-header">
        <h2>Exports</h2>
        <p>
          Four separate CSV exports (not a single zip). Each button writes a file under{" "}
          <code>data_dir/exports/</code> on the server and returns the path below.
        </p>
      </header>
      <ul className="export-descriptions">
        {EXPORTS.map((item) => (
          <li key={item.name}>
            <strong>{item.label}</strong> — {item.description}
          </li>
        ))}
      </ul>
      <div className="toolbar-actions">
        {EXPORTS.map((item) => (
          <button key={item.name} type="button" onClick={() => void runExport(item.name)}>
            {item.label}
          </button>
        ))}
      </div>
      {lastPath ? (
        <p className="export-path">
          Wrote <code>{lastPath}</code>
        </p>
      ) : null}
      {error ? <div className="error">{error}</div> : null}
    </div>
  );
}
