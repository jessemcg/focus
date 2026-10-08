#!/usr/bin/env python3
"""Render inspectable download instructions only for an explicitly pinned release.

No network, publication or installation occurs. A pin is not proof of independent
source authentication; release maintainers must publish/test it explicitly first.
"""
import argparse
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded", action="store_true")
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    ref = json.loads((scripts / "install-release.json").read_text()).get("source_ref")
    if not isinstance(ref, str) or not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise SystemExit("Unpublished: no tested source commit is pinned; no executable one-liner generated")
    script = (scripts / "download-bootstrap.sh.in").read_text().replace("@REF@", ref)
    if args.expanded:
        print(script, end="")
    else:
        # Bash ANSI-C quoting makes this a physical one-liner while preserving the
        # readable script's exact shell structure; downloaded code is never piped.
        escaped = script.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        print("bash -c $'" + escaped + "' --")


if __name__ == "__main__":
    main()
