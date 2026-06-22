#!/usr/bin/env bash
set -euo pipefail

prompt_file="${FOCUS_AGENT_PROMPT_FILE:-}"
case_root="${FOCUS_AGENT_CASE_ROOT:-$PWD}"
codex_bin="${CODEX_BIN:-codex}"
codex_profile="${CODEX_PROFILE:-fireworks}"
cache_root="${XDG_CACHE_HOME:-${HOME:-}/.cache}"

if [[ -z "$cache_root" ]]; then
  printf 'Focus Agent cache directory unavailable: set HOME or XDG_CACHE_HOME.\n' >&2
  exit 2
fi

workspace_parent="$cache_root/focus-agent-workspaces"
mkdir -p "$workspace_parent"
workspace="$(mktemp -d "$workspace_parent/workspace.XXXXXX")"

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

if ! command -v "$codex_bin" >/dev/null 2>&1; then
  printf 'Codex executable not found: %s\n' "$codex_bin" >&2
  exit 127
fi

cd "$workspace"
mkdir -p "$workspace/tmp"
export TMPDIR="$workspace/tmp"
prompt="$(cat "$prompt_file")"
"$codex_bin" \
  --profile "$codex_profile" \
  -C "$workspace" \
  --sandbox workspace-write \
  "$prompt"
