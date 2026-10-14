"""Fixed Focus method resources and read-only case/input session pins."""
from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .profile_contract import ProfileError, _json, _require, json_bytes, read_file_at
from .profile_artifacts import source_map_profile_metadata
from .research_context import METHOD_ID, METHOD_VERSION

PROFILE_REF_ENV = "FOCUS_RESEARCH_PROFILE_REF"  # Retired; always strip from child environments.
INPUTS_ENV = "FOCUS_RESEARCH_INPUTS_SHA256"
CASE_ENV = "FOCUS_RESEARCH_CASE_SHA256"
COMPONENT_ENV = "FOCUS_RESEARCH_COMPONENT_SHA256"


@dataclass(frozen=True)
class CompiledResearch:
    skill: str
    component_sha256: str
    resources: tuple[tuple[str, bytes], ...]


def compile_research() -> CompiledResearch:
    package = Path(__file__).parent
    names = (
        "agent_helper.py", "agent_answer.py", "agent_followup.py",
        "profile_artifacts.py", "profile_contract.py", "research_runtime.py",
        "research_context.py", "preparation_context.py",
        "agent_resources/SYSTEM.md",
        "agent_resources/skills/focus-answer-record-questions/SKILL.md",
        "agent_resources/extensions/focus-record-agent.ts",
        "agent_resources/extensions/focus-followup-bridge.ts",
    )
    contents = {name: (package / name).read_bytes() for name in names}
    # The package-owned method is location-independent, including wheel installs.
    # Wrapper permissions are exercised separately by the shell/offline-SDK suite.
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    component = hashlib.sha256(json_bytes({"id": METHOD_ID, "version": METHOD_VERSION,
                                           "resources": hashes})).hexdigest()
    resources = tuple((name.removeprefix("agent_resources/"), data)
                      for name, data in contents.items()
                      if name.startswith("agent_resources/") or name == "agent_answer.py")
    skill = contents["agent_resources/skills/focus-answer-record-questions/SKILL.md"].decode("utf-8")
    return CompiledResearch(skill, component, resources)


def _check_private_directory(path: Path) -> None:
    # No symlink ancestors and no chmod of existing user directories.
    for parent in (*reversed(path.parents), path):
        _require(stat.S_ISDIR(parent.lstat().st_mode), "unsafe_store_directory", "storage")
    info = path.stat()
    _require(info.st_uid == os.getuid() and not info.st_mode & 0o077,
             "store_permissions", "storage")


def stage_research_resources(pin: ResearchPin, workspace: Path) -> Path:
    compiled = compile_research()
    _require(compiled.component_sha256 == pin.research_component_sha256,
             "research_contract_changed", "start_new_session")
    _check_private_directory(workspace)
    destination = workspace / "research-resources"
    destination.mkdir(mode=0o700)
    for relative, contents in compiled.resources:
        target = destination / relative
        current = destination
        for part in target.parent.relative_to(destination).parts:
            current /= part
            current.mkdir(mode=0o700, exist_ok=True)
        with target.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(contents)
    return destination


