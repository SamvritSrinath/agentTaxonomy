import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getInstance, updateCanonicalPrompt } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { useAsyncResource } from "../hooks/useAsyncResource";

export interface CatalogPromptEditorPaneProps {
  instanceId: string;
  onSaved?: () => void;
}

export function CatalogPromptEditorPane({ instanceId, onSaved }: CatalogPromptEditorPaneProps) {
  const instance = useAsyncResource(() => getInstance(instanceId), [instanceId]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (instance.data?.agent_prompt) {
      setText(instance.data.agent_prompt);
    }
  }, [instanceId, instance.data?.agent_prompt]);

  async function save() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await updateCanonicalPrompt(instanceId, {
        prompt_text: text,
        rebuild_catalog: true,
        ingest_catalog: true
      });
      setMessage("Saved to catalog and re-indexed.");
      instance.reload();
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const label = instance.data?.skill_level ?? "Catalog";

  return (
    <div className="prompt-editor-pane catalog-prompt-pane">
      <LoadingNotice loading={instance.loading} error={instance.error} label="Loading catalog prompt…" />
      {instance.data ? (
        <>
          <header className="prompt-editor-header">
            <h3>{label}</h3>
            <p className="prompt-editor-meta">
              Catalog · <Link to={`/instances/${instanceId}`}>{instanceId}</Link>
              {instance.data.prompt_path ? (
                <>
                  {" · "}
                  <code>{instance.data.prompt_path}</code>
                </>
              ) : null}
            </p>
            <p className="detail-pane-desc">
              Writes to <code>benchmark/task_catalog/…/levels/{instance.data.skill_level}.md</code> and rebuilds the
              generated catalog.
            </p>
          </header>

          <label className="prompt-editor-field prompt-editor-field-grow">
            Prompt text
            <textarea
              className="prompt-editor-textarea"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={16}
              spellCheck={false}
            />
          </label>

          <footer className="prompt-editor-footer">
            <div className="prompt-editor-actions">
              <button type="button" className="btn-primary" disabled={busy} onClick={() => void save()}>
                Save catalog prompt
              </button>
            </div>
            {message ? <p className="toolbar-success">{message}</p> : null}
            {error ? <p className="error">{error}</p> : null}
          </footer>
        </>
      ) : null}
    </div>
  );
}
