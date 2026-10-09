"""Synthetic subprocesses only: no Pi installs, authentication or real settings."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from focus import setup_terminal as t


@pytest.mark.parametrize("name,flags", [
    ("ptyxis", ["--standalone", "--new-window", "--title", "Focus setup", "--"]),
    ("gnome-terminal", ["--wait", "--window", "--title", "Focus setup", "--"]),
    ("konsole", ["--separate", "-p", "tabtitle=Focus setup", "-e"]),
    ("xterm", ["-T", "Focus setup", "-e"]),
])
def test_terminal_launch_argv(monkeypatch, name, flags):
    monkeypatch.setenv("DISPLAY", ":synthetic")
    monkeypatch.setattr(t.shutil, "which", lambda item: "/bin/" + name if item == name else None)
    worker = ["/python with spaces", "-I", "/worker", "/job with spaces"]
    assert t.terminal_command(worker, "Focus setup") == ["/bin/" + name, *flags, *worker]


def test_headless_does_not_launch_gui(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(t.shutil, "which", lambda *args: pytest.fail("headless GUI lookup"))
    assert t.terminal_command(["worker"], "Title") is None


@pytest.mark.parametrize("code", [0, 7])
def test_worker_and_parent_wait_for_real_child(tmp_path, monkeypatch, capsys, code):
    emulator = tmp_path / "fake terminal.py"
    emulator.write_text("import subprocess,sys\n"
                        "p=subprocess.run(sys.argv[1:], input='\\n', text=True)\n"
                        "sys.exit(p.returncode)\n")
    jobs = []

    def launch(worker, title):
        jobs.append(Path(worker[-1]))
        return [sys.executable, str(emulator), *worker]

    monkeypatch.setattr(t, "terminal_command", launch)
    command = [sys.executable, "-c", f"import sys; print('SYNTHETIC STEP'); sys.exit({code})"]
    kwargs = dict(title="Synthetic setup", instructions="No installation happens here.",
                  env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    if code:
        with pytest.raises(t.SetupTerminalError, match="did not finish"):
            t.run_in_terminal(command, **kwargs)
    else:
        t.run_in_terminal(command, **kwargs)
        assert "Back in Focus setup" in capsys.readouterr().out
    assert not jobs[0].parent.exists()


def test_launcher_success_is_not_installation_success(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "terminal_command", lambda *args: [sys.executable, "-c", "pass"])
    with pytest.raises(t.SetupTerminalError, match="closed before completion"):
        t.run_in_terminal(["NEVER_EXECUTED"], title="Synthetic", instructions="Test", env={})


def test_launch_error_does_not_retry_in_original_terminal(monkeypatch):
    monkeypatch.setattr(t, "terminal_command", lambda *args: ["/nonexistent-focus-terminal"])
    with pytest.raises(t.SetupTerminalError, match="no command was retried"):
        t.run_in_terminal(["NEVER_EXECUTED"], title="Synthetic", instructions="Test", env={})


@pytest.mark.parametrize("answer,code", [("\n", 0), ("", 130)])
def test_worker_acknowledgement_and_private_status(tmp_path, answer, code):
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"command": [sys.executable, "-c", "pass"], "env": {},
                               "title": "Synthetic", "instructions": "Nothing installed"}))
    result = subprocess.run([sys.executable, "-I", t.__file__, str(job)], input=answer,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == code
    status = tmp_path / "result.json"
    assert json.loads(status.read_text()) == {"returncode": code}
    assert status.stat().st_mode & 0o777 == 0o600
    assert "return to Focus" in result.stdout


def test_same_terminal_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(t, "terminal_command", lambda *args: None)
    master, slave = os.openpty()
    calls = []
    original_open = open

    def open_tty(path, *args, **kwargs):
        if path == "/dev/tty":
            return os.fdopen(os.dup(slave), "r+b", buffering=0)
        return original_open(path, *args, **kwargs)

    def run(command, **kwargs):
        assert os.isatty(kwargs["stdin"].fileno())
        assert kwargs["stdout"] is kwargs["stdin"] is kwargs["stderr"]
        job = Path(command[-1])
        (job.parent / "result.json").write_text('{"returncode":0}')
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("builtins.open", open_tty)
    monkeypatch.setattr(t.subprocess, "run", run)
    try:
        t.run_in_terminal(["synthetic"], title="Synthetic", instructions="Test", env={})
        assert len(calls) == 1
    finally:
        os.close(master)
        os.close(slave)
