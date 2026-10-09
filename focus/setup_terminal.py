"""Private, synchronous terminal handoff for installation/login, without transcripts.

Also runs as a stdlib-only worker via this file's absolute path and Python -I.
A terminal-launcher's exit code alone is never proof that its command completed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


class SetupTerminalError(RuntimeError):
    pass


def terminal_command(worker: list[str], title: str) -> list[str] | None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    # Dedicated instances/windows and wait semantics; no tabs in the user's shell.
    candidates = (
        ("ptyxis", ["--standalone", "--new-window", "--title", title, "--"]),
        ("gnome-terminal", ["--wait", "--window", "--title", title, "--"]),
        ("konsole", ["--separate", "-p", f"tabtitle={title}", "-e"]),
        ("xterm", ["-T", title, "-e"]),
    )
    for name, flags in candidates:
        executable = shutil.which(name)
        if executable:
            return [executable, *flags, *worker]
    return None


def run_in_terminal(command: list[str], *, title: str, instructions: str,
                    env: dict[str, str]) -> None:
    """Wait for the actual child, then return to the original Focus setup."""
    with tempfile.TemporaryDirectory(prefix="focus-setup-terminal-") as directory:
        root = Path(directory)
        job = root / "job.json"
        result = root / "result.json"
        # Only the caller's filtered desktop environment, never a shell snapshot.
        with job.open("x", encoding="utf-8") as stream:
            os.chmod(job, 0o600)
            json.dump({"command": command, "env": env, "title": title,
                       "instructions": instructions}, stream)
        worker = [sys.executable, "-I", str(Path(__file__).resolve()), str(job)]
        launcher = terminal_command(worker, title)
        if launcher:
            print(f"[WAIT] Opening {title} in a separate terminal.\n"
                  "Keep this Focus installer open. It will continue automatically\n"
                  "when you finish and press Enter in the other window.", flush=True)
            try:
                completed = subprocess.run(launcher, cwd=root, env=env, check=False)
            except OSError as exc:
                raise SetupTerminalError("Could not open the setup terminal; no command was retried") from exc
        else:
            print("[INFO] No supported desktop terminal available; continuing here.\n"
                  "Focus will continue automatically when this step finishes.", flush=True)
            try:
                with open("/dev/tty", "r+b", buffering=0) as tty:
                    completed = subprocess.run(worker, cwd=root, env=env, stdin=tty,
                                               stdout=tty, stderr=tty, check=False)
            except OSError as exc:
                raise SetupTerminalError("An interactive terminal is required for Pi setup") from exc
        try:
            code = json.loads(result.read_text(encoding="utf-8"))["returncode"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SetupTerminalError(
                "Pi setup window closed before completion or could not start. "
                "Focus installation remains incomplete; no automatic retry.") from exc
        if type(code) is not int or code != 0 or completed.returncode != 0:
            raise SetupTerminalError("Pi setup did not finish successfully; Focus installation remains incomplete")
        print("[OK] Back in Focus setup. Checking Pi before continuing...", flush=True)


def worker(job: Path) -> int:
    """Keep all authentication I/O in the new terminal, not a log or parent pipe."""
    data = json.loads(job.read_text(encoding="utf-8"))
    print(f"\n{data['title']}\n{'=' * len(data['title'])}\n{data['instructions']}\n", flush=True)
    try:
        code = subprocess.run(data["command"], cwd=job.parent, env=data["env"],
                              check=False).returncode
    except KeyboardInterrupt:
        code = 130
    except OSError as exc:
        print(f"[FAIL] Could not start setup: {exc}", flush=True)
        code = 1
    if code == 0:
        print("\n[OK] This step has finished. Focus will check the result and continue.\n"
              "You do not need to restart your shell or rerun the Focus installer.", flush=True)
    else:
        print(f"\n[FAIL] This step stopped (exit {code}). Return to Focus for next steps.", flush=True)
    # Keep the result visible until acknowledged. Closing early is not success.
    try:
        input("Press Enter to close this window and return to Focus setup: ")
    except (EOFError, KeyboardInterrupt):
        code = code or 130
    result = job.parent / "result.json"
    temporary = job.parent / "result.tmp"
    with temporary.open("x", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump({"returncode": code}, stream)
    os.replace(temporary, result)
    return code if 0 <= code <= 255 else 1


if __name__ == "__main__":
    raise SystemExit(worker(Path(sys.argv[1])))
