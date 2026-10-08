"""Disposable stdlib maintenance contracts; native/auth operations are mocked."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("focus_maintenance", ROOT / "scripts/focus_maintenance.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.mark.parametrize("release,family", [
    ({"ID": "ubuntu", "VERSION_ID": "24.04"}, "apt"),
    ({"ID": "ubuntu", "VERSION_ID": "26.04"}, "apt"),
    ({"ID": "linuxmint", "ID_LIKE": "ubuntu debian", "VERSION_ID": "22", "UBUNTU_CODENAME": "noble"}, "apt"),
    ({"ID": "fedora", "VERSION_ID": "43"}, "dnf"),
    ({"ID": "fedora", "VERSION_ID": "44"}, "dnf"),
    ({"ID": "derivative", "ID_LIKE": "fedora", "FEDORA_VERSION_ID": "44"}, "dnf"),
])
@pytest.mark.parametrize("arch", ["x86_64", "aarch64"])
def test_platform_baselines(release, family, arch):
    assert m.detect_platform(release, arch, False) == family


@pytest.mark.parametrize("release,arch,immutable", [
    ({"ID": "ubuntu", "VERSION_ID": "22.04"}, "x86_64", False),
    ({"ID": "fedora", "VERSION_ID": "42"}, "x86_64", False),
    ({"ID": "debian", "VERSION_ID": "13"}, "x86_64", False),
    ({"ID": "fedora", "VERSION_ID": "44"}, "armv7l", False),
    ({"ID": "fedora", "VERSION_ID": "44"}, "x86_64", True),
    ({"ID": "bazzite", "ID_LIKE": "fedora", "VERSION_ID": "44"}, "x86_64", False),
    ({"ID": "fedora", "VARIANT_ID": "silverblue", "VERSION_ID": "44"}, "x86_64", False),
    ({"ID": "ubuntu", "VERSION_ID": "22.04", "UBUNTU_CODENAME": "noble"}, "x86_64", False),
])
def test_platform_rejections(release, arch, immutable):
    with pytest.raises(m.MaintenanceError):
        m.detect_platform(release, arch, immutable)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    old_umask = os.umask(0o077)
    home = tmp_path / "home with spaces"; home.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(home))
    for key in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "FOCUS_BOOTSTRAP_PACKAGES", "PI_CODING_AGENT_DIR"):
        monkeypatch.delenv(key, raising=False)
    paths = m.layout(home / "Focus source")
    data = {"schema": 1, "installation_id": "a" * 32, "phase": "preflight", "paths": {k: str(p) for k, p in paths.items()},
            "created": [], "files": {}, "tool_versions": {}, "introduced_packages": [], "package_family": "apt",
            "config_created": False}
    try:
        yield paths, data
    finally:
        os.umask(old_umask)


def test_redirected_and_nested_roots_refused(sandbox, monkeypatch):
    paths, _ = sandbox
    outside = paths["source"].parent / "other"; outside.mkdir()
    link = paths["source"].parent / "link"; link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(m.MaintenanceError, match="Symlink"):
        m.layout(link / "source")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp")
    with pytest.raises(m.MaintenanceError, match="HOME"):
        m.layout(paths["source"])
    monkeypatch.delenv("XDG_DATA_HOME")
    with pytest.raises(m.MaintenanceError, match="contains|Nested"):
        m.layout(paths["source"].parent / ".local")


def test_receipt_version_paths_hashes_and_permissions(sandbox):
    paths, data = sandbox
    m.validate_receipt(data, paths)
    receipt = paths["state"] / "receipt.json"
    m.atomic_json(receipt, data)
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert m.private_json(receipt) == data
    receipt.chmod(0o644)
    with pytest.raises(m.MaintenanceError, match="Nonprivate"):
        m.private_json(receipt)
    for key, value in (("schema", 2), ("installation_id", "../../etc"), ("created", ["alien"]), ("files", {"command": "oops"})):
        corrupt = dict(data); corrupt[key] = value
        with pytest.raises(m.MaintenanceError):
            m.validate_receipt(corrupt, paths)
    corrupt = json.loads(json.dumps(data)); corrupt["paths"]["environment"] = "/tmp/foreign"
    with pytest.raises(m.MaintenanceError):
        m.validate_receipt(corrupt, paths)


def test_shared_cleanup_flags_require_purge(capsys):
    assert m.main(["uninstall", "--cleanup-packages"]) == 1
    assert "requires --purge" in capsys.readouterr().out


def test_purge_dry_run_reports_changes_without_consent(sandbox, monkeypatch, capsys):
    paths, data = sandbox
    paths["source"].mkdir(); m.marker(paths["source"], data["installation_id"], paths["source"])
    data["created"].append("source")
    m.atomic_json(paths["state"] / "receipt.json", data)
    monkeypatch.setattr(m, "active_processes", lambda *a: [])
    monkeypatch.setattr(m, "source_changes", lambda *a: "SYNTHETIC local branch and ignored edits")
    monkeypatch.setattr(m, "approve", lambda *a: pytest.fail("Dry-run requested consent"))
    args = argparse.Namespace(dry_run=True, purge=True, cleanup_packages=False, cleanup_pi=False)
    assert m.uninstall(args) == 0
    assert "SYNTHETIC local branch and ignored edits" in capsys.readouterr().out
    assert paths["source"].is_dir()


def test_concurrent_maintenance_lock(sandbox):
    paths, _ = sandbox
    with m.lock(paths["state"]):
        with pytest.raises(m.MaintenanceError, match="Another"):
            with m.lock(paths["state"]):
                pass


@pytest.mark.parametrize("key", ["command", "uninstall_command", "desktop", "svg", "symbolic", "png"])
def test_foreign_files_and_modified_owned_files(sandbox, key):
    paths, data = sandbox
    target = paths[key]; target.parent.mkdir(parents=True); target.write_text("foreign")
    with pytest.raises(m.MaintenanceError, match="Collision"):
        m.owned_file(key, target, b"new", data, lambda: None)
    target.unlink()
    m.owned_file(key, target, b"owned", data, lambda: None)
    m.owned_file(key, target, b"updated", data, lambda: None)
    target.write_text("edited")
    with pytest.raises(m.MaintenanceError):
        m.owned_file(key, target, b"again", data, lambda: None)


def test_environment_association_and_fingerprint(sandbox):
    paths, data = sandbox
    paths["source"].mkdir(); (paths["source"] / "pyproject.toml").write_text("project")
    (paths["source"] / "uv.lock").write_text("locked")
    paths["environment"].mkdir(parents=True)
    m.marker(paths["environment"], data["installation_id"], paths["source"])
    m.atomic_json(paths["environment"] / "focus-env.json", {"fingerprint": "outdated"})
    with pytest.raises(m.MaintenanceError, match="Dependencies changed"):
        m.verify_environment(paths)
    m.marker(paths["environment"], data["installation_id"], paths["source"] / "alien")
    with pytest.raises(m.MaintenanceError, match="another checkout"):
        m.verify_environment(paths)


def test_clear_inherited_runtime_selections(sandbox, monkeypatch):
    paths, _ = sandbox
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/wrong")
    monkeypatch.setenv("UV_PYTHON", "3.12")
    monkeypatch.setenv("VIRTUAL_ENV", "/wrong")
    monkeypatch.setenv("PYTHONPATH", "/wrong")
    env = m.python_environment(paths)
    assert env["UV_PROJECT_ENVIRONMENT"] == str(paths["environment"])
    assert all(key not in env for key in ("UV_PYTHON", "VIRTUAL_ENV", "PYTHONPATH"))
    assert env["UV_PYTHON_INSTALL_DIR"] == str(paths["python"])


def test_locked_sync_no_dev_by_default(sandbox, monkeypatch):
    paths, data = sandbox
    paths["source"].mkdir(); (paths["source"] / "pyproject.toml").write_text("project")
    (paths["source"] / "uv.lock").write_text("locked")
    commands = []
    monkeypatch.setattr(m, "locate_uv", lambda *args: "/uv")
    monkeypatch.setattr(m, "execute", lambda command, **kw: commands.append((command, kw)))
    monkeypatch.setattr(m, "verify_environment", lambda *args: {})
    m.synchronize(paths, data, lambda: None)
    sync = next(command for command, _ in commands if "sync" in command)
    assert "--locked" in sync and "--no-default-groups" in sync and "--group" not in sync
    assert not (paths["source"] / ".venv").exists()
    commands.clear(); m.synchronize(paths, data, lambda: None, dev=True)
    assert next(c for c, _ in commands if "sync" in c)[-2:] == ["--group", "dev"]


def test_native_fedora_cairo_headers():
    # cairo-devel alone lacks cairo-gobject.h on the clean Fedora image.
    assert {"cairo-devel", "cairo-gobject-devel"}.issubset(m.PACKAGES["dnf"])


def test_package_availability_and_transaction_safety(monkeypatch):
    packages = m.Packages("apt")
    def command(argv, **kwargs):
        output = "Candidate: 1.0\n" if argv[0] == "apt-cache" else "Remv desktop-important [1.0]\n"
        return subprocess.CompletedProcess(argv, 0, output, "")
    monkeypatch.setattr(m, "execute", command)
    with pytest.raises(m.MaintenanceError, match="removes"):
        packages.preview(["git"])
    with pytest.raises(m.MaintenanceError, match="unrelated"):
        packages.preview(["git"], remove=True)
    monkeypatch.setattr(m, "execute", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "Candidate: (none)", ""))
    with pytest.raises(m.MaintenanceError, match="Official repositories"):
        packages.preview(["git"])


def test_sudo_cancellation_no_silent_approval(monkeypatch):
    packages = m.Packages("apt")
    monkeypatch.setattr(packages, "preview", lambda *a: "")
    def canceled(*args, **kwargs):
        raise m.MaintenanceError("Canceled")
    monkeypatch.setattr(m, "approve", canceled)
    with pytest.raises(m.MaintenanceError, match="Canceled"):
        packages.install(["git"])


def test_document_layouts_never_purged(sandbox):
    paths, _ = sandbox
    root = paths["source"]; (root / "text_pages").mkdir(parents=True)
    document = root / "text_pages/0001.txt"; document.write_text("SYNTHETIC")
    with pytest.raises(m.MaintenanceError, match="never purge"):
        m.remove_tree(root)
    assert document.read_text() == "SYNTHETIC"


def test_normal_uninstall_and_purge_retains_external_documents(sandbox, monkeypatch):
    paths, data = sandbox
    paths["source"].mkdir(); m.marker(paths["source"], data["installation_id"], paths["source"])
    paths["config"].mkdir(parents=True); (paths["config"] / "config.json").write_text("{}")
    for name in ("environment", "python", "tools", "cache", "maintenance"):
        paths[name].mkdir(parents=True); m.marker(paths[name], data["installation_id"], paths["source"])
        data["created"].append(name)
    data["created"].append("source")
    external = paths["source"].parent / "case"; (external / "text_pages").mkdir(parents=True)
    (external / "text_pages/0001.txt").write_text("Synthetic external document")
    credentials = paths["source"].parent / ".pi/agent/auth.json"; credentials.parent.mkdir(parents=True); credentials.write_text("fake credentials")
    for key in ("command", "uninstall_command", "desktop", "svg", "symbolic", "png"):
        m.owned_file(key, paths[key], b"owned", data, lambda: None)
    m.owned_file("engine", paths["maintenance"] / "focus_maintenance.py", b"engine", data, lambda: None)
    m.atomic_json(paths["state"] / "receipt.json", data)
    monkeypatch.setattr(m, "approve", lambda *args: None)
    monkeypatch.setattr(m, "refresh_caches", lambda *args: None)
    monkeypatch.setattr(m, "active_processes", lambda *args: [])
    args = argparse.Namespace(dry_run=True, purge=False, cleanup_packages=False, cleanup_pi=False)
    assert m.uninstall(args) == 0 and paths["command"].exists()
    args.dry_run = False
    assert m.uninstall(args) == 0
    assert paths["source"].exists() and paths["config"].exists() and paths["maintenance"].exists()
    assert not paths["command"].exists() and not paths["environment"].exists()
    monkeypatch.setattr(m, "source_changes", lambda *args: ["local unpushed commits", "modified source"])
    args.purge = True
    assert m.uninstall(args) == 0
    assert not paths["source"].exists() and not paths["state"].exists()
    assert paths["config"].exists()  # pre-existing is not owned
    assert credentials.read_text() == "fake credentials"
    assert (external / "text_pages/0001.txt").exists()


def test_active_focus_blocks_uninstall(sandbox, monkeypatch):
    paths, data = sandbox
    m.atomic_json(paths["state"] / "receipt.json", data)
    monkeypatch.setattr(m, "active_processes", lambda *args: [123])
    with pytest.raises(m.MaintenanceError, match="Close Focus"):
        m.uninstall(argparse.Namespace(dry_run=True, purge=False))


def test_no_provision_on_run(sandbox, monkeypatch):
    paths, data = sandbox
    m.atomic_json(paths["state"] / "receipt.json", data)
    paths["source"].mkdir(); binary = paths["environment"] / "bin/focus"
    binary.parent.mkdir(parents=True); binary.write_text("entry")
    monkeypatch.setattr(m, "verify_environment", lambda *a: {})
    monkeypatch.setattr(m, "synchronize", lambda *a, **k: pytest.fail("run provisioned"))
    def executed(executable, argv, env):
        assert executable == binary and argv[-1] == "path with spaces"
        assert env["UV_OFFLINE"] == "1" and env["UV_PYTHON_DOWNLOADS"] == "never"
        raise SystemExit(0)
    monkeypatch.setattr(m.os, "execve", executed)
    old_cwd = Path.cwd()
    try:
        with pytest.raises(SystemExit):
            m.run_environment(argparse.Namespace(operation="run", project=str(paths["source"]), arguments=["focus", "path with spaces"]))
    finally:
        os.chdir(old_cwd)


def test_installer_publication_gate_and_no_root(sandbox, monkeypatch):
    paths, _ = sandbox
    monkeypatch.setattr(m, "detect_platform", lambda: "apt")
    monkeypatch.setattr(m, "approve", lambda *args: None)
    monkeypatch.setattr(m.os, "getuid", lambda: 0)
    with pytest.raises(m.MaintenanceError, match="not root"):
        m.install(argparse.Namespace(source_dir=str(paths["source"])))


def test_desktop_templates_render_paths_with_spaces(sandbox):
    paths, data = sandbox
    paths["source"].mkdir()
    (paths["source"] / "scripts").mkdir()
    import shutil
    shutil.copytree(ROOT / "scripts/desktop", paths["source"] / "scripts/desktop")
    for name in ("focus.svg", "focus-symbolic.svg", "focus.png"):
        shutil.copyfile(ROOT / name, paths["source"] / name)
    # Cache refresh is not run against the user's desktop.
    original = m.refresh_caches
    try:
        m.refresh_caches = lambda *a: None
        m.integration(paths, data, lambda: None)
    finally:
        m.refresh_caches = original
    launcher = paths["command"].read_text()
    assert "refresh-current-case" not in launcher and "PI_RUN_METRICS_ENABLED=0" in launcher
    subprocess.run(["sh", "-n", str(paths["command"])], check=True)
    assert f"Icon={paths['svg']}" in paths["desktop"].read_text()
