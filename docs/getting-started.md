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

After `uv sync`, use `uv run uab` or `uv run python -m agentTaxonomy.cli`. For ad hoc use
without uv, set `PYTHONPATH=src`.

## Build the catalog

Regenerate `benchmark/generated/catalog.json` whenever task metadata or prompt files change:

```bash
uv run uab build-catalog
uv run uab validate-catalog
```

## Generate a run

```bash
uv run uab generate-run \
  --prompt-file benchmark/task_catalog/subject_areas/map_reduce_spark_log_analytics/levels/beginner.md \
  --model moonshotai/kimi-k2.5 \
  --instance-id map_reduce_spark_log_analytics__beginner \
  --output-dir runs/map_reduce_spark_log_analytics/beginner
```

This writes `request.json`, `raw_response.json`, `agent_output.md`, and `trace.jsonl` under the
output directory.

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
