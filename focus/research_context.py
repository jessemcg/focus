"""Instruction-free research metadata; historical references never load snapshots."""
from __future__ import annotations

import re

from .profile_contract import ProfileRef, _json, _object, _require, json_bytes
from .profile_artifacts import preparation_provenance

METHOD_ID = "focus-record-qa"
METHOD_VERSION = 1


def research_context_bytes(value: dict) -> bytes:
    _require(isinstance(value, dict), "invalid_metadata", "research_context")
    version = value.get("schema_version")
    _require(type(version) is int and version in (1, 2), "unsupported_version", "research_context")
    if version == 1:
        _object(value, {"schema_version", "research_profile_ref", "preparation_provenance",
                        "inputs_sha256", "research_component_sha256"}, "research_context")
        ref = value["research_profile_ref"]
        if ref is not None:
            parsed = ProfileRef.from_dict(ref)
            _require(parsed.application == "focus", "wrong_application", "research_context")
        digest = value["research_component_sha256"]
        if ref is None:
            _require(digest is None, "invalid_component", "research_context")
        else:
            _digest(digest)
    else:
        _object(value, {"schema_version", "research_method", "inputs_sha256",
                        "preparation_provenance"}, "research_context")
        method = value["research_method"]
        _object(method, {"id", "version", "component_sha256"}, "research_method")
        _require(method["id"] == METHOD_ID and type(method["version"]) is int
                 and method["version"] == METHOD_VERSION, "unsupported_method", "research_context")
        _digest(method["component_sha256"])
    _digest(value["inputs_sha256"])
    if value["preparation_provenance"] is not None:
        preparation_provenance(value["preparation_provenance"])
    encoded = json_bytes(value)
    _require(len(encoded) <= 16384, "metadata_too_large", "research_context")
    return encoded


def _digest(value) -> None:
    _require(isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value)),
             "invalid_digest", "research_context")


def research_context_payload(data: bytes) -> dict:
    _require(isinstance(data, bytes) and len(data) <= 16384, "invalid_metadata", "research_context")
    value = _json(data, "research_context")
    research_context_bytes(value)
    return value


def saved_schema_for_context(context: bytes | None) -> int:
    if context is None:
        return 1
    return 3 if research_context_payload(context)["schema_version"] == 2 else 2
