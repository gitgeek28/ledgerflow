#!/usr/bin/env bash
# Start API, worker and web app together; Ctrl-C stops all three.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
trap 'kill 0' EXIT INT TERM
(cd "$ROOT/backend" && uv run alembic upgrade head && uv run python -m app.seed.seed >/dev/null)
(cd "$ROOT/backend" && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app) &
(cd "$ROOT/backend" && uv run python -m app.workers.runner) &
(cd "$ROOT/frontend" && npm run dev) &
echo "LedgerFlow: web http://localhost:3000  ·  API docs http://localhost:3000/api/docs"
wait
