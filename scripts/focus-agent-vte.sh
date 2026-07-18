#!/usr/bin/env bash
set -euo pipefail

prompt_file="${FOCUS_AGENT_PROMPT_FILE:-}"
case_root="${FOCUS_AGENT_CASE_ROOT:-$PWD}"
agent_runtime="${FOCUS_AGENT_RUNTIME:-codex}"
agent_argc="${FOCUS_AGENT_COMMAND_ARGC:-0}"
cache_root="${XDG_CACHE_HOME:-${HOME:-}/.cache}"
codex_sandbox="${FOCUS_CODEX_AGENT_SANDBOX:-workspace-write}"
codex_approval="${FOCUS_CODEX_AGENT_APPROVAL:-}"
agent_command=()

if [[ "$agent_argc" =~ ^[0-9]+$ ]] && (( agent_argc > 0 )); then
  for ((i = 0; i < agent_argc; i++)); do
    var_name="FOCUS_AGENT_COMMAND_ARG_${i}"
    agent_command+=("${!var_name:-}")
  done
elif [[ "$agent_runtime" == "pi" ]]; then
  agent_command=(pi)
else
  agent_command=(codex --profile fireconnect)
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

if [[ -z "${agent_command[0]:-}" ]] || ! command -v "${agent_command[0]}" >/dev/null 2>&1; then
  printf 'Focus Agent executable not found: %s\n' "${agent_command[0]:-}" >&2
  exit 127
fi

cd "$workspace"
mkdir -p "$workspace/tmp"
export TMPDIR="$workspace/tmp"
prompt="$(cat "$prompt_file")"

if [[ "$agent_runtime" == "pi" ]]; then
  "${agent_command[@]}" "$prompt"
  exit $?
fi

case "$codex_sandbox" in
  read-only|workspace-write|danger-full-access) ;;
  *) codex_sandbox="workspace-write" ;;
esac

case "$codex_approval" in
  ""|untrusted|on-request|on-failure|never) ;;
  *) codex_approval="" ;;
esac

approval_args=()
if [[ -n "$codex_approval" ]]; then
  approval_args=(--ask-for-approval "$codex_approval")
fi

"${agent_command[@]}" \
  -C "$workspace" \
  --sandbox "$codex_sandbox" \
  "${approval_args[@]}" \
  "$prompt"
