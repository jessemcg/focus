import os

import pytest

from focus import model_settings
from focus._model_store import Endpoint, Failure
from focus.research_skills import (
    MAX_SKILL_BYTES, SkillChanged, SkillPreferences, discover_skills, preferences_path,
    read_preferences, read_selected_skill, save_preferences,
)


def test_two_layouts_titles_search_keys_and_no_recursion(tmp_path):
    (tmp_path / "a.md").write_text("---\nname: wrong\nmodel: ignored\n---\n# Same *title*\n\nFirst line.\nSecond line.\n")
    (tmp_path / "b").mkdir()
    (tmp_path / "b/SKILL.md").write_text("Same title\n==========\n\nOther body.\n")
    (tmp_path / "b/hidden.md").write_text("# Not a separate entry")
    (tmp_path / "b/deeper").mkdir()
    (tmp_path / "b/deeper/SKILL.md").write_text("# Too deep")
    (tmp_path / ".hidden.md").write_text("# Hidden")
    (tmp_path / "c.md").write_text("What happened?\n")
    (tmp_path / "d").mkdir()
    (tmp_path / "d/SKILL.md").write_text("What else happened?\n")
    listing = discover_skills(str(tmp_path))
    assert not listing.notices
    assert [(s.title, s.key) for s in listing.skills] == [
        ("c", "c.md"), ("d", "d/SKILL.md"), ("Same title", "a.md"), ("Same title", "b/SKILL.md"),
    ]
    assert read_selected_skill(str(tmp_path), listing.skills[2]) == "# Same *title*\n\nFirst line.\nSecond line.\n"


@pytest.mark.parametrize("change", ["edit", "replace", "remove", "link"])
def test_recheck_does_not_run_changed_entry(tmp_path, change):
    path = tmp_path / "original.md"
    path.write_text("# Question\nFirst version\n")
    chosen, = discover_skills(str(tmp_path)).skills
    if change == "edit":
        path.write_text("# Question\nEdited version\n")
    else:
        original = path.read_bytes()
        path.unlink()
        if change == "replace":
            path.write_bytes(original)
        elif change == "link":
            target = tmp_path / "elsewhere"
            target.write_bytes(original)
            path.symlink_to(target)
    with pytest.raises(SkillChanged, match="changed or disappeared"):
        read_selected_skill(str(tmp_path), chosen)


def test_bad_entries_are_notices_and_never_hide_good_siblings(tmp_path):
    files = {"invalid.md": b"\xff", "frontmatter.md": b"---\nUnclosed", "empty.md": b" \n",
             "huge.md": b"A" * (MAX_SKILL_BYTES + 1), "good.md": b"Exactly bounded\n" + b"a" * (MAX_SKILL_BYTES - 16)}
    for name, contents in files.items():
        (tmp_path / name).write_bytes(contents)
    assert (tmp_path / "good.md").stat().st_size == MAX_SKILL_BYTES
    (tmp_path / "symlink.md").symlink_to(tmp_path / "good.md")
    os.mkfifo(tmp_path / "fifo.md")
    (tmp_path / "original").write_bytes(b"Hardlinked text")
    (tmp_path / "hard.md").hardlink_to(tmp_path / "original")
    (tmp_path / "redirect").symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/SKILL.md").symlink_to(tmp_path / "good.md")
    listing = discover_skills(str(tmp_path))
    assert [s.key for s in listing.skills] == ["good.md"]
    for entry, reason in [("invalid.md", "UTF-8"), ("frontmatter.md", "delimiter"), ("empty.md", "question text"),
                          ("huge.md", "64 KiB"), ("symlink.md", "link"), ("hard.md", "link"), ("fifo.md", "regular"),
                          ("redirect", "link"), ("nested/SKILL.md", "link")]:
        assert any(entry in notice and reason in notice for notice in listing.notices), listing
    for folder in (tmp_path / "missing", tmp_path / "redirect", tmp_path / "fifo.md"):
        assert discover_skills(str(folder)).notices[0].startswith("Cannot open")


def test_guarded_preferences_and_protocol_omit_folder_and_inherited_slot(tmp_path, monkeypatch):
    monkeypatch.setenv("FOCUS_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(tmp_path / "global"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    pi_path = tmp_path / "pi/settings.json"
    pi_path.parent.mkdir()
    ordinary = b'{  "defaultProvider":"fireworks", "defaultModel":"accounts/fireworks/models/fast", "defaultThinkingLevel":"medium" }\n'
    pi_path.write_bytes(ordinary)
    folder = str(tmp_path / "not-published-in-protocol")
    prefs_path = preferences_path()
    endpoint = Endpoint("focus", model_settings.resolve)
    assert read_preferences() == (SkillPreferences(), "missing")
    assert len(endpoint.execute("inspect", {})["slots"]) == 1
    assert not prefs_path.exists() and not list(tmp_path.glob(".*writer.lock"))
    rev = save_preferences(SkillPreferences(folder), "missing")
    assert len(endpoint.execute("inspect", {})["slots"]) == 1
    key = ("fireworks", "accounts/fireworks/models/standard")
    prefs = SkillPreferences(folder, key, "low")
    rev2 = save_preferences(prefs, rev)
    assert rev != rev2 and read_preferences() == (prefs, rev2)
    with pytest.raises(Failure, match="stale_settings"):
        save_preferences(SkillPreferences(), rev)
    inventory = endpoint.execute("inspect", {})
    assert folder not in str(inventory)
    assert inventory["slots"][1]["slot_id"] == "research-skills"
    assert inventory["slots"][1]["reasoning"] == {"requested": "low"}
    pi_path.unlink()
    without_default = endpoint.execute("inspect", {})
    assert [slot["slot_id"] for slot in without_default["slots"]] == ["research-skills"]
    pi_path.write_bytes(ordinary)
    plan = endpoint.execute("preview", {"source": {"provider": key[0], "model": key[1]},
                "target": {"provider": "fireworks", "model": "accounts/fireworks/models/another"}})
    result = endpoint.execute("apply", {"plan_id": plan["plan_id"], "plan_binding": plan["plan_binding"],
                                           "expected_revision": plan["baseline_revision"]})
    assert result["status"] == "applied"
    assert read_preferences()[0] == SkillPreferences(folder, ("fireworks", "accounts/fireworks/models/another"), "low")
    assert pi_path.read_bytes() == ordinary
    endpoint.execute("rollback", {"operation_id": plan["plan_id"], "plan_binding": plan["plan_binding"]})
    assert read_preferences()[0] == prefs
    save_preferences(SkillPreferences(), read_preferences()[1])
    assert not folder in prefs_path.read_text()
    assert len(endpoint.execute("inspect", {})["slots"]) == 1
    assert pi_path.read_bytes() == ordinary
