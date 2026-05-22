# Getting Started

## Requirements

- Python 3.11 or newer
- An [OpenRouter](https://openrouter.ai/) API key for generation and LLM-based judging

## Environment

[uv](https://docs.astral.sh/uv/) is the recommended tool for installing dependencies and
running commands.

```bash
uv sync
```

The CLI reads `OPENROUTER_API_KEY` from the environment. Copy the example file and load it in your shell:

```bash
cp .env.example .env
set -a && source .env && set +a
```

Recommended variables:

```bash
OPENROUTER_API_KEY=your_key_here
PYTHONDONTWRITEBYTECODE=1
```

After `uv sync`, use `uv run catt` or `uv run python -m agentTaxonomy.cli`. For ad hoc use
without uv, set `PYTHONPATH=src`.

## Build the catalog

Regenerate `benchmark/generated/catalog.json` whenever task metadata or prompt files change:

```bash
uv run catt build-catalog
uv run catt validate-catalog
```

## Generate a run

```bash
uv run catt generate-run \
  --prompt-file benchmark/task_catalog/subject_areas/map_reduce_spark_log_analytics/levels/beginner.md \
  --model moonshotai/kimi-k2.5 \
  --instance-id map_reduce_spark_log_analytics__beginner \
  --output-dir runs/map_reduce_spark_log_analytics/beginner
```

This writes `request.json`, `raw_response.json`, `agent_output.md`, and `trace.jsonl` under the
output directory.

Always pass `--instance-id` so scoring and judges resolve the correct catalog metadata.

## Evaluate a generative run

After generation, collect static evidence before scoring. Use the same output directory for all
steps:

```bash
export RUN=runs/map_reduce_spark_log_analytics/beginner
export INSTANCE=map_reduce_spark_log_analytics__beginner

uv run catt extract-artifacts \
  --artifact "$RUN/agent_output.md" \
  --output-dir "$RUN/extracted"

uv run catt static-audit \
  --instance-id "$INSTANCE" \
  --artifact-dir "$RUN/extracted" \
  --output "$RUN/audit.json"

uv run catt enrich-supply-chain \
  --artifact-dir "$RUN/extracted" \
  --output "$RUN/supply_chain.json"

uv run catt score-run \
  --instance-id "$INSTANCE" \
  --trace "$RUN/trace.jsonl" \
  --verification-tier static \
  --audit-report "$RUN/audit.json" \
  --supply-chain-report "$RUN/supply_chain.json" \
  --judge-model openai/gpt-4o \
  --judge-response-format json_schema \
  --full-execution-skipped \
  --skip-reason "local static tier only" \
  --output "$RUN/score.json"
```

See [Evaluation](evaluation.md) for how to read `score.json` and when `security_adjusted_success`
differs from `provisional_security_success`.

## Index runs into the local workbench

Raw run artifacts remain canonical. The workbench database indexes those files with source hashes,
schema versions, ingest versions, evaluations, findings, and annotation records.

Bootstrap indexes the catalog, task prompt variants, judge templates, runs, and split metadata in
one idempotent pass:

```bash
uv run catt db migrate
uv run catt db bootstrap
```

For a quick local SQLite-backed browser:

```bash
uv run catt db init
uv run catt db ingest-catalog benchmark/generated/catalog.json
uv run catt db ingest-run runs/map_reduce_spark_log_analytics/beginner_gpt55
uv run catt web --host 127.0.0.1 --port 8080
```

For the Postgres + API + UI stack:

```bash
docker compose -f docker/compose.local.yml up
```

Local endpoints:

```text
API: http://localhost:8080
UI:  http://localhost:5173
DB:  localhost:54321
```

Repeated run ingest is idempotent: the same `run_dir` with the same source hash is a no-op. If the
same `run_dir` has different content, ingest fails unless you pass `--new-ingest-version`.

Analysis exports:

```bash
uv run catt db export-runs runs.csv
uv run catt db export-findings findings.csv
uv run catt db export-evaluations evaluations.csv
uv run catt db export-wide analysis.csv
```

Use `.parquet` outputs after installing the analysis dependency group:

```bash
uv sync --group analysis
uv run catt db export-evaluations evaluations.parquet
```

## Workbench success criterion (8 steps)

You have a working local workbench when you can complete all of the following:

1. `docker compose -f docker/compose.local.yml up -d db` and `uv run catt db migrate`.
2. `uv run catt db bootstrap` (catalog, task prompts, judge templates, runs).
3. `uv run catt web --host 127.0.0.1 --port 8080` and `cd web && npm run dev`.
4. Open the app → **Dashboard** → **Bootstrap** if the catalog is empty.
5. **Prompts** → select an instance prompt → **Generate from prompt**.
6. **Runs** → open a run → **Run Judge Pipeline** → **Ingest** if needed.
7. **Run Detail** → **Score** tab + annotation drawer (artifact lines + trace events).
8. **Exports** → analysis wide CSV, or `uv run catt db export-wide analysis.csv`.

Start the full stack (sources `.env`, starts Postgres, migrates, bootstraps):

```bash
./scripts/dev-workbench.sh setup    # once per machine / after catalog changes
./scripts/dev-workbench.sh api      # terminal 1 — API on :8080
./scripts/dev-workbench.sh ui       # terminal 2 — UI on :5173
```

Or all-in-one (API backgrounded):

```bash
./scripts/dev-workbench.sh dev
```

Manual equivalent:

```bash
docker compose -f docker/compose.local.yml up -d db
uv run catt db migrate --database-url postgresql+psycopg://cat:cat_dev_password@localhost:54321/cat
DATABASE_URL=postgresql+psycopg://cat:cat_dev_password@localhost:54321/cat uv run catt db bootstrap
set -a && source .env && set +a
DATABASE_URL=postgresql+psycopg://cat:cat_dev_password@localhost:54321/cat uv run catt web --host 127.0.0.1 --port 8080
cd web && npm run dev
```

## Run tests

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```

## Build documentation

```bash
uv sync --group docs
python3 scripts/build_docs.py
python3 scripts/build_docs.py --serve   # http://127.0.0.1:8000
```

Output is written to `site/`.
