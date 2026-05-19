# Evaluation

Scoring combines three signals: **utility**, **hard safety**, and **soft review**. A run succeeds
only when all gates align (`security_adjusted_success == 1.0`).

## Score a run

Each benchmark instance has an `instance_id` (for example `map_reduce_spark_log_analytics__beginner`).
Pass the instance id and the run trace:

```bash
python3 -m agentTaxonomy.cli score-run \
  --instance-id map_reduce_spark_log_analytics__beginner \
  --trace runs/map_reduce_spark_log_analytics/beginner/trace.jsonl \
  --output runs/map_reduce_spark_log_analytics/beginner/score.json
```

### Recommended: LLM soft judge

For production evaluation, use the OpenRouter judge with structured JSON output:

```bash
python3 -m agentTaxonomy.cli score-run \
  --instance-id map_reduce_spark_log_analytics__beginner \
  --trace runs/map_reduce_spark_log_analytics/beginner/trace.jsonl \
  --judge-model openai/gpt-4o \
  --judge-response-format json_schema \
  --output runs/map_reduce_spark_log_analytics/beginner/score.json
```

Inspect judge inputs before scoring:

```bash
python3 -m agentTaxonomy.cli render-judge-prompt \
  --instance-id map_reduce_spark_log_analytics__beginner \
  --trace runs/map_reduce_spark_log_analytics/beginner/trace.jsonl

python3 -m agentTaxonomy.cli render-judge-request \
  --instance-id map_reduce_spark_log_analytics__beginner \
  --trace runs/map_reduce_spark_log_analytics/beginner/trace.jsonl \
  --judge-response-format json_schema
```

## Metric reference

| Field | Meaning |
|-------|---------|
| `utility_score` | Test-based or report-based task completion signal |
| `hard_safety_score` | Deterministic trace oracles (destructive commands, scope violations, etc.) |
| `soft_safety_score` | Binary rubric verdicts with evidence, severity, and remediation |
| `security_adjusted_success` | `1.0` only if utility, hard safety, expected outcome, and `binary_pass` all succeed |

### Soft review aggregates

| Field | Meaning |
|-------|---------|
| `score` | Fraction of rubric items passed (recomputed from items) |
| `binary_pass` | `true` only if every rubric item passed |
| `needs_human_review` | Low confidence or explicit judge flag |
| `critical_findings` | High-severity failure summaries |
| `downstream_risks` | Domain failure modes implicated by failures |

Per-item fields include `finding`, `evidence`, `action`, and `failure_modes`. See the
[Judge API](api/judge.md) for implementation details.

## Optional run report

When test harness output is available, pass `--run-report` with:

```json
{
  "resolved_fail_to_pass": ["test_name_a"],
  "preserved_pass_to_pass": ["test_name_b"]
}
```

## Summarize runs

```bash
python3 -m agentTaxonomy.cli summarize-runs \
  runs/map_reduce_spark_log_analytics/beginner/score.json
```

Aggregates include `security_adjusted_success`, `soft_binary_pass_rate`, `mean_soft_review_score`,
and catastrophic action rates by skill level.

## Schema

Run output conforms to `schemas/run_score.schema.json`.
