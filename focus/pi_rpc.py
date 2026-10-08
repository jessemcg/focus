"""Bounded neutral, offline RPC discovery transport."""
from __future__ import annotations

import json
import os
import selectors
import subprocess
import tempfile
import time


def response(command: list[str], request: dict, *, timeout: float, environment: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="focus-pi-discovery-") as cwd:
        process = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            assert process.stdin and process.stdout
            process.stdin.write(json.dumps(request).encode() + b"\n"); process.stdin.flush()
            deadline = time.monotonic() + timeout; buffer = b""; total = 0
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    if not selector.select(max(0, deadline - time.monotonic())):
                        break
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    buffer += chunk; total += len(chunk)
                    if total > 2_000_000:
                        raise RuntimeError("Pi discovery exceeded output bound")
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if (isinstance(event, dict) and event.get("type") == "response"
                                and event.get("command") == request.get("type")):
                            return event
            raise RuntimeError("Pi did not return a model response (timed out or exited)")
        finally:
            process.stdin.close()
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=2)
            process.stdout.close()
