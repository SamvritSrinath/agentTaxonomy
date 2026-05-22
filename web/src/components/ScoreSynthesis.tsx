import { useEffect, useMemo, useState } from "react";
import type { Evaluation, Score } from "../api/types";
function formatScore(value: number | null | undefined): string {
  if (value == null) {
    return "—";
  }
  return value.toFixed(3);
}

/**
 * Batch score row from GET /api/runs/{id}/scores.
 */
export interface RunScoreEntry {
  evaluation: Evaluation;
  score: Score | null;
  canonical: boolean;
}

/**
 * Props for score synthesis panel.
 */
export interface ScoreSynthesisProps {
  entries: RunScoreEntry[];
  canonicalEvaluationId: string | null;
  selectedEvaluationId: string | null;
  onSelectEvaluation: (evaluationId: string) => void;
}

/**
 * Render rich score synthesis with gates, rubric items, and compare mode.
 */
export function ScoreSynthesis({
  entries,
  canonicalEvaluationId,
  selectedEvaluationId,
  onSelectEvaluation
}: ScoreSynthesisProps) {
  const [compareMode, setCompareMode] = useState(false);
  const codeOnly = entries.find((row) => row.evaluation.evidence_condition === "code_only");
  const codePlusTrace = entries.find((row) => row.evaluation.evidence_condition === "code_plus_trace");
  const canCompare = Boolean(codeOnly?.score && codePlusTrace?.score);
  const missingCompare = !canCompare && entries.length > 0;

  useEffect(() => {
    if (canCompare) {
      setCompareMode(true);
    }
  }, [canCompare]);

  const selected =
    entries.find((row) => row.evaluation.id === selectedEvaluationId) ??
    entries.find((row) => row.evaluation.id === canonicalEvaluationId) ??
    entries.find((row) => row.canonical) ??
    entries[0] ??
    null;
  const scoreJson = (selected?.score?.score_json ?? {}) as Record<string, unknown>;
  const gates = useMemo(() => extractGates(scoreJson), [scoreJson]);
  const rubricItems = useMemo(() => extractRubricItems(scoreJson), [scoreJson]);
  const softAggregate = useMemo(() => extractSoftAggregate(scoreJson), [scoreJson]);

  if (!entries.length) {
    return <section className="panel">No evaluations indexed for this run.</section>;
  }

  return (
    <section className="panel score-synthesis">
      {missingCompare ? (
        <p className="score-compare-banner">
          Run <strong>Evaluate both</strong> in the toolbar to compare code-only (artifacts/output) vs code+trace
          (full trace, audit, supply chain). Each mode re-runs scoring with different evidence inputs.
        </p>
      ) : null}
      <div className="panel-header-row">
        <h2>Score synthesis</h2>
        {canCompare ? (
          <label className="compare-toggle">
            <input type="checkbox" checked={compareMode} onChange={(event) => setCompareMode(event.target.checked)} />
            Compare code_only vs code_plus_trace
          </label>
        ) : null}
      </div>
      <ul className="evaluation-tabs">
        {entries.map((row) => (
          <li key={row.evaluation.id}>
            <button
              className={
                row.evaluation.id === selected?.evaluation.id
                  ? "text-button selected"
                  : "text-button"
              }
              onClick={() => onSelectEvaluation(row.evaluation.id)}
            >
              <strong>{row.evaluation.evidence_condition}</strong>
              {row.canonical ? <span className="badge">canonical</span> : null}
            </button>
          </li>
        ))}
      </ul>
      {compareMode && codeOnly && codePlusTrace ? (
        <div className="compare-grid">
          <ScoreColumn title="code_only" row={codeOnly} />
          <ScoreColumn title="code_plus_trace" row={codePlusTrace} />
        </div>
      ) : selected ? (
        <ScoreColumn
          title={selected.evaluation.evidence_condition}
          row={selected}
          gates={gates}
          rubricItems={rubricItems}
          softAggregate={softAggregate}
        />
      ) : null}
    </section>
  );
}

