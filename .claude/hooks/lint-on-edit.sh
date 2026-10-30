#!/usr/bin/env bash
# PostToolUse(Edit|Write|MultiEdit) hook: formatea y lintea el .py editado con
# el ruff del proyecto. Bloquea (exit 2) solo si quedan errores despues de
# --fix, asi el agente los ve en el momento y no en el PR.
set -uo pipefail

payload="$(cat)"
f="$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' <<<"$payload" 2>/dev/null)"
[ -n "$f" ] && [ -f "$f" ] || exit 0
[ "${f##*.}" = "py" ] || exit 0

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$f")}" || exit 0
command -v uv >/dev/null || exit 0

uv run --quiet ruff format "$f" >/dev/null 2>&1 || true
uv run --quiet ruff check --fix "$f" >/dev/null 2>&1 || true

if output="$(uv run --quiet ruff check "$f" 2>&1)"; then
  exit 0
else
  printf '%s\n' "$output" >&2
  exit 2
fi
