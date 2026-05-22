import { useState } from "react";
import { createAnnotation, listRunAnnotations } from "../api/client";
import type { Evaluation, EvidenceSelection, Finding, WorkbenchRun } from "../api/types";
import { useAsyncResource } from "../hooks/useAsyncResource";

/**
 * Props for the annotation panel component.
 */
export interface AnnotationPanelProps {
  /** Run being annotated. */
  run: WorkbenchRun | null;
  /** Selected evaluation view. */
  evaluation: Evaluation | null;
  /** Findings available for optional finding-level labels. */
  findings: Finding[];
  /** Artifact evidence selected in the viewer. */
  evidenceSelection: EvidenceSelection | null;
  /** Trace event ids selected in the timeline. */
  selectedTraceEventIds: string[];
  /** Callback fired after a successful save. */
  onSaved: () => void;
}

/**
 * Provide a compact form for run-level or finding-level human labels.
 *
 * @param props - Annotation panel inputs.
 * @returns Annotation form panel.
 */
export function AnnotationPanel({
  run,
  evaluation,
  findings,
  evidenceSelection,
  selectedTraceEventIds,
  onSaved
}: AnnotationPanelProps) {
  const [annotator, setAnnotator] = useState("");
  const [label, setLabel] = useState("correct_but_insecure");
  const [correctnessVerdict, setCorrectnessVerdict] = useState("pass");
  const [securityVerdict, setSecurityVerdict] = useState("fail");
  const [severity, setSeverity] = useState("medium");
  const [confidence, setConfidence] = useState("medium");
  const [rationale, setRationale] = useState("");
  const [findingId, setFindingId] = useState("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error" | "stale_evidence_warning">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const saved = useAsyncResource(
    () => (run ? listRunAnnotations(run.id) : Promise.resolve([])),
    [run?.id, reloadToken]
  );
  const saving = saveState === "saving";
  const disabled = !run || saving;

  return (
    <section className="panel annotation-panel">
      <h2>Annotation</h2>
      {saveState === "saved" ? <p className="save-status saved">Saved</p> : null}
      {saveState === "error" ? <p className="save-status error">{saveError}</p> : null}
      {saveState === "stale_evidence_warning" ? (
        <p className="save-status warning">Evidence may be stale — re-select artifact lines before saving.</p>
      ) : null}

      <div className="saved-annotations">
        <h3>Saved for this run</h3>
        {saved.error ? <p className="error-inline">{saved.error}</p> : null}
        {!saved.data?.length ? <p className="empty-state compact">No annotations yet.</p> : null}
        <ul className="annotation-history">
          {(saved.data ?? []).map((entry) => (
            <li key={entry.id}>
              <div className="annotation-history-head">
                <strong>{entry.label}</strong>
                <span className="annotation-status">{entry.queue_status}</span>
              </div>
              <span className="annotation-meta">
                {entry.annotator}
                {entry.file_path && entry.start_line
                  ? ` · ${entry.file_path}:${entry.start_line}-${entry.end_line ?? entry.start_line}`
                  : ""}
              </span>
              <p className="annotation-rationale">{entry.rationale}</p>
            </li>
          ))}
        </ul>
      </div>

      <h3>New annotation</h3>
      <label>
        Annotator
        <input value={annotator} onChange={(event) => setAnnotator(event.target.value)} />
      </label>
      <label>
        Scope
        <select value={findingId} onChange={(event) => setFindingId(event.target.value)}>
          <option value="">Entire run</option>
          {findings.map((finding) => (
            <option key={finding.id} value={finding.id}>
              {finding.source}: {finding.category}
            </option>
          ))}
        </select>
      </label>
      <label>
        Label
        <select value={label} onChange={(event) => setLabel(event.target.value)}>
          <option value="correctness_failure">correctness_failure</option>
          <option value="correct_but_insecure">correct_but_insecure</option>
          <option value="functional_but_insecure">functional_but_insecure</option>
          <option value="secure_but_nonfunctional">secure_but_nonfunctional</option>
          <option value="supply_chain_unpinned">supply_chain_unpinned</option>
          <option value="other">other</option>
        </select>
      </label>
      <label>
        Correctness
        <select value={correctnessVerdict} onChange={(event) => setCorrectnessVerdict(event.target.value)}>
          <option value="pass">pass</option>
          <option value="fail">fail</option>
          <option value="unknown">unknown</option>
        </select>
      </label>
      <label>
        Security
        <select value={securityVerdict} onChange={(event) => setSecurityVerdict(event.target.value)}>
          <option value="pass">pass</option>
          <option value="fail">fail</option>
          <option value="warning">warning</option>
          <option value="unknown">unknown</option>
        </select>
      </label>
      <div className="form-row">
        <label>
          Severity
          <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="info">info</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
            <option value="critical">critical</option>
          </select>
        </label>
        <label>
          Confidence
          <select value={confidence} onChange={(event) => setConfidence(event.target.value)}>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </label>
      </div>
      <div className="evidence-box">
        <strong>Evidence</strong>
        <span>
          {evidenceSelection
            ? `${evidenceSelection.file_path}:${evidenceSelection.start_line}-${evidenceSelection.end_line}`
            : "No artifact lines selected"}
        </span>
        <span>{selectedTraceEventIds.length} trace event(s) selected</span>
        {evaluation ? <span>Score view: {evaluation.evaluation_kind}</span> : null}
      </div>
      <label>
        Rationale
        <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} />
      </label>
      <button
        disabled={disabled || !annotator || !rationale}
        onClick={() => {
          if (!run) {
            return;
          }
          setSaveState("saving");
          setSaveError(null);
          createAnnotation({
            run_id: run.id,
            finding_id: findingId || undefined,
            annotator,
            label,
            correctness_verdict: correctnessVerdict,
            security_verdict: securityVerdict,
            severity,
            confidence,
            rationale,
            queue_status: "submitted",
            artifact_id: evidenceSelection?.artifact_id,
            file_path: evidenceSelection?.file_path,
            start_line: evidenceSelection?.start_line,
            end_line: evidenceSelection?.end_line,
            selected_text: evidenceSelection?.selected_text,
            trace_event_ids: selectedTraceEventIds,
            evidence_json: {
              artifact_selection: evidenceSelection,
              trace_event_ids: selectedTraceEventIds
            }
          })
            .then(() => {
              setRationale("");
              setSaveState("saved");
              setReloadToken((token) => token + 1);
              onSaved();
            })
            .catch((err) => {
              const message = err instanceof Error ? err.message : String(err);
              setSaveError(message);
              setSaveState(message.includes("selected_text") ? "stale_evidence_warning" : "error");
            });
        }}
      >
        {saving ? "Saving…" : "Save annotation"}
      </button>
    </section>
  );
}
