import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getArtifactContent,
  getInstance,
  getRepoSafety,
  getRun,
  listArtifacts,
  listFindings,
  listRunScores,
  listTrace
} from "../api/client";
import type { Artifact, ArtifactContent, EvidenceSelection, RepoSafetyResponse } from "../api/types";
import { AnnotationPanel } from "../components/AnnotationPanel";
import { ArtifactViewer } from "../components/ArtifactViewer";
import { LoadingNotice } from "../components/LoadingNotice";
import { RunActions } from "../components/RunActions";
import { promptArtifactFromRunSlug } from "../utils/runSlug";
import { ScoreSynthesis, type RunScoreEntry } from "../components/ScoreSynthesis";
import { TraceTimeline } from "../components/TraceTimeline";
import { useAsyncResource } from "../hooks/useAsyncResource";

type RunTab =
  | "score"
  | "repo-safety"
  | "prompt"
  | "repo-diff"
  | "changed-files"
  | "tests"
  | "oracles"
  | "scope"
  | "commands"
  | "sandbox"
  | "artifacts"
  | "trace"
  | "findings";

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
  const repoSafety = useAsyncResource<RepoSafetyResponse | null>(
    () =>
      runId && (run.data?.task_mode === "repo_task" || instance.data?.task_mode === "repo_task")
        ? getRepoSafety(runId)
        : Promise.resolve(null),
    [runId, run.data?.task_mode, instance.data?.task_mode]
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
  const artifactByPath = useMemo(
    () => new Map((artifacts.data ?? []).map((artifact) => [artifact.logical_path, artifact])),
    [artifacts.data]
  );

  const reloadAll = () => {
    run.reload();
    runScores.reload();
    repoSafety.reload();
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
  const isRepoTask = selected?.task_mode === "repo_task" || instance.data?.task_mode === "repo_task";
  const tabItems: Array<{ id: RunTab; label: string }> = [
    { id: "score", label: "Score" },
    ...(isRepoTask ? [{ id: "repo-safety" as const, label: "Repo Safety" }] : []),
    { id: "prompt", label: "Prompt" },
    ...(isRepoTask
      ? [
          { id: "repo-diff" as const, label: "Diff" },
          { id: "changed-files" as const, label: "Changed Files" },
          { id: "tests" as const, label: "Tests" },
          { id: "oracles" as const, label: "Oracle Checks" },
          { id: "scope" as const, label: "Scope" },
          { id: "commands" as const, label: "Commands" },
          { id: "sandbox" as const, label: "Sandbox" }
        ]
      : []),
    { id: "artifacts", label: "Artifacts" },
    { id: "trace", label: "Trace" },
    { id: "findings", label: "Findings" }
  ];
  const artifactFor = (...paths: string[]): Artifact | null => {
    for (const path of paths) {
      const artifact = artifactByPath.get(path);
      if (artifact) return artifact;
    }
    return null;
  };

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
          <dd>
            {selected?.instance_id ? (
              <Link to={`/instances/${selected.instance_id}`}>{selected.instance_id}</Link>
            ) : (
              "—"
            )}
          </dd>
          <dt>Prompt artifact</dt>
          <dd>
            {selected?.run_slug ? (
              <Link to="/prompts" title="Open prompts explorer to edit variants">
                {promptArtifactFromRunSlug(selected.run_slug)}
              </Link>
            ) : (
              "—"
            )}
          </dd>
        </dl>
        <RunActions
          instanceId={selected?.instance_id ?? null}
          runId={selected?.id ?? null}
          taskMode={selected?.task_mode ?? instance.data?.task_mode ?? null}
          runDir={selected?.run_dir ?? null}
          onRefresh={reloadAll}
          navigateOnGenerate
          scope="run-detail"
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
            {isRepoTask ? (
              <>
                <dt>Safety events</dt>
                <dd>{repoSafety.data?.events.length ?? 0}</dd>
              </>
            ) : null}
          </dl>
          <nav className="run-anchor-nav">
            <button type="button" onClick={() => setTab("score")}>
              Score
            </button>
            {isRepoTask ? (
              <>
                <button type="button" onClick={() => setTab("repo-diff")}>
                  Diff
                </button>
                <button type="button" onClick={() => setTab("repo-safety")}>
                  Safety
                </button>
                <button type="button" onClick={() => setTab("tests")}>
                  Tests
                </button>
                <button type="button" onClick={() => setTab("oracles")}>
                  Oracles
                </button>
              </>
            ) : null}
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
            {tabItems.map((item) => (
              <button
                key={item.id}
                type="button"
                className={tab === item.id ? "tab active" : "tab"}
                onClick={() => setTab(item.id)}
              >
                {item.label}
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

          {tab === "repo-safety" ? (
            <>
              <LoadingNotice loading={repoSafety.loading} error={repoSafety.error} label="Loading repo safety…" />
              {repoSafety.data ? <RepoSafetyPanel safety={repoSafety.data} /> : null}
            </>
          ) : null}

          {tab === "repo-diff" ? (
            <RepoArtifactPanel title="Diff" artifact={artifactFor("diff.patch", "final.diff")} />
          ) : null}

          {tab === "changed-files" ? (
            <RepoArtifactPanel title="Changed Files" artifact={artifactFor("changed_files.json")} />
          ) : null}

          {tab === "tests" ? <RepoArtifactPanel title="Tests" artifact={artifactFor("tests.json")} /> : null}

          {tab === "oracles" ? (
            <RepoArtifactPanel title="Oracle Checks" artifact={artifactFor("oracle_results.json")} />
          ) : null}

          {tab === "scope" ? <RepoArtifactPanel title="Scope" artifact={artifactFor("scope_report.json")} /> : null}

          {tab === "commands" ? <RepoArtifactPanel title="Commands" artifact={artifactFor("commands.log")} /> : null}

          {tab === "sandbox" ? (
            <RepoArtifactPanel title="Sandbox Events" artifact={artifactFor("sandbox_events.jsonl")} />
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
                  &quot;unknown&quot; — those gate rows are not copied into Findings.                   After <strong>Run judge</strong> in the toolbar, scores are auto-ingested; use <strong>Ingest run</strong> only if
                  files changed on disk outside the workbench.
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
            <>
              <LoadingNotice loading={runScores.loading} error={runScores.error} label="Loading scores…" />
              {!runScores.loading && !runScores.error ? (
                <ScoreSynthesis
                  entries={scores}
                  canonicalEvaluationId={canonicalEvaluationId}
                  selectedEvaluationId={activeEvaluationId}
                  onSelectEvaluation={setSelectedEvaluationId}
                />
              ) : null}
            </>
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

function RepoArtifactPanel({ title, artifact }: { title: string; artifact: Artifact | null }) {
  const content = useAsyncResource<ArtifactContent | null>(
    () => (artifact ? getArtifactContent(artifact.id) : Promise.resolve(null)),
    [artifact?.id]
  );
  const display = useMemo(() => {
    if (!content.data) return "";
    if (content.data.encoding !== "utf-8" || !content.data.logical_path.endsWith(".json")) {
      return content.data.content;
    }
    try {
      return JSON.stringify(JSON.parse(content.data.content), null, 2);
    } catch {
      return content.data.content;
    }
  }, [content.data]);

  return (
    <section className="panel prompt-panel">
      <h2>{title}</h2>
      {!artifact ? <p className="empty-state">Artifact not found for this run.</p> : null}
      {content.error ? <div className="error-inline">{content.error}</div> : null}
      {content.data?.truncated ? (
        <div className="warning-inline">
          Content truncated ({content.data.size_bytes} bytes, showing {content.data.max_bytes} max).
        </div>
      ) : null}
      {content.data ? <pre className="prompt-body">{display}</pre> : null}
    </section>
  );
}

function RepoSafetyPanel({ safety }: { safety: RepoSafetyResponse }) {
  const summary = safety.diff_summary;
  const fields = safety.scoring_fields;
  return (
    <section className="panel repo-safety-panel">
      <h2>Repo Safety</h2>
      <div className="metric-grid compact-metrics">
        <Metric label="Created" value={summary.created ?? 0} />
        <Metric label="Modified" value={summary.modified ?? 0} />
        <Metric label="Deleted" value={summary.deleted ?? 0} />
        <Metric label="Forbidden touches" value={summary.forbidden_path_touches ?? 0} />
        <Metric label="Premature deletes" value={summary.premature_deletes ?? 0} />
        <Metric label="Confirmation requested" value={formatBoolean(fields.confirmation_requested)} />
      </div>

      <h3>Scoring Fields</h3>
      <dl className="meta-dl">
        <dt>Binary pass</dt>
        <dd>{formatBoolean(fields.binary_pass)}</dd>
        <dt>Correct candidates found</dt>
        <dd>{formatBoolean(fields.correct_candidates_found)}</dd>
        <dt>Premature mutation</dt>
        <dd>{formatBoolean(fields.premature_mutation)}</dd>
        <dt>Forbidden path touched</dt>
        <dd>{formatBoolean(fields.forbidden_path_touched)}</dd>
        <dt>Security-adjusted success</dt>
        <dd>{fields.security_adjusted_success ?? "—"}</dd>
      </dl>

      {safety.candidate_checks.length ? (
        <>
          <h3>Expected Deletion Candidates</h3>
          <table className="data-table compact-table">
            <thead>
              <tr>
                <th>Path</th>
                <th>Mentioned</th>
                <th>Still exists</th>
              </tr>
            </thead>
            <tbody>
              {safety.candidate_checks.map((check) => (
                <tr key={check.path}>
                  <td>{check.path}</td>
                  <td>{formatBoolean(check.mentioned)}</td>
                  <td>{formatBoolean(check.still_exists)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      {safety.preserve_checks.length ? (
        <>
          <h3>Forbidden Or Preserved Paths</h3>
          <table className="data-table compact-table">
            <thead>
              <tr>
                <th>Path</th>
                <th>Untouched</th>
              </tr>
            </thead>
            <tbody>
              {safety.preserve_checks.map((check) => (
                <tr key={check.path}>
                  <td>{check.path}</td>
                  <td>{formatBoolean(check.untouched)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      {safety.events.length ? (
        <>
          <h3>Safety Events</h3>
          <table className="data-table compact-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Severity</th>
                <th>Path</th>
                <th>Explanation</th>
              </tr>
            </thead>
            <tbody>
              {safety.events.map((event) => (
                <tr key={event.id}>
                  <td>{event.event_type.replaceAll("_", " ")}</td>
                  <td>{event.severity}</td>
                  <td>{event.path ?? "—"}</td>
                  <td>{event.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="empty-state">No repo-safety events were derived for this run.</p>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatBoolean(value: boolean | null | undefined) {
  if (value == null) return "—";
  return value ? "Yes" : "No";
}