def preparation_inputs(root: Path) -> tuple[str, dict | None]:
    """Hash consumed inputs, preserving bounded/path/link and collection checks."""
    root = root.resolve(strict=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        map_bytes = read_file_at(fd, "artifacts/source_map.json", limit=64 * 1024 * 1024)
        source_map = _json(map_bytes, "source_map")
        provenance = source_map_profile_metadata(source_map)
        _require(isinstance(source_map.get("pages"), list), "invalid_source_map", "research")
        text_dir = root / "text_pages"
        if text_dir.is_symlink() or not text_dir.is_dir():
            raise ProfileError("invalid_source_directory", "research")
        names = sorted(path.name for path in text_dir.iterdir() if path.suffix == ".txt")
        if len(names) > 100000:
            raise ProfileError("too_many_source_files", "research")
        before = {name: (text_dir / name).lstat() for name in names}
        digest = hashlib.sha256()
        digest.update(json_bytes(["source_map", hashlib.sha256(map_bytes).hexdigest()]))
        extras = {}
        manifest = root / "manifest.json"
        had_manifest = manifest.exists() or manifest.is_symlink()
        if had_manifest:
            data = read_file_at(fd, "manifest.json", limit=4 * 1024 * 1024)
            extras["manifest.json"] = data
            digest.update(json_bytes(["manifest", hashlib.sha256(data).hexdigest()]))
        for name in names:
            data = read_file_at(fd, "text_pages/" + name, limit=16 * 1024 * 1024)
            digest.update(json_bytes([name, hashlib.sha256(data).hexdigest()]))
        from .agent_helper import _case_overview_path
        overview = _case_overview_path(root)
        if overview is not None:
            relative = overview.relative_to(root).as_posix()
            data = read_file_at(fd, relative, limit=4 * 1024 * 1024)
            extras[relative] = data
            digest.update(json_bytes(["overview", hashlib.sha256(data).hexdigest()]))
        if names != sorted(path.name for path in text_dir.iterdir() if path.suffix == ".txt"):
            raise ProfileError("preparation_changed", "research")
        for name, old in before.items():
            new = (text_dir / name).lstat()
            if (old.st_ino, old.st_size, old.st_mtime_ns, old.st_ctime_ns) != (new.st_ino, new.st_size, new.st_mtime_ns, new.st_ctime_ns):
                raise ProfileError("preparation_changed", "research")
        if read_file_at(fd, "artifacts/source_map.json", limit=64 * 1024 * 1024) != map_bytes:
            raise ProfileError("preparation_changed", "research")
        if had_manifest != (manifest.exists() or manifest.is_symlink()) or _case_overview_path(root) != overview:
            raise ProfileError("preparation_changed", "research")
        for relative, original in extras.items():
            if read_file_at(fd, relative, limit=4 * 1024 * 1024) != original:
                raise ProfileError("preparation_changed", "research")
        return digest.hexdigest(), provenance
    finally:
        os.close(fd)


@dataclass(frozen=True)
class ResearchPin:
    inputs_sha256: str
    preparation_json: bytes
    research_component_sha256: str
    case_sha256: str

    @classmethod
    def capture(cls, case_root: Path) -> ResearchPin:
        compiled = compile_research()
        fingerprint, provenance = preparation_inputs(case_root)
        pin = cls(fingerprint, json_bytes(provenance), compiled.component_sha256,
                  hashlib.sha256(os.fsencode(case_root.resolve(strict=True))).hexdigest())
        pin.assert_current(case_root)
        return pin

    def assert_current(self, root: Path) -> None:
        if compile_research().component_sha256 != self.research_component_sha256:
            raise ProfileError("research_contract_changed", "start_new_session")
        if (hashlib.sha256(os.fsencode(root.resolve(strict=True))).hexdigest() != self.case_sha256
                or preparation_inputs(root)[0] != self.inputs_sha256):
            raise ProfileError("preparation_changed", "start_new_session")

    def metadata(self) -> dict:
        return {"schema_version": 2,
                "research_method": {"id": METHOD_ID, "version": METHOD_VERSION,
                                    "component_sha256": self.research_component_sha256},
                "inputs_sha256": self.inputs_sha256,
                "preparation_provenance": _json(self.preparation_json, "preparation")}

    def environment(self, base=None) -> dict[str, str]:
        result = dict(base or {})
        result.pop(PROFILE_REF_ENV, None)
        result.update({INPUTS_ENV: self.inputs_sha256, CASE_ENV: self.case_sha256,
                       COMPONENT_ENV: self.research_component_sha256})
        return result


def assert_environment_inputs(root: Path) -> None:
    """Diagnostics need no pin; session helpers check the complete fixed-method pin."""
    values = [os.environ.get(key) for key in (INPUTS_ENV, CASE_ENV, COMPONENT_ENV)]
    if all(value is None for value in values):
        return
    if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in values):
        raise ProfileError("invalid_research_pin", "start_new_session")
    expected, case_key, component = values
    if compile_research().component_sha256 != component:
        raise ProfileError("research_contract_changed", "start_new_session")
    if (hashlib.sha256(os.fsencode(root.resolve(strict=True))).hexdigest() != case_key
            or preparation_inputs(root)[0] != expected):
        raise ProfileError("preparation_changed", "start_new_session")
