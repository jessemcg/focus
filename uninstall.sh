#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/python3 -I "$root/scripts/focus_maintenance.py" uninstall "$@"
