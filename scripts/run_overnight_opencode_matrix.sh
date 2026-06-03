#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if command -v python >/dev/null 2>&1; then
  PYTHON_CMD=(python)
elif command -v uv >/dev/null 2>&1; then
  PYTHON_CMD=(uv run python)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=(python3)
else
  echo "python, uv, or python3 is required." >&2
  exit 1
fi

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode is required. Install/configure OpenCode and ensure it is on PATH." >&2
  exit 1
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is not set. Set it for model validation and direct OpenRouter judge calls." >&2
  echo "Example: export OPENROUTER_API_KEY='...'" >&2
  exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="runs/overnight_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"
LOG="$OUTPUT_DIR/overnight.log"

{
  echo "Output directory: $OUTPUT_DIR"
  echo "Python: $("${PYTHON_CMD[@]}" --version)"
  echo "OpenCode version:"
  opencode --version || true
  echo "OpenCode help:"
  opencode --help || true
  echo "OpenCode run help:"
  opencode run --help || true
  echo "OpenCode models:"
  opencode models || true

  echo "Validating OpenRouter model config..."
  "${PYTHON_CMD[@]}" -m agentTaxonomy.cli validate-models --models benchmark/configs/models.yaml

  echo "Validating/building fixture snapshots..."
  "${PYTHON_CMD[@]}" -m agentTaxonomy.cli build-fixtures --sources benchmark/repo_sources.yaml

  echo "Running tests..."
  "${PYTHON_CMD[@]}" -m pytest tests

  PREFLIGHT_DIR="runs/preflight_${TIMESTAMP}"
  echo "Running preflight task: $PREFLIGHT_DIR"
  "${PYTHON_CMD[@]}" -m agentTaxonomy.cli run-opencode-task \
    --task-id api_rate_limiting \
    --prompt-level high_specificity \
    --model "openrouter/anthropic/claude-sonnet-4.6" \
    --output-dir "$PREFLIGHT_DIR" \
    --run-judge

  if [[ ! -f "$PREFLIGHT_DIR/score.json" ]]; then
    echo "Preflight run did not produce score.json; refusing to start full matrix." >&2
    exit 1
  fi

  echo "Launching full matrix..."
  "${PYTHON_CMD[@]}" -m agentTaxonomy.cli run-matrix \
    --matrix benchmark/configs/experiment_matrix.yaml \
    --models benchmark/configs/models.yaml \
    --output-dir "$OUTPUT_DIR" \
    --resume

  echo "Summarizing results..."
  "${PYTHON_CMD[@]}" -m agentTaxonomy.cli summarize "$OUTPUT_DIR"
  echo "Final summary: $OUTPUT_DIR/summary/report.md"
} 2>&1 | tee "$LOG"
