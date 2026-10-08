"""Real installed Pi + real Focus extensions against loopback synthetic SSE only."""
import json
import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from focus import setup_pi
from focus.pi_runtime import PiModel


@pytest.mark.parametrize("scenario", ["success", "rejected"])
def test_real_pi_extensions_artifact_with_local_fake_provider(tmp_path, monkeypatch, scenario):
    executable = shutil.which("pi")
    if not executable:
        pytest.skip("Compatible installed Pi required for local fake-provider acceptance")
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(payload)
            tools = {tool["function"]["name"] for tool in payload["tools"]}
            assert tools == {"read", "focus_record", "submit_focus_answer"}
            if scenario == "rejected":
                self.send_response(500); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(b'{"error":{"message":"Synthetic provider rejection","type":"server_error"}}')
                return
            if len(requests) == 1:
                user = next(message for message in reversed(payload["messages"]) if message["role"] == "user")
                text = user["content"]
                if isinstance(text, list):
                    text = " ".join(part.get("text", "") for part in text)
                source = re.search(r"Read (/[^\n]+?/text_pages/0001.txt)", text).group(1)
                calls = [("focus_record", {"action": "context"}), ("read", {"path": source})]
            else:
                calls = [("submit_focus_answer", {"answer_kind": "answered", "markdown": "# Clerk\n*Synthetic verification*\nThe clerk was Ada."})]
            tool_calls = [{"index": i, "id": f"call_{len(requests)}_{i}", "type": "function",
                           "function": {"name": name, "arguments": json.dumps(arguments)}}
                          for i, (name, arguments) in enumerate(calls)]
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for delta, reason in (({"role": "assistant", "tool_calls": tool_calls}, None), ({}, "tool_calls")):
                event = {"id": "synthetic", "object": "chat.completion.chunk", "created": 1, "model": "fixture",
                         "choices": [{"index": 0, "delta": delta, "finish_reason": reason}]}
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    agent = tmp_path / "synthetic-pi"; agent.mkdir()
    models = {"providers": {"synthetic": {"baseUrl": f"http://127.0.0.1:{server.server_port}/v1", "api": "openai-completions",
               "apiKey": "SYNTHETIC_NOT_A_CREDENTIAL", "models": [{"id": "fixture", "name": "Fixture", "reasoning": False,
               "contextWindow": 16384, "maxTokens": 512, "input": ["text"], "compat": {"supportsDeveloperRole": False}}]}}}
    (agent / "models.json").write_text(json.dumps(models))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(agent))
    # HOME remains synthetic; no real auth/model/session files are available to Pi.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, str(tmp_path / key.lower()))
    # Existing npm-style Pi may need Node's absolute parent in the minimal PATH.
    node = shutil.which("node")
    original_environment = setup_pi.desktop_environment
    def environment(executable=""):
        env = original_environment(executable)
        if node:
            env["PATH"] = str(Path(node).parent) + ":" + env["PATH"]
        return env
    monkeypatch.setattr(setup_pi, "desktop_environment", environment)
    try:
        model = PiModel("synthetic", "fixture", "Fixture", ("off",))
        if scenario == "success":
            setup_pi.verify(executable, model, "off", timeout=20)
            assert len(requests) == 2
            assert any(message["role"] == "tool" and "Ada" in str(message["content"])
                       for message in requests[1]["messages"])
            assert any(message["role"] == "tool" and "source_map" in str(message["content"])
                       for message in requests[1]["messages"])
        else:
            from focus.pi_runtime import PiRuntimeError
            with pytest.raises(PiRuntimeError, match="verification failed"):
                setup_pi.verify(executable, model, "off", timeout=20)
            assert len(requests) == 1  # no automatic retry of a setup billing decision
        assert not list(agent.glob("sessions/**/*.jsonl"))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
