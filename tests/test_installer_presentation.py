"""Terminal presentation never changes installation or approval behavior."""
import io
import os
import select
import subprocess
import sys

import pytest

from test_source_installer import ROOT, m


class Terminal(io.StringIO):
    encoding = "utf-8"

    def isatty(self):
        return True


@pytest.fixture
def terminal(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    return Terminal()


def test_status_styles_and_real_stage_progress(terminal):
    assert "✓" in m.status_text("OK", "Ready", terminal)
    assert "✗" in m.status_text("FAIL", "Stopped", terminal)
    first = m.status_text("CHECK", "1/8 Platform", terminal)
    assert "0/8 stages passed" in first
    assert "[────────]" in first
    grouped = m.status_text("CHECK", "5/8 Python; 6/8 dependencies", terminal)
    assert "4/8 stages passed" in grouped
    last = m.status_text("CHECK", "8/8 Final checks", terminal)
    assert "7/8 stages passed" in last
    done = m.status_text("OK", m.INSTALL_SUCCESS, terminal)
    assert "8/8 stages passed" in done
    assert "[━━━━━━━━]" in done
    assert "stages passed" not in m.status_text("FAIL", "Incomplete", terminal)
    assert "stages passed" not in m.status_text("OK", "Dry-run only", terminal)


@pytest.mark.parametrize("mode", ["redirected", "no-color", "dumb"])
def test_plain_output_is_unchanged(terminal, monkeypatch, mode):
    stream = terminal
    if mode == "redirected":
        stream = io.StringIO()
    elif mode == "no-color":
        monkeypatch.setenv("NO_COLOR", "")
    else:
        monkeypatch.setenv("TERM", "dumb")
    for kind in ("CHECK", "OK", "ACTION", "WAIT", "WARN", "FAIL"):
        assert m.status_text(kind, "1/8 Message", stream) == f"[{kind}] 1/8 Message"
    monkeypatch.setattr(m.sys, "stdout", stream)
    m.welcome()
    assert stream.getvalue() == ""


def test_ascii_terminal_has_safe_symbols(terminal):
    terminal.encoding = "ascii"
    text = m.status_text("CHECK", "3/8 Dependencies", terminal)
    text.encode("ascii")
    assert "[##------]" in text


def test_actual_terminal_output(terminal):
    master, slave = os.openpty()
    code = f"""
import runpy
m = runpy.run_path({str(ROOT / 'scripts/focus_maintenance.py')!r})
m['welcome']()
m['say']('CHECK', '1/8 Platform')
m['say']('OK', 'Native packages ready')
m['say']('WARN', 'Approval required')
m['say']('CHECK', '8/8 Final checks')
m['say']('OK', m['INSTALL_SUCCESS'])
"""
    try:
        result = subprocess.run([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                                stdout=slave, stderr=subprocess.PIPE, timeout=10,
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        assert result.returncode == 0, result.stderr.decode()
        output = b""
        while select.select([master], [], [], 0.2)[0]:
            output += os.read(master, 65536)
        text = output.decode()
        assert "Let's get you set up." in text
        assert "\033[1;32m✓ OK\033[0m" in text
        assert "8/8 stages passed" in text
        assert "\033[2J" not in text  # never clear output/history
    finally:
        os.close(master)
        os.close(slave)
