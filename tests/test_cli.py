from pathlib import Path

import focus.cli as cli
import focus.current_case as current_case


def test_main_defaults_to_app_command_for_directory(monkeypatch) -> None:
    captured: dict[str, Path | None] = {}

    def fake_cmd_app(args) -> int:
        captured["directory"] = args.directory
        return 17

    monkeypatch.setattr(cli, "_cmd_app", fake_cmd_app)

    assert cli.main(["/tmp/case_bundle"]) == 17
    assert captured["directory"] == Path("/tmp/case_bundle")


def test_main_routes_explicit_app_command(monkeypatch) -> None:
    captured: dict[str, Path | None] = {}

    def fake_cmd_app(args) -> int:
        captured["directory"] = args.directory
        return 0

    monkeypatch.setattr(cli, "_cmd_app", fake_cmd_app)

    assert cli.main(["app"]) == 0
    assert captured["directory"] is None


def test_refresh_current_case_passes_arguments(monkeypatch, tmp_path) -> None:
    captured: dict[str, list[str] | None] = {}

    def fake_current_case_main(argv=None) -> int:
        captured["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(current_case, "main", fake_current_case_main)

    config = tmp_path / "config.json"
    assert cli.main(["refresh-current-case", "--config", str(config), "--quiet"]) == 0
    assert captured["argv"] == ["--config", str(config), "--quiet"]
