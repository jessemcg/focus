#!/usr/bin/env python3
"""Print a short complete-file loader for an explicitly pinned release.

--expanded shows the reviewed bootstrap; --inline preserves the self-contained
form that can provision a missing downloader. Nothing is downloaded or installed.
"""
import argparse
import json
from pathlib import Path
import re
import shlex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--expanded", action="store_true")
    mode.add_argument("--inline", action="store_true")
    parser.add_argument("--downloader", choices=("curl", "wget"), default="curl")
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    release = json.loads((scripts / "install-release.json").read_text())
    ref = release.get("source_ref")
    if not isinstance(ref, str) or not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise SystemExit("Unpublished: no tested source commit is pinned; no executable one-liner generated")
    script = (scripts / "download-bootstrap.sh.in").read_text().replace("@REF@", ref)
    if args.expanded:
        print(script, end="")
    elif args.inline:
        escaped = script.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        print("bash -c $'" + escaped + "' --")
    else:
        bootstrap = release.get("bootstrap_ref")
        if not isinstance(bootstrap, str) or not re.fullmatch(r"[0-9a-f]{40}", bootstrap):
            raise SystemExit("Unpublished bootstrap: no executable short command generated")
        url = f"https://raw.githubusercontent.com/jessemcg/focus/{bootstrap}/scripts/install-bootstrap.sh"
        download = (f'curl -fL --proto =https --tlsv1.2 {url} -o "$f"' if args.downloader == "curl"
                    else f'wget --https-only -O "$f" {url}')
        # Unique mode-600 file, no pipe/process substitution, and no execution on
        # a failed/partial download. Cleanup preserves the download/child status.
        loader = r'f=$(mktemp) || exit; trap "rm -f \"\$f\"" EXIT; ' + download + ' && bash "$f" "$@"'
        print(shlex.join(["bash", "-c", loader, "--"]))


if __name__ == "__main__":
    main()
