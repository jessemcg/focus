#!/usr/bin/env bash
set -euo pipefail

prompt_file="${FOCUS_AGENT_PROMPT_FILE:-}"
case_root="${FOCUS_AGENT_CASE_ROOT:-$PWD}"
codex_argc="${CODEX_COMMAND_ARGC:-0}"
cache_root="${XDG_CACHE_HOME:-${HOME:-}/.cache}"
codex_command=()

if [[ "$codex_argc" =~ ^[0-9]+$ ]] && (( codex_argc > 0 )); then
  for ((i = 0; i < codex_argc; i++)); do
    var_name="CODEX_COMMAND_ARG_${i}"
    codex_command+=("${!var_name:-}")
  done
else
  codex_command=(codex --profile fireconnect)
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

if [[ -z "${codex_command[0]:-}" ]] || ! command -v "${codex_command[0]}" >/dev/null 2>&1; then
  printf 'Codex executable not found: %s\n' "${codex_command[0]:-}" >&2
  exit 127
fi

cd "$workspace"
mkdir -p "$workspace/tmp"
export TMPDIR="$workspace/tmp"
prompt="$(cat "$prompt_file")"
"${codex_command[@]}" \
  -C "$workspace" \
  --sandbox workspace-write \
  "$prompt"
