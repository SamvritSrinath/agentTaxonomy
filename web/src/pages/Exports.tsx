import { useState } from "react";
import { exportTable } from "../api/client";

const EXPORTS = [
  { name: "runs", label: "Runs CSV" },
  { name: "findings", label: "Findings CSV" },
  { name: "evaluations", label: "Evaluations CSV" },
  { name: "wide", label: "Analysis wide CSV" }
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
        <p>Generate analysis CSV files on the server.</p>
      </header>
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
