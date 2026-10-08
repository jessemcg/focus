"""Install/fail/resume/repair/remove in a disposable Git source and HOME.

Only git and desktop-file-validate execute natively; package/auth/uv are fixtures.
"""
import argparse
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
        if "setup-pi" in command and failing[0]:
            raise m.MaintenanceError("synthetic provider rejected verification")
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
    original = m.execute
    def introduces_pi(command, **kwargs):
        if "setup-pi" in command:
            agent.mkdir(parents=True, exist_ok=True)
        return original(command, **kwargs)
    monkeypatch.setattr(m, "execute", introduces_pi)
    assert m.install(args) == 0
    assert str(agent) in m.private_json(paths["state"] / "receipt.json")["introduced_pi_resources"]
    args.repair = True
    assert m.install(args) == 0
    assert str(agent) in m.private_json(paths["state"] / "receipt.json")["introduced_pi_resources"]


def test_failed_verification_incomplete_resumable_no_reader_success(lifecycle):
    paths, args, calls, failing = lifecycle
    failing[0] = True
    with pytest.raises(m.MaintenanceError, match="rejected verification"):
        m.install(args)
    receipt = m.private_json(paths["state"] / "receipt.json")
    assert receipt["phase"] == "pi"
    assert not paths["desktop"].exists()
    assert paths["uninstall_command"].exists() and paths["maintenance"].exists()
    failing[0] = False; args.resume = True
    assert m.install(args) == 0
    assert m.private_json(paths["state"] / "receipt.json")["phase"] == "complete"


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
