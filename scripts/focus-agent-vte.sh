#!/usr/bin/env bash
set -euo pipefail

prompt_file="${FOCUS_AGENT_PROMPT_FILE:-}"
case_root="${FOCUS_AGENT_CASE_ROOT:-$PWD}"
pi_project_dir="${FOCUS_PI_PROJECT_DIR:-}"
answer_artifact="${FOCUS_AGENT_ANSWER_ARTIFACT:-}"
run_id="${FOCUS_AGENT_RUN_ID:-}"
runtime_dir="${FOCUS_AGENT_RUNTIME_DIR:-}"
answer_protocol="${FOCUS_AGENT_ANSWER_PROTOCOL:-}"
session_preserve_dir="${FOCUS_AGENT_SESSION_PRESERVE_DIR:-}"
agent_argc="${FOCUS_AGENT_COMMAND_ARGC:-0}"
cache_root="${XDG_CACHE_HOME:-${HOME:-}/.cache}"
agent_command=()

if [[ "$agent_argc" =~ ^[0-9]+$ ]] && (( agent_argc > 0 )); then
  for ((i = 0; i < agent_argc; i++)); do
    var_name="FOCUS_AGENT_COMMAND_ARG_${i}"
    agent_command+=("${!var_name:-}")
  done
else
  agent_command=(pi)
fi

if [[ -z "$cache_root" ]]; then
  printf 'Focus Agent cache directory unavailable: set HOME or XDG_CACHE_HOME.\n' >&2
  exit 2
fi

workspace_parent="$cache_root/focus-agent-workspaces"
mkdir -p "$workspace_parent"
if [[ -n "${FOCUS_AGENT_WORKSPACE:-}" ]]; then
  workspace="$FOCUS_AGENT_WORKSPACE"
  mkdir -p "$workspace"
else
  workspace="$(mktemp -d "$workspace_parent/workspace.XXXXXX")"
fi

cleanup() {
  # Preserve the session JSONL for post-run Copy Trace diagnostics before the
  # disposable workspace is removed. Best-effort: a failure here must not block
  # workspace cleanup.
  if [[ -n "$session_preserve_dir" && -n "$run_id" && -d "$workspace/pi-sessions" ]]; then
    mkdir -p "$session_preserve_dir" 2>/dev/null || true
    latest_session="$(ls -t "$workspace/pi-sessions"/*.jsonl 2>/dev/null | head -n 1 || true)"
    if [[ -n "$latest_session" ]]; then
      mv -f "$latest_session" "$session_preserve_dir/${run_id}.jsonl" 2>/dev/null || true
    fi
  fi
  rm -rf "$workspace"
  rm -f "$prompt_file"
}
trap cleanup EXIT

if [[ -z "$prompt_file" || ! -f "$prompt_file" ]]; then
  printf 'Focus Agent prompt file not found: %s\n' "$prompt_file" >&2
  exit 2
fi

if [[ ! -d "$case_root" ]]; then
  printf 'Focus Agent case root not found: %s\n' "$case_root" >&2
  exit 2
fi

if [[ -z "$pi_project_dir" || ! -f "$pi_project_dir/settings.json" ]]; then
  printf 'Focus PI project settings not found: %s\n' "$pi_project_dir/settings.json" >&2
  exit 2
fi

if [[ ! -s "$pi_project_dir/SYSTEM.md" ]]; then
  printf 'Focus PI system prompt not found or empty: %s\n' \
    "$pi_project_dir/SYSTEM.md" >&2
  exit 2
fi

if [[ ! -f "$pi_project_dir/skills/focus-answer-record-questions/SKILL.md" ]]; then
  printf 'Focus PI record-question skill not found: %s\n' \
    "$pi_project_dir/skills/focus-answer-record-questions/SKILL.md" >&2
  exit 2
fi

if [[ ! -s "$pi_project_dir/extensions/focus-record-agent.ts" ]]; then
  printf 'Focus record extension not found or empty: %s\n' \
    "$pi_project_dir/extensions/focus-record-agent.ts" >&2
  exit 2
fi

if [[ -z "$answer_artifact" || -z "$run_id" || -z "$runtime_dir" || ! -f "$answer_protocol" ]]; then
  printf 'Focus answer protocol resources are unavailable.\n' >&2
  exit 2
fi

if [[ ! "$answer_artifact" = "$runtime_dir"/* ]]; then
  printf 'Focus answer artifact must be under the Focus runtime directory.\n' >&2
  exit 2
fi

if [[ -z "${agent_command[0]:-}" ]] || ! command -v "${agent_command[0]}" >/dev/null 2>&1; then
  printf 'Focus Agent executable not found: %s\n' "${agent_command[0]:-}" >&2
  exit 127
fi

mkdir -p "$workspace/tmp"
mkdir -p "$workspace/.pi"
mkdir -p "$workspace/pi-sessions"
cp -a "$pi_project_dir/." "$workspace/.pi/"
cd "$workspace"
export TMPDIR="$workspace/tmp"
export PI_CODING_AGENT_SESSION_DIR="$workspace/pi-sessions"
prompt="$(cat "$prompt_file")"
"${agent_command[@]}" \
  --approve \
  --no-extensions \
  --extension "$workspace/.pi/extensions/focus-record-agent.ts" \
  --no-skills \
  --no-prompt-templates \
  --no-themes \
  --no-context-files \
  --system-prompt "$workspace/.pi/SYSTEM.md" \
  --skill "$workspace/.pi/skills/focus-answer-record-questions/SKILL.md" \
  --tools read,focus_record,submit_focus_answer \
  "$prompt"
