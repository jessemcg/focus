"""Exercise the real piped bootstrap with a local fake downloader and private tty."""
import errno
import os
import pty
import select
import signal
import subprocess
import sys
import time

import pytest

from test_source_installer import ROOT, m


def test_piped_bootstrap_latest_source_and_interactive_stdin(tmp_path):
    try:
        m.detect_platform()
    except m.MaintenanceError:
        pytest.skip("Host bootstrap platform unsupported")
    if os.getuid() == 0:
        pytest.skip("Bootstrap requires a normal desktop user")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "curl"
    fake.write_text(f'''#!{sys.executable}
import sys
from pathlib import Path
args = sys.argv[1:]
if '-o' not in args:
    assert args == ['-fsSL', 'https://raw.githubusercontent.com/jessemcg/focus/main/scripts/install-bootstrap.sh']
    sys.stdout.write(Path({str(ROOT / 'scripts/install-bootstrap.sh')!r}).read_text())
else:
    assert 'https://raw.githubusercontent.com/jessemcg/focus/main/install.sh' in args
    Path(args[args.index('-o') + 1]).write_text('test -t 0 || exit 81\\n[ "$FOCUS_INSTALL_REF" = main ] || exit 82\\n[ "$1" = --source-dir ] || exit 83\\n[ "$2" = "synthetic source" ] || exit 84\\nprintf "SYNTHETIC_INSTALL_OK\\\\n"\\n')
''')
    fake.chmod(0o755)
    command = subprocess.check_output([sys.executable, str(ROOT / "scripts/print-install-command.py")], text=True).strip()
    pid, fd = pty.fork()
    if pid == 0:
        os.execve("/bin/bash", ["bash", "-c", command + ' -s -- --source-dir "synthetic source"'],
                  dict(os.environ, PATH=str(bindir) + ":/usr/bin:/bin"))
    output = b""
    status = None
    ended = 0
    try:
        deadline = time.monotonic() + 15
        sent_inspect = sent_approve = False
        while time.monotonic() < deadline:
            if select.select([fd], [], [], 0.1)[0]:
                try:
                    chunk = os.read(fd, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
                if not chunk:
                    break
                output += chunk
                if b"Inspect before execution?" in output and not sent_inspect:
                    os.write(fd, b"n\n")
                    sent_inspect = True
                if b"Type yes:" in output and not sent_approve:
                    os.write(fd, b"yes\n")
                    sent_approve = True
            ended, status = os.waitpid(pid, os.WNOHANG)
            if ended:
                break
        else:
            pytest.fail("Piped bootstrap hung: " + output.decode(errors="replace"))
        if status is None or not ended:
            _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0, output.decode(errors="replace")
        assert b"SYNTHETIC_INSTALL_OK" in output
    finally:
        os.close(fd)
        try:
            if os.waitpid(pid, os.WNOHANG)[0] == 0:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
        except (ChildProcessError, ProcessLookupError):
            pass
