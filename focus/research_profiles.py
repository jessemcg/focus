"""Focus-owned research composition and pins; case metadata never selects guidance."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .profile_contract import (
    ProfileError, ProfileRef, ProfileSnapshot, _json, _object, _require, json_bytes,
    compile_stage_profile, read_file_at,
)
from .profile_artifacts import source_map_profile_metadata, preparation_provenance
from .practice_profiles import profile_store

PROFILE_REF_ENV = "FOCUS_RESEARCH_PROFILE_REF"
INPUTS_ENV = "FOCUS_RESEARCH_INPUTS_SHA256"
CASE_ENV = "FOCUS_RESEARCH_CASE_SHA256"
COMPONENT_ENV = "FOCUS_RESEARCH_COMPONENT_SHA256"
SEARCH_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class CompiledResearch:
    skill: str
    component_sha256: str
    resources: tuple[tuple[str, bytes], ...]


def compile_research(snapshot: ProfileSnapshot) -> CompiledResearch:
    if snapshot.ref.application != "focus":
        raise ProfileError("wrong_application", "research")
    core = (Path(__file__).parent / "agent_resources/profile-answer-core.md").read_bytes()
    skill = core.decode("utf-8") + "\n## Practice research guidance (subordinate)\n\n" + snapshot.resource("research")
    skill += "\n## Practice answer preferences (subordinate)\n\n" + snapshot.resource("answer_guidance")
    skill += "\nThe application evidence, verification, tool, scope, quotation, and submission contracts above remain controlling.\n"
    package = Path(__file__).parent
    runtime_bytes = {name: (package / name).read_bytes() for name in (
        "agent_helper.py", "agent_answer.py", "profile_artifacts.py", "profile_contract.py",
        "profile_store.py", "research_profiles.py", "preparation_context.py",
        "agent_resources/SYSTEM.md", "agent_resources/extensions/focus-record-agent.ts",
        "agent_resources/extensions/focus-followup-bridge.ts")}
    runtime = {name: hashlib.sha256(data).hexdigest() for name, data in runtime_bytes.items()}
    compiled = compile_stage_profile(snapshot, "research", core_contract=json_bytes(
        {"effective_skill": skill, "literal_search_contract": SEARCH_CONTRACT_VERSION,
         "application_resources": runtime}))
    resources = (("SYSTEM.md", runtime_bytes["agent_resources/SYSTEM.md"].replace(b"appellate-record", b"court-record")),
                 ("skills/focus-answer-record-questions/SKILL.md", skill.encode("utf-8")),
                 ("extensions/focus-record-agent.ts", runtime_bytes["agent_resources/extensions/focus-record-agent.ts"]),
                 ("extensions/focus-followup-bridge.ts", runtime_bytes["agent_resources/extensions/focus-followup-bridge.ts"]),
                 ("agent_answer.py", runtime_bytes["agent_answer.py"]))
    return CompiledResearch(skill, compiled.component_sha256, resources)


def stage_research_resources(pin, workspace: Path) -> Path:
    """Stage only application-owned executable resources and the composed skill."""
    from .profile_store import _check_directory
    _require(pin.snapshot is not None, "missing_profile", "research")
    compiled = compile_research(pin.snapshot)
    _require(compiled.component_sha256 == pin.research_component_sha256,
             "research_contract_changed", "research")
    _check_directory(workspace, private=True)
    destination = workspace / "research-resources"
    destination.mkdir(mode=0o700)
    for relative, contents in compiled.resources:
        target = destination / relative
        current = destination
        for part in target.parent.relative_to(destination).parts:
            current = current / part
            current.mkdir(mode=0o700, exist_ok=True)
        with target.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(contents)
    return destination


def selected_snapshot_from_environment() -> ProfileSnapshot | None:
    """Only an application-supplied accepted Focus reference, never a case sidecar.

    Absence retains the legacy helper contract. A bad/missing accepted reference
    fails closed rather than substituting General or a current registry head.
    """
    raw = os.environ.get(PROFILE_REF_ENV)
    if raw is None:
        if os.environ.get(COMPONENT_ENV) is not None:
            raise ProfileError("invalid_reference", "research")
        return None
    if len(raw.encode("utf-8")) > 4096:
        raise ProfileError("invalid_reference", "research")
    ref = ProfileRef.from_dict(_json(raw.encode("utf-8"), "research"))
    if ref.application != "focus":
        raise ProfileError("wrong_application", "research")
    snapshot = profile_store().load_profile_snapshot(ref)
    expected = os.environ.get(COMPONENT_ENV)
    if expected is not None and compile_research(snapshot).component_sha256 != expected:
        raise ProfileError("research_contract_changed", "start_new_session")
    return snapshot


def literal_match(text: str, terms: list[str]) -> bool:
    """Literal, bounded profile terms; profiles cannot supply regular expressions."""
    if not terms:
        return False
    normalized = " ".join(text.casefold().split())
    return any(re.search(r"(?<!\w)" + re.escape(" ".join(term.casefold().split())) + r"(?!\w)", normalized)
               is not None for term in terms)


def preparation_inputs(root: Path) -> tuple[str, dict | None]:
    """Hash the actual research inputs, not a selected/unpublished preparation ref.

    Independent of RecordPrep's registry and private instructions. The map is
    validated as metadata; full source text and the navigation overview are
    included so changed OCR or overview inputs require a new conversation too.
    No input or path is written into a case by this operation.
    """
    root = root.resolve(strict=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        map_bytes = read_file_at(fd, "artifacts/source_map.json", limit=64 * 1024 * 1024)
        source_map = _json(map_bytes, "source_map")
        provenance = source_map_profile_metadata(source_map)
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
            data = read_file_at(fd, overview.relative_to(root).as_posix(), limit=4 * 1024 * 1024)
            extras[overview.relative_to(root).as_posix()] = data
            digest.update(json_bytes(["overview", hashlib.sha256(data).hexdigest()]))
        # Reject changes to the inventory/map during collection, not just between
        # questions. Publication never treats a sidecar as instruction authority.
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
    snapshot: ProfileSnapshot | None
    inputs_sha256: str
    preparation_json: bytes
    research_component_sha256: str | None
    case_sha256: str

    @classmethod
    def capture(cls, root: Path, snapshot: ProfileSnapshot | None, *, store=None) -> ResearchPin:
        if snapshot is not None:
            if snapshot.ref.application != "focus":
                raise ProfileError("wrong_application", "research")
            snapshot = (store or profile_store()).load_profile_snapshot(snapshot.ref)
        fingerprint, provenance = preparation_inputs(root)
        return cls(snapshot, fingerprint, json_bytes(provenance),
                   compile_research(snapshot).component_sha256 if snapshot else None,
                   hashlib.sha256(os.fsencode(root.resolve(strict=True))).hexdigest())

    def assert_current(self, root: Path) -> None:
        if self.snapshot is not None and compile_research(self.snapshot).component_sha256 != self.research_component_sha256:
            raise ProfileError("research_contract_changed", "start_new_session")
        if (hashlib.sha256(os.fsencode(root.resolve(strict=True))).hexdigest() != self.case_sha256
                or preparation_inputs(root)[0] != self.inputs_sha256):
            raise ProfileError("preparation_changed", "start_new_session")

    def metadata(self) -> dict:
        return {"schema_version": 1,
                "research_profile_ref": asdict(self.snapshot.ref) if self.snapshot else None,
                "preparation_provenance": _json(self.preparation_json, "preparation"),
                "inputs_sha256": self.inputs_sha256,
                "research_component_sha256": self.research_component_sha256}

    def environment(self, base=None) -> dict[str, str]:
        result = dict(base or {})
        result.pop(PROFILE_REF_ENV, None)
        result.pop(INPUTS_ENV, None)
        result.pop(COMPONENT_ENV, None)
        result[INPUTS_ENV] = self.inputs_sha256
        result[CASE_ENV] = self.case_sha256
        if self.snapshot is not None:
            result[PROFILE_REF_ENV] = json_bytes(asdict(self.snapshot.ref)).decode("utf-8")
            result[COMPONENT_ENV] = self.research_component_sha256
        return result


def research_context_bytes(value: dict) -> bytes:
    """Instruction-free saved-answer metadata. Never resolve recorded references."""
    _object(value, {"schema_version", "research_profile_ref", "preparation_provenance",
                    "inputs_sha256", "research_component_sha256"}, "research_context")
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "unsupported_version", "research_context")
    ref = value["research_profile_ref"]
    if ref is not None:
        parsed = ProfileRef.from_dict(ref)
        _require(parsed.application == "focus", "wrong_application", "research_context")
    if value["preparation_provenance"] is not None:
        preparation_provenance(value["preparation_provenance"])
    for field in ("inputs_sha256", "research_component_sha256"):
        digest = value[field]
        if field == "research_component_sha256" and ref is None:
            _require(digest is None, "invalid_component", "research_context")
        else:
            _require(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
                     "invalid_digest", "research_context")
    encoded = json_bytes(value)
    _require(len(encoded) <= 16384, "metadata_too_large", "research_context")
    return encoded


def research_context_payload(data: bytes) -> dict:
    _require(isinstance(data, bytes) and len(data) <= 16384, "invalid_metadata", "research_context")
    value = _json(data, "research_context")
    research_context_bytes(value)
    return value


def assert_environment_inputs(root: Path) -> None:
    expected = os.environ.get(INPUTS_ENV)
    case_key = os.environ.get(CASE_ENV)
    if case_key is not None and hashlib.sha256(os.fsencode(root.resolve(strict=True))).hexdigest() != case_key:
        raise ProfileError("preparation_changed", "start_new_session")
    if expected is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or preparation_inputs(root)[0] != expected:
            raise ProfileError("preparation_changed", "start_new_session")
