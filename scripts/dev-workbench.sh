#!/usr/bin/env bash
# Local CaT workbench: source .env, start Postgres, migrate, bootstrap, API, and UI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker/compose.local.yml"
DEFAULT_DATABASE_URL="postgresql+psycopg://cat:cat_dev_password@localhost:54321/cat"
API_HOST="${CAT_WEB_HOST:-127.0.0.1}"
API_PORT="${CAT_WEB_PORT:-8080}"
UI_PORT="${CAT_UI_PORT:-5173}"

usage() {
  cat <<'EOF'
Usage: scripts/dev-workbench.sh <command>

Commands:
  setup     Start Postgres, run migrations, bootstrap catalog/prompts/runs
  api       Run FastAPI backend (sources .env, blocks until Ctrl+C)
  ui        Run Vite dev server for the workbench UI
  dev       setup + api in background + ui in foreground
  env       Print export commands after sourcing .env (for manual shells)

Environment (optional overrides):
  DATABASE_URL, CAT_DATABASE_URL
  CAT_WEB_HOST, CAT_WEB_PORT, CAT_UI_PORT

Examples:
  scripts/dev-workbench.sh setup
  scripts/dev-workbench.sh api          # terminal 1
  scripts/dev-workbench.sh ui           # terminal 2
  scripts/dev-workbench.sh dev          # all-in-one (api backgrounded)
EOF
}

source_env() {
  if [[ -f "$ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT/.env"
    set +a
    echo "Sourced $ROOT/.env"
  else
    echo "No .env file at $ROOT/.env — copy from .env.example and set OPENROUTER_API_KEY" >&2
  fi
  export DATABASE_URL="${DATABASE_URL:-${CAT_DATABASE_URL:-$DEFAULT_DATABASE_URL}}"
  export PYTHONPATH="${PYTHONPATH:-src}"
}

wait_for_postgres() {
  local attempts=0
  until docker exec cat-postgres pg_isready -U cat -d cat >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [[ "$attempts" -ge 30 ]]; then
      echo "Postgres did not become ready in time." >&2
      exit 1
    fi
    sleep 1
  done
  echo "Postgres is ready."
}

cmd_setup() {
  source_env
  docker compose -f "$COMPOSE_FILE" up -d db
  wait_for_postgres
  uv run catt db migrate --database-url "$DATABASE_URL"
  uv run catt db bootstrap --database-url "$DATABASE_URL"
  echo ""
  echo "Setup complete."
  echo "  API: http://${API_HOST}:${API_PORT}"
  echo "  UI:  http://127.0.0.1:${UI_PORT}  (after: scripts/dev-workbench.sh ui)"
}

needs_local_postgres() {
  [[ "$DATABASE_URL" == *"@localhost:54321/"* || "$DATABASE_URL" == *"@127.0.0.1:54321/"* ]]
}

cmd_api() {
  source_env
  if needs_local_postgres; then
    docker compose -f "$COMPOSE_FILE" up -d db
    wait_for_postgres
  fi
  if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "Warning: OPENROUTER_API_KEY is not set; /api/openrouter/usage and generate will fail." >&2
  fi
  echo "Starting API at http://${API_HOST}:${API_PORT} (DATABASE_URL set; reload watches src/ only)"
  exec uv run catt web --host "$API_HOST" --port "$API_PORT" --database-url "$DATABASE_URL" --reload
}

cmd_ui() {
  cd "$ROOT/web"
  echo "Starting UI at http://127.0.0.1:${UI_PORT} (proxy -> ${VITE_API_BASE:-http://localhost:8080})"
  exec npm run dev -- --host 127.0.0.1 --port "$UI_PORT"
}

cmd_dev() {
  source_env
  cmd_setup
  echo "Starting API in background…"
  uv run catt web --host "$API_HOST" --port "$API_PORT" --database-url "$DATABASE_URL" --reload &
  API_PID=$!
  trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
  sleep 2
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "API process exited early." >&2
    exit 1
  fi
  echo "API pid=$API_PID — http://${API_HOST}:${API_PORT}"
  cmd_ui
}

cmd_env() {
  source_env
  echo "export DATABASE_URL=\"$DATABASE_URL\""
  echo "export PYTHONPATH=\"$PYTHONPATH\""
  if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
    echo "export OPENROUTER_API_KEY=\"(set, ${#OPENROUTER_API_KEY} chars)\""
  else
    echo "# OPENROUTER_API_KEY is not set — add it to .env"
  fi
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    setup) cmd_setup ;;
    api) cmd_api ;;
    ui) cmd_ui ;;
    dev) cmd_dev ;;
    env) cmd_env ;;
    -h|--help|help|"") usage ;;
    *)
      echo "Unknown command: $cmd" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
