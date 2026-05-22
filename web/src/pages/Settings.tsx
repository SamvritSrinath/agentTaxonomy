import { getHealth } from "../api/client";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function SettingsPage() {
  const health = useAsyncResource(getHealth, []);

  return (
    <div className="page settings-page">
      <header className="page-header">
        <h2>Settings</h2>
        <p>Read-only diagnostics and CLI parity hints.</p>
      </header>
      <section className="panel">
        <h3>Backend</h3>
        <dl className="meta-dl">
          <dt>Status</dt>
          <dd>{health.data?.status ?? "—"}</dd>
          <dt>Database URL</dt>
          <dd>
            <code>{health.data?.database_url ?? "—"}</code>
          </dd>
          <dt>OPENROUTER_API_KEY</dt>
          <dd>{import.meta.env.VITE_OPENROUTER_CONFIGURED === "true" ? "set (client hint)" : "configure on server"}</dd>
        </dl>
      </section>
      <section className="panel">
        <h3>CLI parity</h3>
        <pre className="cli-hints">{`uv run catt build-catalog
uv run catt db migrate
uv run catt db bootstrap
uv run catt web --host 127.0.0.1 --port 8080`}</pre>
      </section>
    </div>
  );
}
