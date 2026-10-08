"""Only synthetic local downloads execute; no installer/package/auth operations."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_public_bootstrap import command_fixture


@pytest.mark.parametrize("downloader", ["curl", "wget"])
@pytest.mark.parametrize("download_status,child_status", [(7, 0), (0, 0), (0, 17)])
def test_short_loader_complete_download_status_args_and_cleanup(tmp_path, downloader, download_status, child_status):
    scripts = command_fixture(tmp_path, "a" * 40)
    command = subprocess.check_output([sys.executable, str(scripts / "print-install-command.py"),
                                       "--downloader", downloader], text=True).strip()
    assert len(command) < 350 and len(command.splitlines()) == 1
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    # Spaces, quotes and shell metacharacters must remain path data in the trap.
    temporary = tmp_path / "temporary space '$literal\""; temporary.mkdir()
    downloaded = tmp_path / "download.json"
    executed = tmp_path / "executed.txt"
    fake = bin_dir / downloader
    fake.write_text(f'''#!{sys.executable}
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
path=Path(args[args.index({"-o" if downloader == "curl" else "-O"!r})+1])
Path(os.environ['DOWNLOAD_RECORD']).write_text(json.dumps({{'path':str(path),'mode':path.stat().st_mode & 0o777,'args':args}}))
path.write_text('printf "%s\\\\n" "$@" > "$EXECUTION_RECORD"\\nexit {child_status}\\n')
sys.exit({download_status})
''')
    fake.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_dir) + ":/usr/bin:/bin", TMPDIR=str(temporary),
               DOWNLOAD_RECORD=str(downloaded), EXECUTION_RECORD=str(executed))
    result = subprocess.run(["/bin/bash", "-c", command + ' --source-dir "synthetic source"'],
                            env=env, text=True, capture_output=True)
    assert result.returncode == (download_status or child_status)
    record = json.loads(downloaded.read_text())
    assert record["mode"] == 0o600
    assert not Path(record["path"]).exists()
    assert not list(temporary.iterdir())
    assert any("/" + "b" * 40 + "/scripts/install-bootstrap.sh" in arg for arg in record["args"])
    if download_status:
        assert not executed.exists()  # never execute a partial/failed download
    else:
        assert executed.read_text().splitlines() == ["--source-dir", "synthetic source"]


def test_short_loader_rejects_unpinned_bootstrap(tmp_path):
    scripts = command_fixture(tmp_path, "a" * 40)
    (scripts / "install-release.json").write_text(json.dumps({"source_ref": "a" * 40}))
    result = subprocess.run([sys.executable, str(scripts / "print-install-command.py")],
                            text=True, capture_output=True)
    assert result.returncode != 0 and not result.stdout
    assert "Unpublished bootstrap" in result.stderr


def test_short_loader_stops_if_temporary_file_creation_fails(tmp_path):
    scripts = command_fixture(tmp_path, "a" * 40)
    command = subprocess.check_output([sys.executable, str(scripts / "print-install-command.py")], text=True).strip()
    bin_dir = tmp_path / "bin"; bin_dir.mkdir()
    (bin_dir / "mktemp").write_text("#!/bin/sh\nexit 9\n")
    (bin_dir / "mktemp").chmod(0o755)
    (bin_dir / "curl").write_text("#!/bin/sh\necho SHOULD_NOT_RUN\nexit 0\n")
    (bin_dir / "curl").chmod(0o755)
    result = subprocess.run(["/bin/bash", "-c", command],
                            env=dict(os.environ, PATH=str(bin_dir) + ":/usr/bin:/bin"),
                            text=True, capture_output=True)
    assert result.returncode == 9 and "SHOULD_NOT_RUN" not in result.stdout
