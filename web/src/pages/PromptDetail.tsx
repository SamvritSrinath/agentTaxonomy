import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { duplicatePrompt, generateForPrompt, getPrompt, updatePrompt } from "../api/client";
import { LoadingNotice } from "../components/LoadingNotice";
import { ModelSelect } from "../components/ModelSelect";
import { useAsyncResource } from "../hooks/useAsyncResource";

export function PromptDetailPage() {
  const { promptId = "" } = useParams();
  const prompt = useAsyncResource(() => getPrompt(promptId), [promptId]);
  const [text, setText] = useState("");
  const [model, setModel] = useState("moonshotai/kimi-k2.5");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (prompt.data?.prompt_text) {
      setText(prompt.data.prompt_text);
    }
  }, [promptId, prompt.data?.prompt_text]);

  async function save() {
    if (!promptId) return;
    await updatePrompt(promptId, { prompt_text: text });
    setMessage("Saved");
    prompt.reload();
  }

  async function duplicate() {
    if (!promptId) return;
    const copy = await duplicatePrompt(promptId);
    window.location.href = `/prompts/${copy.id}`;
  }

  async function generate() {
    if (!promptId) return;
    const job = await generateForPrompt(promptId, { model });
    setMessage(`Generate queued for this prompt: ${job.job_id}`);
  }

  if (!promptId) {
    return <p className="empty-state">No prompt selected.</p>;
  }

  return (
    <div className="page prompt-detail-page">
      <header className="page-header">
        <Link to="/prompts">← Prompts</Link>
        <h2>{prompt.data?.instance_id ?? "Prompt"}</h2>
        <p>{prompt.data?.skill_level ?? prompt.data?.variant_name ?? ""}</p>
      </header>
      <LoadingNotice loading={prompt.loading} error={prompt.error} />
      <textarea className="prompt-editor" value={text} onChange={(e) => setText(e.target.value)} rows={18} />
      <div className="toolbar-actions">
        <button type="button" onClick={() => void save()}>
          Save
        </button>
        <button type="button" onClick={() => void duplicate()}>
          Duplicate
        </button>
        <ModelSelect label="Model" value={model} onChange={setModel} />
        <button type="button" onClick={() => void generate()}>
          Generate from prompt
        </button>
      </div>
      {message ? <p className="toolbar-phase">{message}</p> : null}
    </div>
  );
}
