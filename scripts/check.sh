#!/usr/bin/env bash
# Lo mismo que corre CI: formato, lint, tipos y tests. Usado por gh-flow.sh pr.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
bash scripts/check_secrets.sh
