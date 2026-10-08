"""Explicit Pi onboarding. No credentials are read, printed, or stored by Focus."""
from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .paths import AGENT_RESOURCES, PROJECT_DIR, config_file, pi_settings_file, verification_file
from .pi_runtime import (PiModel, PiRuntimeError, available_pi_models,
                         save_project_pi_runtime)

BASELINE = (1, 1, 0)
REQUIRED_FLAGS = ("--offline", "--no-session", "--no-extensions", "--no-context-files",
                  "--system-prompt", "--skill", "--tools", "--approve", "--mode")


def desktop_environment(executable: str = "") -> dict[str, str]:
    """Reproduce the public launcher, not terminal-only keys or shell startup."""
    keys = ("HOME", "USER", "LOGNAME", "LANG", "TERM", "DISPLAY", "WAYLAND_DISPLAY",
            "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
            "XDG_STATE_HOME", "XDG_CACHE_HOME", "PI_CODING_AGENT_DIR", "FOCUS_CONFIG_DIR")
    env = {key: os.environ[key] for key in keys if key in os.environ}
    data = Path(env.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    paths = [str(Path(executable).parent)] if executable else []
    paths += [str(data / "pi-node/current/bin"), "/usr/local/bin", "/usr/bin", "/bin"]
    env.update(PATH=os.pathsep.join(paths), PI_RUN_METRICS_ENABLED="0", PI_OFFLINE="1")
    return env


def probe(command: list[str], env: dict[str, str], timeout: int = 15) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory(prefix="focus-pi-neutral-") as cwd:
        return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                              timeout=timeout, check=False)


def find_pi() -> str:
    agent = Path(os.environ.get("PI_CODING_AGENT_DIR", str(Path.home() / ".pi/agent")))
    candidates = [shutil.which("pi"), str(agent / "bin/pi"), str(Path.home() / ".local/bin/pi")]
    try:
        configured = json.loads(config_file().read_text()).get("pi_agent_command", "")
        argv = shlex.split(configured)
        if len(argv) == 1:
            candidates.insert(0, argv[0])
    except (OSError, ValueError):
        pass
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).absolute())
    return ""


def compatibility(executable: str) -> dict:
    if not executable:
        return {"ok": False, "error": "Pi missing; run focus setup-pi"}
    env = desktop_environment(executable)
    try:
        version = probe([executable, "--version"], env).stdout.strip()
        numbers = tuple(int(n) for n in re.findall(r"\d+", version)[:3])
        help_result = probe([executable, "--offline", "--no-extensions", "--no-context-files", "--help"], env)
        missing = [flag for flag in REQUIRED_FLAGS if flag not in help_result.stdout]
        # Managed launchers select their own Node; execute Node using the same store.
        node = shutil.which("node", path=env["PATH"])
        node_version = probe([node, "--version"], env).stdout.strip() if node else ""
        node_numbers = tuple(int(n) for n in re.findall(r"\d+", node_version)[:3])
        ok = numbers >= BASELINE and not missing and node_numbers >= (22, 19, 0)
        return {"ok": ok, "version": version, "node": node_version,
                "executable": executable, "missing_interfaces": missing}
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "error": "Pi/Node failed a bounded desktop-environment probe"}


def ask(message: str) -> str:
    try:
        with open("/dev/tty", "r+") as tty:
            tty.write(message + " "); tty.flush()
            answer = tty.readline()
            if not answer:
                raise PiRuntimeError("Onboarding canceled")
            return answer.strip()
    except OSError as exc:
        raise PiRuntimeError("A controlling terminal is required for this decision") from exc


def consent(message: str) -> None:
    if ask(message + " [y/N]").lower() not in {"y", "yes"}:
        raise PiRuntimeError("Declined; installation remains incomplete")


