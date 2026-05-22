import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { duplicatePrompt, generateForPrompt, getPrompt, updatePrompt } from "../api/client";
import { DEFAULT_GENERATION_MODEL } from "../config/models";
import { ModelSelect } from "./ModelSelect";
import { isCatalogShadowPrompt, promptDisplayLabel } from "../utils/promptLabels";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { useJobRunner } from "../hooks/useJobRunner";

export interface PromptEditorPaneProps {
  promptId: string;
  onSaved?: () => void;
  onNavigate?: (promptId: string) => void;
  onOpenCatalog?: (instanceId: string) => void;
}

export function PromptEditorPane({
  promptId,
  onSaved,
  onNavigate,
  onOpenCatalog
}: PromptEditorPaneProps) {
  const prompt = useAsyncResource(() => getPrompt(promptId), [promptId]);
  const [text, setText] = useState("");
  const [variantName, setVariantName] = useState("");
  const [model, setModel] = useState(DEFAULT_GENERATION_MODEL);
  const [message, setMessage] = useState<string | null>(null);
  const { busy, phase, error, runJob } = useJobRunner({
    onRefresh: () => {
      prompt.reload();
      onSaved?.();
    },
    navigateOnGenerate: true
  });

  useEffect(() => {
    if (prompt.data) {
      setText(prompt.data.prompt_text);
      setVariantName(prompt.data.variant_name);
    }
  }, [promptId, prompt.data?.prompt_text, prompt.data?.variant_name]);

  async function save() {
    await updatePrompt(promptId, { prompt_text: text, variant_name: variantName });
    setMessage("Saved");
    prompt.reload();
    onSaved?.();
  }

  async function duplicate() {
    const copy = await duplicatePrompt(promptId);
    onNavigate?.(copy.id);
  }

  if (!promptId) {
    return <p className="empty-state">Select a prompt variant from the tree.</p>;
  }

  if (prompt.loading) {
    return <p className="loading-notice">Loading prompt…</p>;
  }

  if (prompt.error) {
    return <div className="error">{prompt.error}</div>;
  }

  const data = prompt.data;
  if (!data) {
    return <p className="empty-state">Prompt not found.</p>;
  }

  if (isCatalogShadowPrompt(data)) {
    return (
      <div className="prompt-editor-pane">
        <p className="score-compare-banner">
          This DB row duplicates the on-disk catalog prompt. Click <strong>{data.skill_level}</strong> in the tree to
          edit the catalog, or run <strong>Bootstrap workbench</strong> on the Dashboard to remove legacy shadow rows.
        </p>
        <button
          type="button"
          className="btn-primary"
          onClick={() => onOpenCatalog?.(data.instance_id)}
        >
          Open {data.skill_level} catalog prompt
        </button>
      </div>
    );
  }

  return (
    <div className="prompt-editor-pane">
      <header className="prompt-editor-header">
        <h3>{promptDisplayLabel(data)}</h3>
        <p className="prompt-editor-meta">
          <Link to={`/instances/${data.instance_id}`}>{data.instance_id}</Link>
          {" · "}
          {data.skill_level}
        </p>
      </header>

      <label className="prompt-editor-field">
        Variant name
        <input
          value={variantName}
          onChange={(event) => setVariantName(event.target.value)}
          placeholder="e.g. stricter_logging_v1"
        />
      </label>

      <label className="prompt-editor-field prompt-editor-field-grow">
        Prompt text
        <textarea
          className="prompt-editor-textarea"
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={16}
          spellCheck={false}
        />
      </label>

      <footer className="prompt-editor-footer">
        <div className="prompt-editor-actions">
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void save()}>
            Save
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => void duplicate()}>
            Duplicate
          </button>
        </div>
        <div className="prompt-editor-generate">
          <ModelSelect label="Model" value={model} onChange={setModel} disabled={busy} />
          <button
            type="button"
            className="btn-primary"
            disabled={busy}
            onClick={() => void runJob(() => generateForPrompt(promptId, { model }))}
          >
            Generate from prompt
          </button>
        </div>
        {phase ? <p className="toolbar-phase">Phase: {phase}</p> : null}
        {message ? <p className="toolbar-success">{message}</p> : null}
        {error ? <p className="error-inline">{error}</p> : null}
      </footer>
    </div>
  );
}