function ScoreColumn({
  title,
  row,
  gates,
  rubricItems,
  softAggregate
}: {
  title: string;
  row: RunScoreEntry;
  gates?: ReturnType<typeof extractGates>;
  rubricItems?: ReturnType<typeof extractRubricItems>;
  softAggregate?: ReturnType<typeof extractSoftAggregate>;
}) {
  const scoreJson = (row.score?.score_json ?? {}) as Record<string, unknown>;
  const columnGates = gates ?? extractGates(scoreJson);
  const columnRubric = rubricItems ?? extractRubricItems(scoreJson);
  const columnSoft = softAggregate ?? extractSoftAggregate(scoreJson);
  return (
    <div className="score-column">
      <h3>{title}</h3>
      <dl className="metric-grid">
        <div>
          <dt>Outcome</dt>
          <dd>{row.evaluation.final_outcome_class ?? "unknown"}</dd>
        </div>
        <div>
          <dt>Strict success</dt>
          <dd>{formatScore(row.score?.security_adjusted_success)}</dd>
        </div>
        <div>
          <dt>Utility</dt>
          <dd>{formatScore(row.score?.utility_score)}</dd>
        </div>
        <div>
          <dt>Hard safety</dt>
          <dd>{formatScore(row.score?.hard_safety_score)}</dd>
        </div>
        <div>
          <dt>Soft safety</dt>
          <dd>
            {formatScore(row.score?.soft_safety_score)}
            {columnSoft.score != null ? (
              <span className="metric-subtle"> (rubric {formatScore(columnSoft.score)})</span>
            ) : null}
          </dd>
        </div>
        {columnSoft.binaryPass != null ? (
          <div>
            <dt>Soft rubric pass</dt>
            <dd>{columnSoft.binaryPass ? "all items pass" : "one or more items failed"}</dd>
          </div>
        ) : null}
      </dl>
      {columnGates.length ? (
        <>
          <h4>Gates</h4>
          <ul className="gate-list">
            {columnGates.map((gate) => (
              <li key={gate.id} className={`gate-${gate.kind}`}>
                <strong>{gate.id}</strong>
                <span>{gate.verdict}</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {columnRubric.length ? (
        <>
          <h4>Soft rubric</h4>
          <table className="rubric-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Pass</th>
                <th>Severity</th>
              </tr>
            </thead>
            <tbody>
              {columnRubric.map((item) => (
                <tr key={item.rubric_id}>
                  <td>{item.rubric_id}</td>
                  <td>{item.binary_pass ? "pass" : "fail"}</td>
                  <td>{item.severity ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </div>
  );
}

function extractGates(scoreJson: Record<string, unknown>) {
  const gateItems = scoreJson.security_gate_verdicts as Array<Record<string, unknown>> | undefined;
  if (gateItems?.length) {
    return gateItems.map((gate) => ({
      id: String(gate.name ?? gate.gate_id ?? "gate"),
      verdict: String(gate.verdict ?? "unknown"),
      kind: String(gate.verdict ?? "unknown")
    }));
  }
  return [];
}

function extractRubricItems(scoreJson: Record<string, unknown>) {
  const soft = scoreJson.soft_safety_score as Record<string, unknown> | undefined;
  const items = (soft?.items as Array<Record<string, unknown>> | undefined) ?? [];
  return items.map((item) => ({
    rubric_id: String(item.rubric_id ?? "item"),
    binary_pass: Boolean(item.binary_pass ?? item.passed),
    severity: item.severity as string | undefined
  }));
}

function extractSoftAggregate(scoreJson: Record<string, unknown>) {
  const soft = scoreJson.soft_safety_score as Record<string, unknown> | undefined;
  if (!soft) {
    return { score: null as number | null, binaryPass: null as boolean | null };
  }
  const score = typeof soft.score === "number" ? soft.score : null;
  const binaryPass =
    typeof soft.binary_pass === "boolean"
      ? soft.binary_pass
      : Array.isArray(soft.items)
        ? (soft.items as Array<Record<string, unknown>>).every((item) => Boolean(item.passed ?? item.binary_pass))
        : null;
  return { score, binaryPass };
}
