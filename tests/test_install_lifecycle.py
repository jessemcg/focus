"""Install/fail/resume/repair/remove in a disposable Git source and HOME.

Only git and desktop-file-validate execute natively; package/auth/uv are fixtures.
"""
import argparse
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_source_installer import ROOT, m, sandbox


@pytest.fixture
def lifecycle(sandbox, monkeypatch, tmp_path):
    paths, data = sandbox
    repo = tmp_path / "published-fixture"; repo.mkdir()
    for name in ("pyproject.toml", "uv.lock", "focus.svg", "focus-symbolic.svg", "focus.png", "install.sh"):
        shutil.copyfile(ROOT / name, repo / name)
    for name in ("scripts", "focus/agent_resources"):
        shutil.copytree(ROOT / name, repo / name, ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run(["git", "init", "-q", "--initial-branch=main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "fixture"], check=True)
    revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setenv("FOCUS_INSTALL_REF", revision)
    monkeypatch.setattr(m, "REPOSITORY", str(repo))
    monkeypatch.setattr(m, "detect_platform", lambda: "apt")
    monkeypatch.setattr(m, "approve", lambda *a: None)
    monkeypatch.setattr(m, "continue_pi_install", lambda: False)
    monkeypatch.setattr(m, "install_optional_pi", lambda *a: pytest.fail("Unexpected Pi install"))
    monkeypatch.setattr(m, "native_meets", lambda *a: True)
    monkeypatch.setattr(m, "active_processes", lambda *a: [])
    monkeypatch.setattr(m, "refresh_caches", lambda *a: None)
    monkeypatch.setattr(m.Packages, "snapshot", lambda *a: {"git", "curl"})
    monkeypatch.setattr(m.Packages, "missing", lambda *a: [])
    monkeypatch.setattr(m.Packages, "install", lambda *a: None)
    monkeypatch.setattr(m, "verify_environment", lambda *a: {})
    calls = []
    original = m.execute
    failing = [False]
    def execute(command, **kwargs):
        calls.append(command)
        if command[0] in ("git", "desktop-file-validate"):
            return original(command, **kwargs)
        if "setup-pi" in command or "doctor" in command:
            pytest.fail("Focus installation must not require AI onboarding or verification")
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(m, "execute", execute)
    def sync(paths, data, save, dev=False):
        for name in ("environment", "python", "tools", "cache"):
            if not paths[name].exists():
                paths[name].mkdir(parents=True); m.marker(paths[name], data["installation_id"], paths["source"])
                if name not in data["created"]: data["created"].append(name)
        data["dependency_fingerprint"] = m.fingerprint(paths["source"]); save()
    monkeypatch.setattr(m, "synchronize", sync)
    args = argparse.Namespace(source_dir=str(paths["source"]), payload_root=str(ROOT), dry_run=False,
                              resume=False, repair=False, login=False, provider="synthetic", model="fixture",
                              thinking="off", approve_verification=True)
    return paths, args, calls, failing


def test_default_installs_latest_main_and_repair_preserves_checkout(lifecycle, monkeypatch):
    paths, args, calls, _ = lifecycle
    monkeypatch.delenv("FOCUS_INSTALL_REF")
    repo = Path(m.REPOSITORY)
    (repo / "latest.txt").write_text("new main code")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Synthetic", "-c",
                    "user.email=synthetic@example.invalid", "commit", "-qm", "latest"], check=True)
    latest = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    # A different remote default branch must not change the main selection.
    subprocess.run(["git", "-C", str(repo), "checkout", "-qb", "other", "HEAD~1"], check=True)
    assert m.install(args) == 0
    receipt = m.private_json(paths["state"] / "receipt.json")
    assert receipt["source_ref"] == "main" and receipt["source_revision"] == latest
    assert (paths["source"] / "latest.txt").read_text() == "new main code"
    (paths["source"] / "latest.txt").write_text("local edits")
    calls.clear()
    args.repair = True
    assert m.install(args) == 0
    assert (paths["source"] / "latest.txt").read_text() == "local edits"
    assert not any(call[:2] == ["git", "clone"] or "switch" in call or "fetch" in call for call in calls)


def test_complete_repair_and_normal_uninstall(lifecycle):
    paths, args, calls, _ = lifecycle
    assert m.install(args) == 0
    receipt = m.private_json(paths["state"] / "receipt.json")
    assert receipt["phase"] == "complete" and paths["desktop"].exists()
    assert paths["source"] != paths["environment"] and (paths["source"] / ".git").is_dir()
    changed = paths["source"] / "user-edit.txt"; changed.write_text("synthetic editable source")
    args.repair = True
    assert m.install(args) == 0
    assert changed.read_text() == "synthetic editable source"
    assert not any(any(arg in {"reset", "clean", "stash"} for arg in call) for call in calls)
    assert m.uninstall(argparse.Namespace(dry_run=False, purge=False, cleanup_packages=False, cleanup_pi=False)) == 0
    assert changed.exists() and paths["config"].exists()
    assert not paths["desktop"].exists() and not paths["environment"].exists()


def test_repair_retains_original_pi_resource_ownership(lifecycle, monkeypatch):
    paths, args, _, _ = lifecycle
    agent = Path.home() / ".pi/agent/install"
    def introduces_pi(env):
        assert m.private_json(paths["state"] / "receipt.json")["phase"] == "complete"
        agent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(m, "continue_pi_install", lambda: True)
    monkeypatch.setattr(m, "install_optional_pi", introduces_pi)
    assert m.install(args) == 0
    assert str(agent) in m.private_json(paths["state"] / "receipt.json")["introduced_pi_resources"]
    args.repair = True
    assert m.install(args) == 0
    assert str(agent) in m.private_json(paths["state"] / "receipt.json")["introduced_pi_resources"]


@pytest.mark.parametrize("failure", [None, RuntimeError("synthetic Pi failure"), KeyboardInterrupt()])
def test_focus_completes_before_optional_pi_and_survives_failure(lifecycle, monkeypatch, capsys, failure):
    paths, args, calls, _ = lifecycle
    monkeypatch.setattr(m, "continue_pi_install", lambda: True)

    def optional(env):
        assert m.private_json(paths["state"] / "receipt.json")["phase"] == "complete"
        assert paths["desktop"].exists() and paths["command"].exists()
        assert "Focus is installed and ready to use" in capsys.readouterr().out
        if failure is not None:
            raise failure

    monkeypatch.setattr(m, "install_optional_pi", optional)
    assert m.install(args) == 0
    assert m.private_json(paths["state"] / "receipt.json")["phase"] == "complete"
    assert paths["desktop"].exists()
    assert not any("setup-pi" in call or "doctor" in call for call in calls)
    output = capsys.readouterr().out
    assert "Focus remains installed" in output
    assert "Incomplete at" not in output


def test_existing_pi_is_not_reinstalled(lifecycle, monkeypatch, capsys):
    paths, args, _, _ = lifecycle
    original = m.execute
    def existing(command, **kwargs):
        if "from focus.setup_pi import find_pi; print(find_pi())" in command:
            return subprocess.CompletedProcess(command, 0, "/synthetic/pi\n", "")
        return original(command, **kwargs)
    monkeypatch.setattr(m, "execute", existing)
    monkeypatch.setattr(m, "continue_pi_install", lambda: pytest.fail("Already installed Pi prompted"))
    assert m.install(args) == 0
    assert "Pi is already installed" in capsys.readouterr().out


def test_optional_pi_detection_failure_does_not_fail_focus(lifecycle, monkeypatch, capsys):
    paths, args, _, _ = lifecycle
    original = m.execute
    def cannot_detect(command, **kwargs):
        if "from focus.setup_pi import find_pi; print(find_pi())" in command:
            raise m.MaintenanceError("synthetic discovery failure")
        return original(command, **kwargs)
    monkeypatch.setattr(m, "execute", cannot_detect)
    assert m.install(args) == 0
    assert m.private_json(paths["state"] / "receipt.json")["phase"] == "complete"
    assert "Focus remains installed" in capsys.readouterr().out


def test_old_incomplete_pi_receipt_can_finish_without_pi(lifecycle, capsys):
    paths, args, calls, _ = lifecycle
    assert m.install(args) == 0
    receipt = m.private_json(paths["state"] / "receipt.json")
    receipt["phase"] = "pi"
    m.atomic_json(paths["state"] / "receipt.json", receipt)
    args.resume = True
    assert m.install(args) == 0
    assert m.private_json(paths["state"] / "receipt.json")["phase"] == "complete"
    assert "Pi installation skipped" in capsys.readouterr().out


def test_optional_pi_complete_download_runs_in_existing_terminal(monkeypatch, tmp_path):
    master, slave = os.openpty()
    downloaded = []
    original_open = open

    def download(command, **kwargs):
        assert "https://pi.dev/install.sh" in command
        script = Path(command[-1])
        script.write_text("#!/bin/sh\ntest -t 0 && test -t 1 && test -t 2\n")
        downloaded.append(script)

    def open_tty(path, *args, **kwargs):
        if path == "/dev/tty":
            return os.fdopen(os.dup(slave), "r+b", buffering=0)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(m, "execute", download)
    monkeypatch.setattr("builtins.open", open_tty)
    try:
        m.install_optional_pi({"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
        assert len(downloaded) == 1 and not downloaded[0].exists()
    finally:
        os.close(master)
        os.close(slave)


def test_optional_pi_download_failure_never_executes(monkeypatch):
    def failed_download(*args, **kwargs):
        raise m.MaintenanceError("synthetic download failure")
    monkeypatch.setattr(m, "execute", failed_download)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw: pytest.fail("Executed failed download"))
    with pytest.raises(m.MaintenanceError, match="download failure"):
        m.install_optional_pi({})


def test_readme_has_one_focus_uninstall_command():
    text = (ROOT / "README.md").read_text()
    section = text.split("**Uninstall Focus:**", 1)[1].split("**Uninstall Pi:**", 1)[0]
    assert section.count('"$HOME/.local/bin/focus-uninstall"') == 1
    assert "--dry-run" not in section


def test_partial_source_download_failure_is_uninstallable(lifecycle, monkeypatch):
    paths, args, calls, _ = lifecycle
    original = m.execute
    def interrupted(command, **kwargs):
        if command[:2] == ["git", "clone"]:
            raise m.MaintenanceError("Interrupted source download")
        return original(command, **kwargs)
    monkeypatch.setattr(m, "execute", interrupted)
    with pytest.raises(m.MaintenanceError, match="Interrupted"):
        m.install(args)
    assert not paths["source"].exists()
    assert paths["maintenance"].exists() and paths["uninstall_command"].exists()
    assert m.uninstall(argparse.Namespace(dry_run=False, purge=True, cleanup_packages=False, cleanup_pi=False)) == 0
    assert not paths["state"].exists()
