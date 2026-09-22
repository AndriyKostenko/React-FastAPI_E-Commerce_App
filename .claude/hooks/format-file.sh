#!/usr/bin/env bash
# PostToolUse hook for Edit/Write.
# Reads the tool call JSON from stdin and runs the appropriate
# formatter/linter on whatever file Claude just touched, based on
# your stack: Prettier for JS/TS/React, Ruff + Black for Python.
# Non-blocking: formatting failures are logged but never fail the hook.

set -uo pipefail

input="$(cat)"
file_path="$(echo "$input" | jq -r '.tool_input.file_path // empty')"

if [ -z "$file_path" ] || [ ! -f "$file_path" ]; then
  exit 0
fi

log() {
  echo "[format-file] $1" >> "$(dirname "$file_path")/.claude-format.log" 2>/dev/null || true
}

case "$file_path" in
  *.ts|*.tsx|*.js|*.jsx|*.json|*.css|*.scss|*.md)
    if command -v npx >/dev/null 2>&1; then
      npx --yes prettier --write "$file_path" >/dev/null 2>&1 \
        && log "prettier formatted $file_path" \
        || log "prettier failed on $file_path (no config? not installed?)"
    fi
    ;;
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff check --fix "$file_path" >/dev/null 2>&1
      ruff format "$file_path" >/dev/null 2>&1 \
        && log "ruff formatted $file_path"
    elif command -v black >/dev/null 2>&1; then
      black --quiet "$file_path" >/dev/null 2>&1 \
        && log "black formatted $file_path"
    else
      log "no python formatter found (install ruff or black) for $file_path"
    fi
    ;;
  *)
    ;;
esac

exit 0
