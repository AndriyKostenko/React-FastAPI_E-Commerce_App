#!/usr/bin/env bash
# PreToolUse hook for the Bash tool.
# Reads the tool call JSON from stdin, blocks commands that match
# known-destructive patterns, and approves everything else.

set -euo pipefail

input="$(cat)"
command="$(echo "$input" | jq -r '.tool_input.command // empty')"

if [ -z "$command" ]; then
  echo '{"decision": "approve"}'
  exit 0
fi

# Add/remove patterns here as you see fit. Matching is case-insensitive.
blocked_patterns=(
  'rm[[:space:]]+-[a-zA-Z]*r[a-zA-Z]*f'   # rm -rf, rm -fr, rm -Rf, etc.
  'rm[[:space:]]+-[a-zA-Z]*f[a-zA-Z]*r'
  'git[[:space:]]+push[[:space:]]+.*--force'
  'git[[:space:]]+push[[:space:]]+.*-f([[:space:]]|$)'
  'git[[:space:]]+reset[[:space:]]+--hard'
  'git[[:space:]]+clean[[:space:]]+.*-[a-zA-Z]*f[a-zA-Z]*d'
  'drop[[:space:]]+(database|table|schema)'
  'truncate[[:space:]]+table'
  '>[[:space:]]*/dev/(sd|nvme|disk)'
  'mkfs\.'
  ':\(\)\{.*\}.*;.*:'                      # fork bomb
  'chmod[[:space:]]+-R[[:space:]]+000'
  'chown[[:space:]]+-R[[:space:]]+.*[[:space:]]/'
)

lower_command="$(echo "$command" | tr '[:upper:]' '[:lower:]')"

# Protected file/path patterns — any command that reads, writes, moves,
# copies, or deletes something matching these is blocked outright,
# regardless of which command (rm, cat, mv, cp, echo >, etc.) is used.
protected_paths=(
  '\.env([.\][a-z]*)?([[:space:]]|$)'      # .env, .env.local, .env.production, etc.
  'secrets?/'
  '\.pem([[:space:]]|$)'
  '\.key([[:space:]]|$)'
  'id_rsa'
  'id_ed25519'
  '\.pgpass'
  'credentials\.json'
  '\.aws/'
  '\.ssh/'
)

for pattern in "${protected_paths[@]}"; do
  if echo "$lower_command" | grep -qE "$pattern"; then
    reason="Blocked by guard-bash.sh: command touches a protected/sensitive path ('$pattern'). Edit or view this file manually outside Claude Code if intentional."
    jq -n --arg reason "$reason" '{decision: "block", reason: $reason}'
    exit 0
  fi
done

for pattern in "${blocked_patterns[@]}"; do
  if echo "$lower_command" | grep -qE "$pattern"; then
    reason="Blocked by guard-bash.sh: command matches destructive pattern ('$pattern'). If this is intentional, run it manually outside Claude Code."
    jq -n --arg reason "$reason" '{decision: "block", reason: $reason}'
    exit 0
  fi
done

echo '{"decision": "approve"}'
