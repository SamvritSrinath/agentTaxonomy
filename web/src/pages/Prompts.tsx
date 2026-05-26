import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createPrompt, listCatalog, listPrompts } from "../api/client";
import { CatalogPromptEditorPane } from "../components/CatalogPromptEditorPane";
import { Combobox } from "../components/Combobox";
import { CreateCatalogTaskPanel } from "../components/CreateCatalogTaskPanel";
import { LoadingNotice } from "../components/LoadingNotice";
import { PromptEditorPane } from "../components/PromptEditorPane";
import { PromptTree } from "../components/PromptTree";
import { useAsyncResource } from "../hooks/useAsyncResource";
import { isCatalogShadowPrompt } from "../utils/promptLabels";

type CreateMode = "none" | "variant" | "task";

export function PromptsPage() {
  const { promptId: routePromptId } = useParams();
  const navigate = useNavigate();
  const prompts = useAsyncResource(listPrompts, []);
  const catalog = useAsyncResource(listCatalog, []);
  const [selectedPromptId, setSelectedPromptId] = useState<string | null>(routePromptId ?? null);
  const [selectedCanonicalInstanceId, setSelectedCanonicalInstanceId] = useState<string | null>(null);
  const [createMode, setCreateMode] = useState<CreateMode>("none");
  const [instanceId, setInstanceId] = useState("");
  const [variantName, setVariantName] = useState("");
  const [promptText, setPromptText] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    if (!routePromptId) return;
    const match = (prompts.data ?? []).find((p) => p.id === routePromptId);
    if (match && isCatalogShadowPrompt(match)) {
      selectCanonical(match.instance_id);
      return;
    }
    setSelectedPromptId(routePromptId);
    setSelectedCanonicalInstanceId(null);
    setCreateMode("none");
  }, [routePromptId, prompts.data]);

  const instanceOptions = (catalog.data ?? []).map((item) => ({
    value: item.instance_id,
    label: item.instance_id
  }));

  const existingTaskIds = useMemo(() => {
    const ids = new Set<string>();
    for (const item of catalog.data ?? []) {
      if (item.task_id) {
        ids.add(item.task_id);
      }
    }
    return [...ids];
  }, [catalog.data]);

  function reloadAll() {
    void catalog.reload();
    void prompts.reload();
  }

  function selectPrompt(id: string) {
    setSelectedPromptId(id);
    setSelectedCanonicalInstanceId(null);
    setCreateMode("none");
    navigate(`/prompts/${id}`);
  }

  function selectCanonical(instId: string) {
    setSelectedCanonicalInstanceId(instId);
    setSelectedPromptId(null);
    setCreateMode("none");
    navigate("/prompts");
  }

  function openCreateVariant(instId = "") {
    setInstanceId(instId);
    setVariantName("");
    setPromptText("");
    setCreateMode("variant");
    setCreateError(null);
    setSelectedPromptId(null);
    setSelectedCanonicalInstanceId(null);
    navigate("/prompts");
  }

  function openCreateTask() {
    setCreateMode("task");
    setSelectedPromptId(null);
    setSelectedCanonicalInstanceId(null);
    navigate("/prompts");
  }

  function closeCreate() {
    setCreateMode("none");
    setCreateError(null);
  }

  async function submitCreateVariant() {
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
      await prompts.reload();
      setCreateMode("none");
      selectPrompt(created.id);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : String(err));
    }
  }

  function onTaskCreated(taskId: string) {
    setCreateMode("none");
    reloadAll();
    selectCanonical(`${taskId}__beginner`);
  }

  const detailContent = (() => {
    if (createMode === "task") {
      return (
        <CreateCatalogTaskPanel
          existingTaskIds={existingTaskIds}
          onCreated={onTaskCreated}
          onCancel={closeCreate}
        />
      );
    }
    if (createMode === "variant") {
      return (
        <section className="create-prompt-panel">
          <header className="detail-pane-header">
            <h3>New prompt variant</h3>
            <p className="detail-pane-desc">
              DB-backed experiment variants. The skill name in the tree (e.g. beginner) is the on-disk catalog prompt.
            </p>
          </header>
          <div className="create-prompt-form">
            <Combobox
              label="Instance"
              value={instanceId}
              options={[{ value: "", label: "Select instance…" }, ...instanceOptions]}
              onChange={setInstanceId}
            />
            <label>
              Variant name
              <input
                value={variantName}
                onChange={(event) => setVariantName(event.target.value)}
                placeholder="e.g. stricter_logging_v1"
              />
            </label>
            <label className="full-width prompt-editor-field">
              Prompt text
              <textarea
                className="prompt-editor-textarea"
                value={promptText}
                onChange={(event) => setPromptText(event.target.value)}
                rows={12}
                placeholder="Agent-facing task prompt…"
              />
            </label>
          </div>
          {createError ? <p className="error">{createError}</p> : null}
          <div className="detail-pane-actions">
            <button type="button" className="btn-primary" onClick={() => void submitCreateVariant()}>
              Create variant
            </button>
            <button type="button" className="btn-ghost" onClick={closeCreate}>
              Cancel
            </button>
          </div>
        </section>
      );
    }
    if (selectedPromptId) {
      return (
            <PromptEditorPane
              promptId={selectedPromptId}
              onSaved={() => void prompts.reload()}
              onNavigate={selectPrompt}
              onOpenCatalog={selectCanonical}
            />
      );
    }
    if (selectedCanonicalInstanceId) {
      return <CatalogPromptEditorPane instanceId={selectedCanonicalInstanceId} onSaved={reloadAll} />;
    }
    return (
      <div className="prompts-empty-state">
        <h3>Select or create</h3>
        <p>
          Use the tree: click a skill name (beginner, intermediate, expert) to edit the catalog on disk, or a custom
          variant name for experiments stored in the DB.
        </p>
        <ul className="prompts-empty-hints">
          <li>
            <strong>Catalog</strong> — canonical prompts per skill level; changes write to{" "}
            <code>benchmark/task_catalog/</code>
          </li>
          <li>
            <strong>Variants</strong> — experimental prompts for generate/judge without editing the catalog
          </li>
        </ul>
        <div className="prompts-empty-actions">
          <button type="button" className="btn-primary" onClick={() => openCreateTask()}>
            New catalog task
          </button>
          <button type="button" className="btn-secondary" onClick={() => openCreateVariant()}>
            New prompt variant
          </button>
        </div>
      </div>
    );
  })();

  return (
    <div className="page prompts-page">
      <header className="page-header prompts-page-header">
        <div>
          <h2>Prompts</h2>
          <p className="prompts-subtitle">
            Browse by task and skill level. Edit catalog sources on disk or add DB variants for experiments.
          </p>
        </div>
        <div className="prompts-toolbar" role="toolbar" aria-label="Prompt authoring">
          <button
            type="button"
            className={createMode === "task" ? "btn-secondary prompts-toolbar-active" : "btn-secondary"}
            onClick={() => (createMode === "task" ? closeCreate() : openCreateTask())}
          >
            {createMode === "task" ? "Cancel task" : "New catalog task"}
          </button>
          <button
            type="button"
            className={createMode === "variant" ? "btn-secondary prompts-toolbar-active" : "btn-secondary"}
            onClick={() => (createMode === "variant" ? closeCreate() : openCreateVariant())}
          >
            {createMode === "variant" ? "Cancel variant" : "New variant"}
          </button>
        </div>
      </header>

      <LoadingNotice
        loading={prompts.loading || catalog.loading}
        error={prompts.error ?? catalog.error}
        label="Loading prompts…"
      />

      {!prompts.loading && !catalog.loading && !prompts.error && !catalog.error ? (
        <div className="master-detail-grid prompts-layout">
          <aside className="master-list panel" aria-label="Prompt tree">
            <PromptTree
              catalog={catalog.data ?? []}
              prompts={prompts.data ?? []}
              selectedPromptId={selectedPromptId}
              selectedCanonicalInstanceId={selectedCanonicalInstanceId}
              onSelectPrompt={selectPrompt}
              onSelectCanonical={selectCanonical}
              onAddVariant={(instId) => openCreateVariant(instId)}
            />
          </aside>
          <section className="detail-pane panel">{detailContent}</section>
        </div>
      ) : null}
    </div>
  );
}
