"""Real terminal regression tests; no packages, credentials or model calls."""
import os
from pathlib import Path
import select
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOAD = f"""
import runpy
import sys
sys.path.insert(0, {str(ROOT)!r})
maintenance = runpy.run_path({str(ROOT / 'scripts/focus_maintenance.py')!r})
from focus.setup_pi import ask
"""


@pytest.mark.parametrize("action,answer,success", [
    ("maintenance['approve']('TEST_PROMPT')", "yes", True),
    ("maintenance['approve']('TEST_PROMPT')", "no", False),
    ("maintenance['approve']('TEST_PROMPT')", "", False),
    ("assert ask('TEST_PROMPT') == 'chosen model'", "chosen model", True),
    ("maintenance['approve']('TEST_PROMPT', 'exact path')", "exact path", True),
    ("maintenance['approve']('TEST_PROMPT', '')", "", True),
    ("maintenance['approve']('TEST_PROMPT', '')", "no", False),
    ("maintenance['approve']('TEST_PROMPT', '')", None, False),
])
def test_prompt_uses_controlling_terminal_not_stdin(action, answer, success):
    master, slave = os.openpty()
    # A fresh session acquires only our disposable terminal. stdin remains a pipe.
    code = f"""
import fcntl, os, termios
fd = os.open({os.ttyname(slave)!r}, os.O_RDWR)
fcntl.ioctl(fd, termios.TIOCSCTTY, 0)
{LOAD}
{action}
print('PROMPT_OK', flush=True)
"""
    process = subprocess.Popen([sys.executable, "-c", code], start_new_session=True,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    try:
        output = b""
        deadline = time.monotonic() + 10
        while b"TEST_PROMPT" not in output and time.monotonic() < deadline:
            if process.poll() is not None:
                break
            if select.select([master], [], [], 0.1)[0]:
                output += os.read(master, 65536)
        if b"TEST_PROMPT" not in output:
            process.kill()
            _, errors = process.communicate(timeout=5)
            pytest.fail(f"No terminal prompt: {output!r} {errors!r}")
        if action == "maintenance['approve']('TEST_PROMPT', '')":
            assert b"Press Enter to continue" in output
        os.write(master, b"\x04" if answer is None else (answer + "\n").encode())
        stdout, stderr = process.communicate(timeout=5)
        assert (process.returncode == 0) == success, stderr.decode()
        assert (b"PROMPT_OK" in stdout) == success
        assert b"No controlling terminal" not in stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
        os.close(slave)


@pytest.mark.parametrize("action", [
    "maintenance['approve']('TEST_PROMPT')", "ask('TEST_PROMPT')",
])
def test_missing_terminal_still_requires_approval(action):
    result = subprocess.run([sys.executable, "-c", LOAD + action],
                            input="yes\n", capture_output=True, text=True,
                            start_new_session=True, timeout=10)
    assert result.returncode != 0
    assert "controlling terminal" in result.stderr
