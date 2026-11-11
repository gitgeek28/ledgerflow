#!/usr/bin/env bash
# Run the evaluation harness against the isolated test database. Pass --llm to enable the Ollama fallback.
set -euo pipefail
cd "$(dirname "$0")/../backend"
uv run python -m app.seed.evaluate "$@"
