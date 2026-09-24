from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import threading

import pytest

from focus.agent_followup import (
    MAX_TEXT_BYTES,
    FollowUpBusy,
    FollowUpClient,
    FollowUpEndpoint,
    FollowUpProtocolError,
    FollowUpUnauthorized,
    FollowUpUncertain,
    FollowUpUnavailable,
    create_followup_runtime,
    create_followup_token,
    focus_followup_runtime_root,
    normalize_submit_text,
    remove_followup_runtime,
    text_transport_error,
    validate_endpoint,
)


class FakeBridge:
    """Small deterministic Unix-socket server implementing protocol v1."""

    def __init__(
        self,
        socket_path: Path,
        token: str,
        *,
        state: str = "ready",
        fail_mode: str = "",
    ) -> None:
        self.socket_path = socket_path
        self.token = token
        self.state = state
        self.fail_mode = fail_mode
        self.requests: list[dict] = []
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(socket_path))
        self._server.listen(16)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while True:
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            threading.Thread(
                target=self._handle, args=(connection,), daemon=True
            ).start()

    def _handle(self, connection: socket.socket) -> None:
        try:
            data = b""
            while b"\n" not in data:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                data += chunk
            if self.fail_mode == "oversize":
                connection.sendall(b"x" * (300_000) + b"\n")
                return
            if self.fail_mode == "malformed":
                connection.sendall(b"not json\n")
                return
            payload = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
            self.requests.append(payload)
            response = {
                "v": 1,
                "type": payload.get("type"),
                "id": payload.get("id"),
            }
            if payload.get("token") != self.token:
                response.update(ok=False, error="unauthorized", state="closed")
            elif payload.get("v") != 1:
                response.update(ok=False, error="bad_version", state="closed")
            elif self.fail_mode == "busy":
                response.update(ok=False, error="busy", state="busy")
            elif payload.get("type") == "status":
                response.update(ok=True, state=self.state)
            else:
                response.update(ok=True, state="busy", duplicate=False)
            connection.sendall((json.dumps(response) + "\n").encode("utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        finally:
            connection.close()

    def close(self) -> None:
        try:
            self._server.close()
        except OSError:
            pass


@pytest.fixture()
def runtime_root(tmp_path, monkeypatch):
    # AF_UNIX paths are limited; /tmp keeps the pytest temp prefix short.
    root = Path(tempfile.mkdtemp(prefix="fu-", dir="/tmp"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(root))
    try:
        yield focus_followup_runtime_root()
    finally:
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def _endpoint(runtime_root: Path, *, token: str | None = None) -> FollowUpEndpoint:
    directory = Path(tempfile.mkdtemp(prefix="session.", dir=runtime_root))
    return FollowUpEndpoint(
        socket_path=directory / "bridge.sock",
        token=token or create_followup_token(),
        generation=1,
    )


def test_create_and_remove_followup_runtime_is_private(runtime_root) -> None:
    runtime = create_followup_runtime(generation=3)
    assert runtime.directory.stat().st_mode & 0o777 == 0o700
    assert runtime.endpoint.generation == 3
    assert runtime.endpoint.socket_path.parent == runtime.directory
    remove_followup_runtime(runtime.directory)
    assert not runtime.directory.exists()


def test_validate_endpoint_rejects_missing_and_wrong_types(runtime_root) -> None:
    assert validate_endpoint(None) == "missing"
    endpoint = _endpoint(runtime_root)
    assert validate_endpoint(endpoint) == "missing"
    endpoint.socket_path.write_text("not a socket", encoding="utf-8")
    assert validate_endpoint(endpoint) == "invalid_type"
    assert validate_endpoint(
        FollowUpEndpoint(endpoint.socket_path, "short", 1)
    ) == "invalid_token"


def test_client_status_and_submit_round_trip(runtime_root) -> None:
    endpoint = _endpoint(runtime_root)
    bridge = FakeBridge(endpoint.socket_path, endpoint.token)
    try:
        client = FollowUpClient(endpoint)
        assert client.status() == "ready"
        assert client.submit("  hello follow up  ") == "busy"
        submit = bridge.requests[-1]
        assert submit["v"] == 1
        assert submit["type"] == "submit"
        assert submit["text"] == "hello follow up"
    finally:
        bridge.close()


def test_client_rejects_wrong_token(runtime_root) -> None:
    endpoint = _endpoint(runtime_root)
    bridge = FakeBridge(endpoint.socket_path, endpoint.token)
    try:
        with pytest.raises(FollowUpUnauthorized):
            FollowUpClient(
                FollowUpEndpoint(endpoint.socket_path, create_followup_token(), 1)
            ).status()
    finally:
        bridge.close()


def test_client_reports_busy(runtime_root) -> None:
    endpoint = _endpoint(runtime_root)
    bridge = FakeBridge(endpoint.socket_path, endpoint.token, fail_mode="busy")
    try:
        with pytest.raises(FollowUpBusy):
            FollowUpClient(endpoint).submit("question")
    finally:
        bridge.close()


def test_client_rejects_malformed_and_oversized_responses(runtime_root) -> None:
    for mode in ("malformed", "oversize"):
        endpoint = _endpoint(runtime_root)
        bridge = FakeBridge(endpoint.socket_path, endpoint.token, fail_mode=mode)
        try:
            with pytest.raises(FollowUpProtocolError):
                FollowUpClient(endpoint).status()
        finally:
            bridge.close()


def test_client_rejects_oversized_text_before_sending(runtime_root) -> None:
    endpoint = _endpoint(runtime_root)
    bridge = FakeBridge(endpoint.socket_path, endpoint.token)
    try:
        with pytest.raises(FollowUpProtocolError):
            FollowUpClient(endpoint).submit("x" * (MAX_TEXT_BYTES + 1))
        assert bridge.requests == []
    finally:
        bridge.close()


def test_client_reports_uncertain_when_connection_closes_before_reply(
    runtime_root,
) -> None:
    endpoint = _endpoint(runtime_root)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(endpoint.socket_path))
    server.listen(1)

    def _drop() -> None:
        connection, _ = server.accept()
        connection.recv(4096)
        connection.close()

    thread = threading.Thread(target=_drop, daemon=True)
    thread.start()
    try:
        with pytest.raises(FollowUpUncertain):
            FollowUpClient(endpoint).submit("question")
    finally:
        server.close()


def test_client_unavailable_when_socket_absent(runtime_root) -> None:
    endpoint = _endpoint(runtime_root)
    with pytest.raises(FollowUpUnavailable):
        FollowUpClient(endpoint).status()


def test_normalize_submit_text_trims_only_edges() -> None:
    assert normalize_submit_text("  keep  interior \n spaced  ") == "keep  interior \n spaced"
    assert normalize_submit_text("") == ""


def test_text_transport_error_bounds() -> None:
    assert text_transport_error("") == "empty_text"
    assert text_transport_error("ok") == ""
    assert text_transport_error("x" * MAX_TEXT_BYTES) == ""
    assert text_transport_error("x" * (MAX_TEXT_BYTES + 1)) == "too_large"
