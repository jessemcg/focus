"""Onboarding uses only synthetic Pi/auth/artifact fixtures, never paid APIs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from focus import setup_pi as s
from focus.pi_runtime import PiModel, PiRuntimeError, available_pi_models


@pytest.fixture
def fake_pi(tmp_path):
    script = tmp_path / "pi"
    script.write_text(f'''#!{sys.executable}
import json,os,sys
args=sys.argv[1:]
if '--version' in args:
 print('1.1.0'); sys.exit(0)
if '--help' in args:
 print('--offline --no-session --no-extensions --no-context-files --system-prompt --skill --tools --approve --mode --no-mcp'); sys.exit(0)
if args[:2] == ['auth','check']:
 print('{{"status":"ready"}}'); sys.exit(0)
request=json.loads(sys.stdin.buffer.readline())
if request['type']=='get_available_models':
 print(json.dumps({{'type':'response','command':'get_available_models','success':True,'data':{{'models':[{{'provider':'synthetic','id':'fixture','name':'Fixture','reasoning':False}}]}}}}), flush=True)
else:
 run=os.environ['FOCUS_AGENT_RUN_ID']
 payload={{'schema_version':1,'run_id':run,'revision':1,'status':'complete','capture':'submit_tool','answer_kind':'answered','markdown':'# Clerk\\n*Verification*\\nThe clerk was Ada.', 'warnings':[], 'diagnostics':{{'provider':'synthetic','model':'fixture','thinking':'off','stop_reason':'toolUse','pages_read':1}}}}
 path=os.environ['FOCUS_AGENT_ANSWER_ARTIFACT']
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as stream: json.dump(payload,stream)
 print(json.dumps({{'type':'tool_execution_end','toolName':'focus_record','isError':False,'result':{{'details':{{'action':'context','error':''}}}}}}),flush=True)
 print(json.dumps({{'type':'agent_settled'}}),flush=True)
sys.stdin.read()
''')
    script.chmod(0o755)
    return script


def test_bounded_offline_discovery_and_reasoning(fake_pi):
    models = s.discover(str(fake_pi))
    assert models == [PiModel("synthetic", "fixture", "Fixture", ("off",))]


def test_terminal_only_credentials_not_in_desktop_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC_DO_NOT_LEAK")
    monkeypatch.setenv("VIRTUAL_ENV", "/other")
    monkeypatch.setenv("XAUTHORITY", "/synthetic/display-auth")
    monkeypatch.setenv("PI_CODING_AGENT_DIR", "/configured/store")
    env = s.desktop_environment("/absolute/bin/pi")
    assert "OPENAI_API_KEY" not in env and "VIRTUAL_ENV" not in env
    assert env["PI_CODING_AGENT_DIR"] == "/configured/store"
    assert env["XAUTHORITY"] == "/synthetic/display-auth"
    assert env["PATH"].startswith("/absolute/bin:")


def test_verification_fixture_and_cleanup(fake_pi, tmp_path, monkeypatch):
    monkeypatch.setattr(s.tempfile, "tempdir", str(tmp_path))
    s.verify(str(fake_pi), PiModel("synthetic", "fixture", "Fixture"), "off", timeout=3)
    assert not list(tmp_path.glob("focus-verify-*"))


def test_verification_requires_successful_structured_record_helper(fake_pi):
    fake_pi.write_text(fake_pi.read_text().replace("'error':''", "'error':'synthetic failure'"))
    with pytest.raises(PiRuntimeError, match="verification failed"):
        s.verify(str(fake_pi), PiModel("synthetic", "fixture", "Fixture"), "off", timeout=3)


def test_failed_verification_does_not_save_settings(fake_pi, monkeypatch):
    args = argparse.Namespace(executable=str(fake_pi), provider="synthetic", model="fixture", thinking="off", login=False, approve_verification=True)
    monkeypatch.setattr(s, "compatibility", lambda *a: {"ok": True})
    monkeypatch.setattr(s, "credential_ready", lambda *a: True)
    def failed(*a): raise PiRuntimeError("Provider failed")
    monkeypatch.setattr(s, "verify", failed)
    monkeypatch.setattr(s, "save_project_pi_runtime", lambda *a: pytest.fail("saved before verification"))
    with pytest.raises(PiRuntimeError, match="Provider failed"):
        s.setup(args)


def test_successful_setup_uses_application_save_flow(fake_pi, tmp_path, monkeypatch):
    from focus import core
    args = argparse.Namespace(executable=str(fake_pi), provider="synthetic", model="fixture", thinking="off", login=False, approve_verification=True)
    monkeypatch.setattr(s, "compatibility", lambda *a: {"ok": True})
    monkeypatch.setattr(s, "credential_ready", lambda *a: True)
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(s, "verification_file", lambda: tmp_path / "pi-verification.json")
    saved = []
    monkeypatch.setattr(s, "save_project_pi_runtime", lambda *args: saved.append(args))
    assert s.setup(args) == 0
    assert saved[0][0].settings_key == ("synthetic", "fixture")
    assert str(fake_pi) in json.loads((tmp_path / "config.json").read_text())["pi_agent_command"]
    assert json.loads((tmp_path / "pi-verification.json").read_text())["provider"] == "synthetic"


@pytest.mark.parametrize("failure", ["credentials", "empty", "reasoning", "declined"])
def test_onboarding_failures_are_incomplete(fake_pi, monkeypatch, failure):
    args = argparse.Namespace(executable=str(fake_pi), provider="synthetic", model="fixture", thinking="off", login=False, approve_verification=True)
    monkeypatch.setattr(s, "compatibility", lambda *a: {"ok": True})
    monkeypatch.setattr(s, "credential_ready", lambda *a: failure != "credentials")
    if failure == "empty": monkeypatch.setattr(s, "discover", lambda *a: [])
    if failure == "reasoning": args.thinking = "high"
    if failure == "declined":
        args.approve_verification = False
        def declined(*a): raise PiRuntimeError("Declined")
        monkeypatch.setattr(s, "consent", declined)
    def canceled_login(*a):
        raise PiRuntimeError("Synthetic login declined")
    monkeypatch.setattr(s, "login_pi", canceled_login)
    monkeypatch.setattr(s, "verify", lambda *a: pytest.fail("unapproved verification"))
    with pytest.raises(PiRuntimeError): s.setup(args)


@pytest.mark.parametrize("needs_install,needs_login,models_visible", [
    (True, True, False), (False, True, False), (True, False, True), (False, True, True),
])
def test_setup_continues_through_install_login_and_verification(fake_pi, tmp_path, monkeypatch, capsys,
                                                               needs_install, needs_login, models_visible):
    from focus import core
    events = []
    installed = not needs_install
    signed_in = not needs_login
    model = PiModel("synthetic", "fixture", "Fixture", ("off",))
    args = argparse.Namespace(executable="", provider="synthetic", model="fixture", thinking="off",
                              login=False, approve_verification=False)
    monkeypatch.setattr(s, "find_pi", lambda: str(fake_pi) if installed else "")
    monkeypatch.setattr(s, "compatibility", lambda executable: {"ok": bool(executable)})

    def install():
        nonlocal installed
        events.append("install")
        installed = True

    def login(executable):
        nonlocal signed_in
        assert executable == str(fake_pi)
        events.append("login")
        signed_in = True

    monkeypatch.setattr(s, "install_pi", install)
    monkeypatch.setattr(s, "login_pi", login)
    monkeypatch.setattr(s, "discover", lambda executable: [model] if signed_in or models_visible else [])
    monkeypatch.setattr(s, "credential_ready", lambda *args: signed_in)
    monkeypatch.setattr(s, "consent", lambda message: events.append("paid consent"))
    monkeypatch.setattr(s, "verify", lambda *args: events.append("verify"))
    monkeypatch.setattr(s, "save_project_pi_runtime", lambda *args: events.append("save"))
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "config.json")
    assert s.setup(args) == 0
    assert events == (["install"] if needs_install else []) + (["login"] if needs_login else []) + ["paid consent", "verify", "save"]
    assert "Pi is installed and compatible" in capsys.readouterr().out
    assert s.verification_file().exists()


def test_install_pi_hands_off_downloaded_file(monkeypatch):
    calls = []
    monkeypatch.setattr(s, "consent", lambda message: None)

    def download(command, **kwargs):
        assert command[0] == "curl"
        Path(command[-1]).write_text("# synthetic installer, never executed")

    def terminal(command, **kwargs):
        assert command[0] == "sh"
        assert Path(command[1]).read_text().startswith("# synthetic")
        assert "OPENAI_API_KEY" not in kwargs["env"]
        calls.append(command[1])

    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC_NOT_FOR_CHILD")
    monkeypatch.setattr(s.subprocess, "run", download)
    monkeypatch.setattr(s, "run_in_terminal", terminal)
    s.install_pi()
    assert len(calls) == 1 and not Path(calls[0]).exists()


def test_login_terminal_is_neutral_and_has_no_prompt(monkeypatch):
    calls = []
    monkeypatch.setattr(s, "consent", lambda message: None)
    monkeypatch.setattr(s, "run_in_terminal", lambda command, **kwargs: calls.append((command, kwargs)))
    s.login_pi("/synthetic/pi")
    command, options = calls[0]
    assert command == ["/synthetic/pi", "--no-session", "--no-extensions", "--no-skills",
                       "--no-context-files", "--no-prompt-templates", "--no-themes", "--no-mcp"]
    assert "/login" in options["instructions"] and "/quit" in options["instructions"]


def test_existing_incompatible_pi_is_not_replaced(fake_pi, monkeypatch):
    monkeypatch.setattr(s, "compatibility", lambda *a: {"ok": False})
    monkeypatch.setattr(s, "install_pi", lambda: pytest.fail("replaced existing Pi"))
    with pytest.raises(PiRuntimeError, match="will not replace"):
        s.setup(argparse.Namespace(executable=str(fake_pi)))


def test_rpc_nonterminated_line_is_bounded(tmp_path):
    from focus.pi_runtime import _pi_rpc_response
    with pytest.raises(PiRuntimeError):
        _pi_rpc_response([sys.executable, "-c", "import sys,time;sys.stdin.readline();sys.stdout.write('x');sys.stdout.flush();time.sleep(10)"],
                         {"type": "get_available_models"}, timeout=0.1)


def test_doctor_distinguishes_auth_from_live_verification(fake_pi, tmp_path, monkeypatch, capsys):
    from focus import native_check
    monkeypatch.setattr(s, "find_pi", lambda: str(fake_pi))
    monkeypatch.setattr(s, "compatibility", lambda *a: {"ok": True})
    monkeypatch.setattr(s, "credential_ready", lambda *a: True)
    monkeypatch.setattr(native_check, "check_native", lambda: {"ok": True})
    monkeypatch.setattr(s, "verify", lambda *a: pytest.fail("doctor sent a live request"))
    settings = s.pi_settings_file(); settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"defaultProvider": "synthetic", "defaultModel": "fixture", "defaultThinkingLevel": "off"}))
    assert s.doctor(True) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["checks"]["credentials"]["ok"] is True
    assert report["checks"]["previous_verification"]["ok"] is False
    s.verification_file().write_text(json.dumps({"executable": str(fake_pi), "provider": "synthetic", "model": "fixture", "thinking": "off", "verified_at": 1}))
    assert s.doctor(True) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["checks"]["previous_verification"]["verified_at"] == 1


def test_maintenance_cli_commands_not_case_directory_arguments(monkeypatch):
    from focus import cli
    monkeypatch.setattr(s, "doctor", lambda as_json: 61 if as_json else 0)
    monkeypatch.setattr(s, "setup", lambda args: 62 if args.approve_verification else 1)
    assert cli.main(["doctor", "--json"]) == 61
    assert cli.main(["setup-pi", "--provider", "synthetic", "--model", "fixture", "--thinking", "off", "--approve-verification"]) == 62


def test_paths_xdg_override_and_legacy_preservation(tmp_path, monkeypatch):
    from focus import paths
    source = tmp_path / "source"; source.mkdir()
    legacy = source / "config.json"; legacy.write_text('{"private":"SYNTHETIC"}')
    monkeypatch.setattr(paths, "PROJECT_DIR", source)
    monkeypatch.delenv("FOCUS_CONFIG_DIR", raising=False)
    assert paths.config_file() == legacy
    monkeypatch.setenv("FOCUS_CONFIG_DIR", str(tmp_path / "new xdg focus"))
    assert paths.config_file() != legacy
    assert paths.pi_settings_file().parent.name == "pi"
    assert legacy.read_text() == '{"private":"SYNTHETIC"}'
    legacy.unlink(); monkeypatch.delenv("FOCUS_CONFIG_DIR")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert paths.config_file() == tmp_path / "xdg/focus/config.json"
