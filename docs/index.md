# Unsafe Autonomy Bench

**Unsafe Autonomy Bench** is an open-source benchmark for measuring how coding agents behave under
realistic engineering tasks when safety, utility, and permission boundaries matter.

The benchmark is **taxonomy-first**: every instance is labeled by problem class, subject area,
skill level, permission scope, consequence class, and expected safe outcome. Runs are scored with
deterministic hard-safety oracles, optional test utility signals, and an adversarial soft-review
judge.

## What this repository provides

| Component | Description |
|-----------|-------------|
| **Task catalog** | Prompt sets and metadata under `benchmark/task_catalog/` |
| **`agentTaxonomy`** | Python package for catalog generation, run tracing, and scoring |
| **Schemas** | JSON schemas for traces, instances, and run scores |
| **Rubrics** | Binary soft-review criteria with evidence-backed verdicts |

## Typical workflow

1. [Build the catalog](getting-started.md#build-the-catalog) after adding or editing tasks.
2. [Generate an agent run](getting-started.md#generate-a-run) via OpenRouter (`agent_output.md` + `trace.jsonl`).
3. [Extract artifacts, audit, and enrich supply chain](evaluation.md#comprehensive-pipeline-generative-runs) on `extracted/`.
4. [Score the run](evaluation.md#score-a-run) with audit reports, static verification tier, and an LLM judge.
5. [Review metrics](evaluation.md#reviewing-a-run) and [aggregate](evaluation.md#summarize-runs) across models.

## Documentation map

- **[Getting Started](getting-started.md)** — environment, CLI, and first commands
- **[Evaluation](evaluation.md)** — metrics, judges, and score interpretation
- **[Task Authoring](authoring.md)** — how to add prompt sets to the catalog
- **[API Reference](api/index.md)** — Python modules with source links

## Package layout

The installable package lives at `src/agentTaxonomy/`. Subpackages include `catalog`, `cli`,
`generate`, `harness`, `judge`, `schema`, `scoring`, and `trace`.
