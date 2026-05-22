import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getInstance,
  getRun,
  listArtifacts,
  listFindings,
  listRunScores,
  listTrace
} from "../api/client";
import type { EvidenceSelection } from "../api/types";
import { AnnotationPanel } from "../components/AnnotationPanel";
import { ArtifactViewer } from "../components/ArtifactViewer";
import { RunActions } from "../components/RunActions";
import { ScoreSynthesis, type RunScoreEntry } from "../components/ScoreSynthesis";
import { TraceTimeline } from "../components/TraceTimeline";
import { useAsyncResource } from "../hooks/useAsyncResource";

type RunTab = "prompt" | "artifacts" | "trace" | "findings" | "score";

export function RunDetailRoute() {
  const { runId = "" } = useParams();
  const run = useAsyncResource(() => getRun(runId), [runId]);
  const instance = useAsyncResource(
    () => (run.data?.instance_id ? getInstance(run.data.instance_id) : Promise.resolve(null)),
    [run.data?.instance_id]
  );
  const runScores = useAsyncResource(
    () =>
      runId
        ? listRunScores(runId)
        : Promise.resolve({ run_id: "", canonical_evaluation_id: null, scores: [] }),
    [runId]
  );
  const artifacts = useAsyncResource(() => (runId ? listArtifacts(runId) : Promise.resolve([])), [runId]);
  const trace = useAsyncResource(() => (runId ? listTrace(runId) : Promise.resolve([])), [runId]);
  const findings = useAsyncResource(() => (runId ? listFindings(runId) : Promise.resolve([])), [runId]);

  const [tab, setTab] = useState<RunTab>("score");
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null);
  const [evidenceSelection, setEvidenceSelection] = useState<EvidenceSelection | null>(null);
  const [selectedTraceEventIds, setSelectedTraceEventIds] = useState<string[]>([]);

  const canonicalEvaluationId = runScores.data?.canonical_evaluation_id ?? null;
  const scores: RunScoreEntry[] = runScores.data?.scores ?? [];
  const activeEvaluationId =
    selectedEvaluationId ?? canonicalEvaluationId ?? scores[0]?.evaluation.id ?? null;
  const activeEvaluation = scores.find((entry) => entry.evaluation.id === activeEvaluationId)?.evaluation ?? null;

  const gateCount = useMemo(() => {
    const score = scores.find((entry) => entry.evaluation.id === activeEvaluationId)?.score;
    const gates = (score?.score_json as { security_gate_verdicts?: unknown[] } | undefined)?.security_gate_verdicts;
    return Array.isArray(gates) ? gates.length : 0;
  }, [scores, activeEvaluationId]);

  const reloadAll = () => {
    run.reload();
    runScores.reload();
    artifacts.reload();
    trace.reload();
    findings.reload();
    instance.reload();
  };

  const toggleTraceEvent = (eventId: string) => {
    setSelectedTraceEventIds((current) =>
      current.includes(eventId) ? current.filter((item) => item !== eventId) : [...current, eventId]
    );
  };

  if (!runId) {
    return <p className="empty-state">No run selected.</p>;
  }

  if (run.error) {
    return <div className="error">{run.error}</div>;
  }

  const selected = run.data;

  return (
    <div className="page run-detail-page">
      <header className="run-header panel">
        <div className="run-header-main">
          <Link to="/runs">← Runs</Link>
          <h2>{selected?.run_slug ?? runId}</h2>
          <span className={`status-badge status-${selected?.status ?? "unknown"}`}>{selected?.status}</span>
        </div>
        <dl className="run-header-meta">
          <dt>Model</dt>
          <dd>{selected?.model_name ?? "—"}</dd>
          <dt>Instance</dt>
          <dd>{selected?.instance_id ?? "—"}</dd>
        </dl>
        <RunActions
          instanceId={selected?.instance_id ?? null}
          runId={selected?.id ?? null}
          taskMode={selected?.task_mode ?? instance.data?.task_mode ?? null}
          runDir={selected?.run_dir ?? null}
          onRefresh={reloadAll}
        />
      </header>

      <div className="run-detail-layout">
        <aside className="run-summary-rail panel">
          <h3>Summary</h3>
          <dl className="meta-dl">
            <dt>Status</dt>
            <dd>{selected?.status}</dd>
            <dt>Task mode</dt>
            <dd>{selected?.task_mode ?? "—"}</dd>
            <dt>Findings</dt>
            <dd>{findings.data?.length ?? 0}</dd>
            <dt>Gates</dt>
            <dd>{gateCount}</dd>
          </dl>
          <nav className="run-anchor-nav">
            <button type="button" onClick={() => setTab("score")}>
              Score
            </button>
            <button type="button" onClick={() => setTab("findings")}>
              Findings
            </button>
            <button type="button" onClick={() => setTab("artifacts")}>
              Artifacts
            </button>
          </nav>
        </aside>

        <section className="run-tab-workspace">
          <div className="evaluation-tabs">
            {(["prompt", "artifacts", "trace", "findings", "score"] as RunTab[]).map((name) => (
              <button
                key={name}
                type="button"
                className={tab === name ? "tab active" : "tab"}
                onClick={() => setTab(name)}
              >
                {name.charAt(0).toUpperCase() + name.slice(1)}
              </button>
            ))}
          </div>

          {tab === "prompt" ? (
            <section className="panel prompt-panel">
              {instance.data?.agent_prompt ? (
                <pre className="prompt-body">{instance.data.agent_prompt}</pre>
              ) : (
                <p className="empty-state">No catalog prompt loaded for this instance.</p>
              )}
            </section>
          ) : null}

          {tab === "artifacts" ? (
            <ArtifactViewer
              artifacts={artifacts.data ?? []}
              evidenceSelection={evidenceSelection}
              onSelectEvidence={setEvidenceSelection}
            />
          ) : null}

          {tab === "trace" ? (
            <TraceTimeline
              events={trace.data ?? []}
              selectedEventIds={selectedTraceEventIds}
              onToggleEvent={toggleTraceEvent}
            />
          ) : null}

          {tab === "findings" ? (
            <section className="panel">
              {(findings.data ?? []).length === 0 ? (
                <p className="empty-state">
                  No findings indexed for this run. Ingest only loads non-empty <strong>findings[]</strong> from{" "}
                  <strong>audit.json</strong> and <strong>supply_chain.json</strong>, plus <strong>failed</strong> soft-judge
                  rubric rows from <strong>score.json</strong>. Your audit file can exist with{" "}
                  <code>findings: []</code> (no static hits) while <code>security_gate_verdicts</code> show
                  &quot;unknown&quot; — those gate rows are not copied into Findings. After <strong>Run Judge Pipeline</strong>,
                  click <strong>Ingest run</strong> again (the run folder hash changes when audit/score are written).
                </p>
              ) : (
                <ul className="finding-list">
                  {(findings.data ?? []).map((finding) => (
                    <li key={finding.id}>
                      <strong>
                        {finding.source} · {finding.severity}
                      </strong>
                      <span>{finding.message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ) : null}

          {tab === "score" ? (
            <ScoreSynthesis
              entries={scores}
              canonicalEvaluationId={canonicalEvaluationId}
              selectedEvaluationId={activeEvaluationId}
              onSelectEvaluation={setSelectedEvaluationId}
            />
          ) : null}
        </section>

        <aside className="annotation-drawer">
          <AnnotationPanel
            run={selected ?? null}
            evaluation={activeEvaluation}
            findings={findings.data ?? []}
            evidenceSelection={evidenceSelection}
            selectedTraceEventIds={selectedTraceEventIds}
            onSaved={reloadAll}
          />
        </aside>
      </div>
    </div>
  );
}
