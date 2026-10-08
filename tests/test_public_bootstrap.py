import os
from pathlib import Path
import subprocess

from test_source_installer import ROOT


def command_fixture(tmp_path, ref):
    import json
    import shutil
    scripts = tmp_path / "scripts"; scripts.mkdir()
    for name in ("print-install-command.py", "download-bootstrap.sh.in"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    (scripts / "install-release.json").write_text(json.dumps({"source_ref": ref}))
    return scripts


def test_unpublished_command_is_not_advertised(tmp_path):
    scripts = command_fixture(tmp_path, None)
    result = subprocess.run(["python3", str(scripts / "print-install-command.py")], capture_output=True, text=True)
    assert result.returncode != 0
    assert "no executable one-liner" in result.stderr
    assert "bash -c" not in result.stdout


def test_pinned_one_liner_round_trips_to_reviewed_script(tmp_path):
    scripts = command_fixture(tmp_path, "a" * 40)
    command = subprocess.check_output(["python3", str(scripts / "print-install-command.py")], text=True).strip()
    expanded = subprocess.check_output(["python3", str(scripts / "print-install-command.py"), "--expanded"], text=True)
    assert len(command.splitlines()) == 1
    # Decode the outer shell quoting without executing the bootstrap or fetching.
    decoded = subprocess.check_output(["/bin/bash", "-c", 'bash() { printf "%s" "$2"; }; ' + command], text=True)
    assert decoded == expanded
    subprocess.run(["/bin/bash", "-n"], input=expanded, text=True, check=True)


def test_interrupted_download_never_executes_partial_script(tmp_path):
    from test_source_installer import m
    try:
        m.detect_platform()
    except m.MaintenanceError:
        import pytest
        pytest.skip("Native bootstrap rejection is tested in distribution fixtures")
    sentinel = tmp_path / "NEVER_EXECUTED"
    bindir = tmp_path / "bin"; bindir.mkdir()
    curl = bindir / "curl"
    curl.write_text(f'''#!/bin/sh
while [ "$#" -gt 0 ]; do
 if [ "$1" = -o ]; then shift; target=$1; fi
 shift
done
printf '#!/bin/sh\\ntouch "{sentinel}"\\n' > "$target"
exit 7
''')
    curl.chmod(0o755)
    script = tmp_path / "bootstrap.sh"
    script.write_text((ROOT / "scripts/download-bootstrap.sh.in").read_text().replace("@REF@", "a" * 40))
    env = dict(os.environ, PATH=str(bindir) + ":/usr/bin:/bin")
    result = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 7
    assert not sentinel.exists()


def test_source_lockfile_is_not_ignored_and_has_editable_contract():
    import tomllib
    assert "/uv.lock" not in (ROOT / ".gitignore").read_text()
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    focus = next(item for item in lock["package"] if item["name"] == "focus")
    assert focus["source"] == {"editable": "."}
    assert next(item for item in lock["package"] if item["name"] == "pygobject")["version"] == "3.54.5"


def test_normal_coding_discovery_does_not_load_embedded_resources(tmp_path):
    import shutil
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("Installed Pi SDK required")
    env = {key: os.environ[key] for key in ("PATH", "PI_METRICS_TEST_SDK") if key in os.environ}
    env.update(HOME=str(tmp_path), PI_OFFLINE="1")
    result = subprocess.run([node, str(ROOT / "tests/coding_resource_discovery.mjs"), str(ROOT), str(tmp_path / "agent")],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
