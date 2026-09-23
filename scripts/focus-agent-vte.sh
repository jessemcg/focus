#!/usr/bin/env bash
set -euo pipefail

prompt_file="${FOCUS_AGENT_PROMPT_FILE:-}"
case_root="${FOCUS_AGENT_CASE_ROOT:-$PWD}"
pi_project_dir="${FOCUS_PI_PROJECT_DIR:-}"
answer_artifact="${FOCUS_AGENT_ANSWER_ARTIFACT:-}"
run_id="${FOCUS_AGENT_RUN_ID:-}"
runtime_dir="${FOCUS_AGENT_RUNTIME_DIR:-}"
answer_protocol="${FOCUS_AGENT_ANSWER_PROTOCOL:-}"
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
cp -a "$pi_project_dir/." "$workspace/.pi/"
metrics_args=()
project_root="$(cd "$pi_project_dir/.." && pwd)"
export PI_RUN_METRICS_ROOT="${PI_RUN_METRICS_ROOT:-$project_root/.run-metrics/runs}"
collector="${PI_RUN_METRICS_COLLECTOR:-$project_root/../PiRunMetrics/run-collector.ts}"
if [[ "${PI_RUN_METRICS_ENABLED:-1}" != 0 ]]; then
  if [[ "$collector" = /* && -r "$collector" ]]; then
    metrics_args=(--extension "$collector")
  else
    printf 'Pi run metrics: collector unavailable; continuing without collection.\n' >&2
  fi
fi
export PI_RUN_METRICS_APP=focus PI_RUN_METRICS_WORKFLOW=record_question
export PI_RUN_METRICS_REVISION="$(git -C "$project_root" rev-parse HEAD 2>/dev/null || true)"
if git -C "$project_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [[ -n "$(git -C "$project_root" status --porcelain --untracked-files=no 2>/dev/null)" ]]; then
    export PI_RUN_METRICS_DIRTY=1
  else
    export PI_RUN_METRICS_DIRTY=0
  fi
else
  unset PI_RUN_METRICS_DIRTY
fi
cd "$workspace"
export TMPDIR="$workspace/tmp"
prompt="$(cat "$prompt_file")"
"${agent_command[@]}" \
  --approve \
  --no-session \
  --no-extensions \
  "${metrics_args[@]}" \
  --extension "$workspace/.pi/extensions/focus-record-agent.ts" \
  --no-skills \
  --no-prompt-templates \
  --no-themes \
  --no-context-files \
  --system-prompt "$workspace/.pi/SYSTEM.md" \
  --skill "$workspace/.pi/skills/focus-answer-record-questions/SKILL.md" \
  --tools read,focus_record,submit_focus_answer \
  "$prompt"