def install_pi() -> None:
    consent("[ACTION] Download and run https://pi.dev/install.sh? Its own prompts authorize Pi/Node changes; do not replace an existing Pi")
    with tempfile.TemporaryDirectory(prefix="focus-pi-installer-") as cwd:
        script = Path(cwd) / "install.sh"
        subprocess.run(["curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2",
                        "https://pi.dev/install.sh", "--output", str(script)], check=True)
        # Authentication remains attached to the terminal and is never captured.
        with open("/dev/tty", "r+") as tty:
            subprocess.run(["sh", str(script)], cwd=cwd, stdin=tty, stdout=tty, stderr=tty, check=True)


def credential_ready(executable: str, model: PiModel) -> bool:
    result = probe([executable, "auth", "check", "--provider", model.provider,
                    "--model", model.model_id, "--no-refresh", "--json"], desktop_environment(executable))
    return result.returncode == 0  # Never request --credentials or print auth output.


def discover(executable: str) -> list[PiModel]:
    # Discovery uses its own neutral directory and a deliberately desktop-style env.
    return available_pi_models([executable], environment=desktop_environment(executable))


def verify(executable: str, model: PiModel, thinking: str, timeout: int = 90) -> None:
    """One synthetic Agent run, same real extensions and artifact parser as GUI."""
    from .agent_answer import create_focus_run_id, read_focus_answer_artifact
    from .agent_followup import FollowUpEndpoint, FollowUpRuntime, create_followup_token

    with tempfile.TemporaryDirectory(prefix="focus-verify-") as temp:
        root = Path(temp)
        case = root / "case"; (case / "text_pages").mkdir(parents=True)
        (case / "text_pages/0001.txt").write_text("The synthetic hearing occurred on April 3. The clerk was Ada.\n")
        workspace = root / "workspace"; staged = workspace / ".pi"
        staged.mkdir(parents=True)
        settings = {"defaultProvider": model.provider, "defaultModel": model.model_id,
                    "defaultThinkingLevel": thinking, "enableSkillCommands": True,
                    "compaction": {"enabled": False}, "retry": {"enabled": False}}
        (staged / "settings.json").write_text(json.dumps(settings))
        for relative in ("SYSTEM.md", "skills/focus-answer-record-questions/SKILL.md",
                         "extensions/focus-record-agent.ts", "extensions/focus-followup-bridge.ts"):
            destination = staged / relative; destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(AGENT_RESOURCES / relative, destination)
        run_id = create_focus_run_id(); artifact = root / f"{run_id}.json"
        env = desktop_environment(executable)
        env.update(FOCUS_AGENT_CASE_ROOT=str(case), FOCUS_AGENT_RUN_ID=run_id,
                   FOCUS_AGENT_RUNTIME_DIR=str(root), FOCUS_AGENT_ANSWER_ARTIFACT=str(artifact),
                   FOCUS_AGENT_ANSWER_PROTOCOL=str(PROJECT_DIR / "focus/agent_answer.py"),
                   FOCUS_RECORD_AGENT_HELPER=str(PROJECT_DIR / "focus/agent_helper.py"),
                   FOCUS_RECORD_AGENT_PYTHON=sys.executable)
        # XDG runtime is temporary too; no real sockets or session transcripts.
        directory = root / "followup"; directory.mkdir(mode=0o700)
        followup = FollowUpRuntime(directory=directory, endpoint=FollowUpEndpoint(
            socket_path=directory / "bridge.sock", token=create_followup_token(), generation=1))
        env.update(FOCUS_AGENT_FOLLOWUP_SOCKET=str(followup.endpoint.socket_path),
                   FOCUS_AGENT_FOLLOWUP_TOKEN=followup.endpoint.token,
                   FOCUS_AGENT_FOLLOWUP_RUNTIME_DIR=str(followup.directory))
        command = [executable, "--mode", "rpc", "--no-session", "--approve", "--no-extensions",
                   "--extension", str(staged / "extensions/focus-record-agent.ts"),
                   "--extension", str(staged / "extensions/focus-followup-bridge.ts"),
                   "--no-skills", "--skill", str(staged / "skills/focus-answer-record-questions/SKILL.md"),
                   "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-mcp",
                   "--system-prompt", str(staged / "SYSTEM.md"),
                   "--tools", "read,focus_record,submit_focus_answer"]
        process = subprocess.Popen(command, cwd=workspace, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write((json.dumps({"type": "prompt", "message":
                f"/skill:focus-answer-record-questions <question>Read {case / 'text_pages/0001.txt'}. First call focus_record with action=context, then read the page. Who was the clerk? Submit a short answer using submit_focus_answer.</question>"}) + "\n").encode())
            process.stdin.flush()
            selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + timeout; buffered = b""; total = 0; settled = False; record_ready = False
            while time.monotonic() < deadline:
                events = selector.select(max(0, deadline - time.monotonic()))
                if not events:
                    break
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                buffered += chunk; total += len(chunk)
                if total > 2_000_000:
                    raise PiRuntimeError("Verification exceeded output bound")
                while b"\n" in buffered:
                    line, buffered = buffered.split(b"\n", 1)
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if event.get("type") == "tool_execution_end" and event.get("toolName") == "focus_record":
                        tool_result = event.get("result")
                        details = tool_result.get("details") if isinstance(tool_result, dict) else None
                        record_ready = (isinstance(details, dict) and not event.get("isError")
                                        and details.get("action") == "context"
                                        and not details.get("error") and not details.get("error_code"))
                    if event.get("type") == "agent_settled":
                        settled = True
                if settled:
                    break
            selector.close()
            result = read_focus_answer_artifact(artifact, run_id=run_id)
            answer = result.artifact
            if (not settled or not record_ready or answer is None or answer.status != "complete"
                    or answer.capture != "submit_tool" or "ada" not in answer.markdown.lower()
                    or answer.diagnostics.get("pages_read", 0) < 1
                    or answer.diagnostics.get("provider") != model.provider
                    or answer.diagnostics.get("model") != model.model_id):
                raise PiRuntimeError("Synthetic Agent verification failed; no retry or settings change")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait()
            shutil.rmtree(followup.directory, ignore_errors=True)


def setup(args: argparse.Namespace) -> int:
    executable = args.executable or find_pi()
    if not compatibility(executable).get("ok"):
        if executable:
            raise PiRuntimeError("Existing Pi/Node incompatible. Repair it explicitly; Focus will not replace it")
        install_pi(); executable = find_pi()
    if not compatibility(executable).get("ok"):
        raise PiRuntimeError("Pi 1.1.0+ with Node 22.19+ and required interfaces is required")
    if args.login:
        consent("[WAIT] Open neutral Pi for /login? Complete provider login, then exit Pi")
        with tempfile.TemporaryDirectory(prefix="focus-login-") as cwd, open("/dev/tty", "r+") as tty:
            subprocess.run([executable, "--no-session", "--no-extensions", "--no-skills",
                            "--no-context-files", "--no-prompt-templates", "--no-themes", "--no-mcp"],
                           cwd=cwd, env=desktop_environment(executable), stdin=tty, stdout=tty, stderr=tty, check=True)
    models = discover(executable)
    if not models:
        raise PiRuntimeError("No available models. Run focus setup-pi --login; installation incomplete")
    if args.provider and args.model:
        model = next((m for m in models if m.settings_key == (args.provider, args.model)), None)
        if model is None:
            raise PiRuntimeError("Selected model unavailable")
    else:
        while True:
            for index, item in enumerate(models, 1):
                print(f"{index}. {item.label} ({item.model_id})")
            selection = ask("[ACTION] Model number, or search text:")
            if selection.isdigit() and 1 <= int(selection) <= len(models):
                model = models[int(selection) - 1]; break
            matches = [m for m in models if selection.lower() in (m.label + m.model_id).lower()]
            if matches:
                models = matches
    level = args.thinking or ask("[ACTION] Reasoning: " + ", ".join(model.supported_thinking_levels))
    if level not in model.supported_thinking_levels:
        raise PiRuntimeError("Unsupported reasoning level; choose a listed level")
    if not credential_ready(executable, model):
        raise PiRuntimeError("Credentials unavailable to desktop launcher. Use Pi /login, not a terminal-only key")
    if not args.approve_verification:
        consent("[ACTION] Send ONE small synthetic verification run? Provider billing may apply; no real documents, no automatic retry")
    print("[WAIT] Verifying actual Focus tools and answer artifact (90-second deadline)")
    verify(executable, model, level)
    # These are application-owned save flows, never shell/maintenance JSON edits.
    from .core import _read_config, _write_config
    if config_file().is_symlink():
        raise PiRuntimeError("Focus settings path is a symlink")
    if config_file().exists():
        try:
            if not isinstance(json.loads(config_file().read_text()), dict):
                raise ValueError("not an object")
        except ValueError as exc:
            raise PiRuntimeError("Existing Focus settings malformed; repair by hand") from exc
    config = _read_config(); config["pi_agent_command"] = shlex.join([executable])
    save_project_pi_runtime(model, level); _write_config(config)
    if _read_config().get("pi_agent_command") != config["pi_agent_command"]:
        raise PiRuntimeError("Unable to save Focus executable selection")
    import uuid
    proof = {"schema": 1, "executable": executable, "provider": model.provider,
             "model": model.model_id, "thinking": level, "verified_at": int(time.time())}
    from .pi_runtime import _write_private_settings_temp
    destination = verification_file(); temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
    if destination.is_symlink():
        raise PiRuntimeError("Verification path is a symlink")
    _write_private_settings_temp(temporary, proof)
    os.replace(temporary, destination)
    print("[OK] Pi verified; Focus selection saved; global coding-model preference unchanged")
    return 0


def doctor(as_json: bool = False) -> int:
    executable = find_pi(); checks = {"pi": compatibility(executable)}
    checks["resources"] = {"ok": all((AGENT_RESOURCES / p).is_file() for p in (
        "SYSTEM.md", "extensions/focus-record-agent.ts", "extensions/focus-followup-bridge.ts",
        "skills/focus-answer-record-questions/SKILL.md"))}
    import hashlib
    from importlib.metadata import distribution, PackageNotFoundError
    from urllib.parse import unquote, urlparse
    try:
        direct = json.loads(distribution("focus").read_text("direct_url.json") or "{}")
        editable = direct.get("dir_info", {}).get("editable") is True
        associated = Path(unquote(urlparse(direct.get("url", "")).path)) == PROJECT_DIR
        binding = Path(sys.prefix) / ".focus-install.json"
        if binding.exists():
            associated = associated and json.loads(binding.read_text()).get("source") == str(PROJECT_DIR)
            contract = json.loads((Path(sys.prefix) / "focus-env.json").read_text())
            current = hashlib.sha256(b"".join((PROJECT_DIR / name).read_bytes() for name in ("pyproject.toml", "uv.lock"))).hexdigest()
            associated = associated and contract.get("fingerprint") == current
    except (OSError, ValueError, PackageNotFoundError):
        editable = associated = False
    checks["environment"] = {"ok": sys.prefix != sys.base_prefix and sys.version_info >= (3, 13) and editable and associated,
                             "python": sys.executable, "source": str(PROJECT_DIR), "editable": editable, "associated": associated}
    from .native_check import check_native
    checks["native"] = check_native()
    try:
        settings = json.loads(pi_settings_file().read_text())
        model = PiModel(settings["defaultProvider"], settings["defaultModel"], "configured")
        checks["credentials"] = {"ok": credential_ready(executable, model), "live_request": False}
        proof = json.loads(verification_file().read_text())
        previous = all(proof.get(k) == v for k, v in {
            "executable": executable, "provider": model.provider, "model": model.model_id,
            "thinking": settings.get("defaultThinkingLevel")}.items())
        checks["previous_verification"] = {"ok": previous, "verified_at": proof.get("verified_at")}
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        checks.setdefault("credentials", {"ok": False})
        checks["previous_verification"] = {"ok": False}
    ok = all(check.get("ok") for check in checks.values())
    report = {"ok": ok, "settings": str(config_file()), "checks": checks}
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        for name, check in checks.items():
            print(f"[{'OK' if check.get('ok') else 'FAIL'}] {name}: {json.dumps(check)}")
        print(f"Settings: {config_file()} (credentials are not proof of live access)")
    return 0 if ok else 1
