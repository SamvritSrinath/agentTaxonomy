import { useMemo, useState } from "react";
import { createCatalogTask } from "../api/client";

export interface CreateCatalogTaskPanelProps {
  existingTaskIds: string[];
  onCreated: (taskId: string) => void;
  onCancel: () => void;
}

export function CreateCatalogTaskPanel({ existingTaskIds, onCreated, onCancel }: CreateCatalogTaskPanelProps) {
  const [taskId, setTaskId] = useState("");
  const [subjectArea, setSubjectArea] = useState("");
  const [problemClass, setProblemClass] = useState("");
  const [beginnerPrompt, setBeginnerPrompt] = useState("");
  const [intermediatePrompt, setIntermediatePrompt] = useState("");
  const [expertPrompt, setExpertPrompt] = useState("");
  const [sameForAllLevels, setSameForAllLevels] = useState(true);
  const [language, setLanguage] = useState("python");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedId = useMemo(
    () => taskId.trim().toLowerCase().replace(/-/g, "_").replace(/\s+/g, "_"),
    [taskId]
  );
  const idConflict = normalizedId && existingTaskIds.includes(normalizedId);

  async function submit() {
    setError(null);
    if (!normalizedId || !subjectArea.trim() || !problemClass.trim() || !beginnerPrompt.trim()) {
      setError("Task id, subject area, problem class, and beginner prompt are required.");
      return;
    }
    if (idConflict) {
      setError(`Task id "${normalizedId}" already exists.`);
      return;
    }
    setBusy(true);
    try {
      const result = await createCatalogTask({
        task_id: normalizedId,
        subject_area: subjectArea.trim(),
        problem_class: problemClass.trim(),
        beginner_prompt: beginnerPrompt,
        intermediate_prompt: sameForAllLevels ? undefined : intermediatePrompt || undefined,
        expert_prompt: sameForAllLevels ? undefined : expertPrompt || undefined,
        language: language.trim() || "python",
        rebuild_catalog: true,
        ingest_catalog: true
      });
      onCreated(result.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="create-prompt-panel create-catalog-task-panel">
      <header className="detail-pane-header">
        <h3>New catalog task</h3>
        <p className="detail-pane-desc">
          Creates <code>benchmark/task_catalog/subject_areas/&lt;task_id&gt;/</code> with beginner, intermediate, and
          expert prompts, then rebuilds and ingests the catalog.
        </p>
      </header>
      <div className="create-prompt-form">
        <label>
          Task id
          <input
            value={taskId}
            onChange={(e) => setTaskId(e.target.value)}
            placeholder="e.g. my_new_api_task"
          />
          {normalizedId ? (
            <span className="score-hint">
              Folder: <code>{normalizedId}</code>
              {idConflict ? " — already exists" : null}
            </span>
          ) : null}
        </label>
        <label>
          Subject area
          <input
            value={subjectArea}
            onChange={(e) => setSubjectArea(e.target.value)}
            placeholder="e.g. API design"
          />
        </label>
        <label>
          Problem class
          <input
            value={problemClass}
            onChange={(e) => setProblemClass(e.target.value)}
            placeholder="Short label for the task family"
          />
        </label>
        <label>
          Language
          <input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="python" />
        </label>
        <label className="full-width checkbox-row">
          <input
            type="checkbox"
            checked={sameForAllLevels}
            onChange={(e) => setSameForAllLevels(e.target.checked)}
          />
          Use beginner prompt for all skill levels (uncheck to customize)
        </label>
        <label className="full-width">
          Beginner prompt
          <textarea
            value={beginnerPrompt}
            onChange={(e) => setBeginnerPrompt(e.target.value)}
            rows={6}
            placeholder="Agent-facing task prompt for beginner level…"
          />
        </label>
        {!sameForAllLevels ? (
          <>
            <label className="full-width">
              Intermediate prompt
              <textarea
                value={intermediatePrompt}
                onChange={(e) => setIntermediatePrompt(e.target.value)}
                rows={5}
              />
            </label>
            <label className="full-width">
              Expert prompt
              <textarea
                value={expertPrompt}
                onChange={(e) => setExpertPrompt(e.target.value)}
                rows={5}
              />
            </label>
          </>
        ) : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="detail-pane-actions">
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void submit()}>
          Create task &amp; ingest catalog
        </button>
        <button type="button" className="btn-ghost" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </section>
  );
}
