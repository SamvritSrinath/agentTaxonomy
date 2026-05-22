import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createPrompt, listCatalog, listPrompts } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function PromptsPage() {
  const prompts = useAsyncResource(listPrompts, []);
  const catalog = useAsyncResource(listCatalog, []);
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);
  const [instanceId, setInstanceId] = useState("");
  const [variantName, setVariantName] = useState("");
  const [promptText, setPromptText] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const generativeInstances = (catalog.data ?? []).filter((item) => item.task_mode === "generative_task");

  async function submitCreate() {
    setCreateError(null);
    if (!instanceId.trim() || !variantName.trim() || !promptText.trim()) {
      setCreateError("Instance, variant name, and prompt text are required.");
      return;
    }
    try {
      const created = await createPrompt({
        instance_id: instanceId.trim(),
        variant_name: variantName.trim(),
        prompt_text: promptText
      });
      prompts.reload();
      navigate(`/prompts/${created.id}`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="page prompts-page master-detail">
      <header className="page-header">
        <h2>Prompts</h2>
        <p>
          A <strong>prompt variant</strong> is one version of the task prompt for a catalog instance (e.g. canonical
          from bootstrap, or a custom ladder you create). Generation uses the selected variant&apos;s text, not the
          on-disk file unless you pick canonical.
        </p>
        <button type="button" className="text-button" onClick={() => setShowCreate((value) => !value)}>
          {showCreate ? "Cancel" : "+ New prompt variant"}
        </button>
      </header>
      {showCreate ? (
        <section className="panel create-prompt-panel">
          <h3>New prompt variant</h3>
          <p className="score-hint">Repo-task instances cannot be generated from the UI; pick a generative instance.</p>
          <div className="create-prompt-form">
            <label>
              Instance
              <select value={instanceId} onChange={(event) => setInstanceId(event.target.value)}>
                <option value="">Select instance…</option>
                {generativeInstances.map((item) => (
                  <option key={item.instance_id} value={item.instance_id}>
                    {item.instance_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Variant name
              <input
                value={variantName}
                onChange={(event) => setVariantName(event.target.value)}
                placeholder="e.g. stricter_logging_v1"
              />
            </label>
            <label className="full-width">
              Prompt text
              <textarea
                value={promptText}
                onChange={(event) => setPromptText(event.target.value)}
                rows={8}
                placeholder="Agent-facing task prompt…"
              />
            </label>
          </div>
          {createError ? <p className="error">{createError}</p> : null}
          <button type="button" onClick={() => void submitCreate()}>
            Create variant
          </button>
        </section>
      ) : null}
      <LoadingNotice loading={prompts.loading} error={prompts.error} label="Loading prompts…" />
      <div className="master-detail-grid">
        <aside className="master-list panel">
          <ul className="link-list">
            {(prompts.data ?? []).map((prompt) => (
              <li key={prompt.id}>
                <Link to={`/prompts/${prompt.id}`} className="prompt-link">
                  <strong>{prompt.instance_id}</strong>
                  <span>
                    {prompt.variant_name} · {prompt.skill_level}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </aside>
        <section className="detail-placeholder panel">
          <p>Select a prompt to view, edit, or generate from it.</p>
        </section>
      </div>
    </div>
  );
}
