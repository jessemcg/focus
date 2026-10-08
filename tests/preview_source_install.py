"""Actual GUI acceptance using editable source, synthetic XDG and no providers.

Run explicitly with the verified environment's Python. Never starts a model or
provisions dependencies. Close only this preview (or it exits after five minutes).
"""
import os
from pathlib import Path
import socket
import tempfile

root = Path(tempfile.mkdtemp(prefix="focus-source-preview-"))
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
    path = root / key.lower(); path.mkdir(mode=0o700)
    os.environ[key] = str(path)
os.environ.update(FOCUS_CONFIG_DIR=str(root / "xdg_config_home/focus"),
                  PI_CODING_AGENT_DIR=str(root / "synthetic-pi"),
                  PI_RUN_METRICS_ENABLED="0", GSETTINGS_BACKEND="memory")
# Internet connections are forbidden; Unix desktop IPC remains available.
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Preview network disabled"))
from focus import core
from focus import app

app.APPLICATION_ID = f"com.mcglaw.Focus.SourcePreview.p{os.getpid()}"
bundle = root / "synthetic-record"; (bundle / "text_pages").mkdir(parents=True)
(bundle / "text_pages/0001.txt").write_text("Synthetic source-install acceptance. Ada was the clerk.\n")
(bundle / "case_name.txt").write_text("Synthetic Source Installation")
application = app.Focus(input_override=bundle)


def ready():
    application.get_active_window().set_title(core.APPLICATION_NAME + " — Source Installer Acceptance")
    print(f"READY pid={os.getpid()} root={root} config={core.CONFIG_FILE} source={core.PROJECT_DIR}", flush=True)
    return False


application.connect("activate", lambda _: core.GLib.timeout_add(600, ready))
core.GLib.timeout_add_seconds(300, lambda: application.quit())
raise SystemExit(application.run([]))
