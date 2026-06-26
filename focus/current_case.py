#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


CURRENT_CASE_FILE = Path(
    "/home/jesse/Dropbox/MCGLAW/config_files/scripts/misc/currently_selected_case"
)
OPEN_CASES_ROOT = Path("/home/jesse/Dropbox/MCGLAW/OPEN_CASES")
CLOSED_CASES_ROOT = Path("/home/jesse/Dropbox/MCGLAW/CLOSED_CASES")
FOCUS_CONFIG = Path(__file__).resolve().parent.parent / "config.json"
BUNDLE_RELATIVE_PATH = Path("0_record") / "case_bundle"


class CurrentCaseFocusError(RuntimeError):
    pass


def _clean_case_name(raw_case: str) -> str:
    case_name = raw_case.replace("\r", "").strip()
    if not case_name:
        raise CurrentCaseFocusError("Current case file is empty.")
    if "/" in case_name or "\\" in case_name or case_name in {".", ".."}:
        raise CurrentCaseFocusError(f"Invalid current case name: {case_name!r}")
    return case_name


def _normalize_root(root: Path) -> Path:
    return Path(os.path.normpath(str(root))).expanduser()


def read_current_case(case_file: Path) -> str:
    if not case_file.is_file():
        raise CurrentCaseFocusError(f"Current case file not found: {case_file}")
    return _clean_case_name(case_file.read_text(encoding="utf-8"))


def resolve_case_dir(case_name: str, roots: list[Path]) -> Path:
    for root in roots:
        target = _normalize_root(root) / case_name
        if target.is_dir():
            return target.resolve(strict=False)

    roots_text = ", ".join(str(root) for root in roots)
    raise CurrentCaseFocusError(f"Selected case {case_name!r} not found in {roots_text}.")


def resolve_case_bundle(case_dir: Path) -> Path:
    bundle = case_dir / BUNDLE_RELATIVE_PATH
    if not bundle.is_dir():
        raise CurrentCaseFocusError(f"Case bundle not found: {bundle}")
    return bundle.resolve(strict=False)


def _read_config(config_path: Path) -> dict[str, object]:
    if not config_path.exists():
        return {}

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurrentCaseFocusError(f"Unable to read Focus config at {config_path}: {exc}") from exc

    if not isinstance(config, dict):
        raise CurrentCaseFocusError(f"Focus config is not a JSON object: {config_path}")
    return config


def update_focus_config(config_path: Path, input_dir: Path) -> bool:
    config = _read_config(config_path)
    input_dir_text = str(input_dir)
    if config.get("input_dir") == input_dir_text:
        return False

    config["input_dir"] = input_dir_text
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_name(f".{config_path.name}.tmp")
    temp_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(config_path)
    return True


def refresh_focus_config(args: argparse.Namespace) -> bool:
    case_name = read_current_case(args.current_case_file)
    case_dir = resolve_case_dir(case_name, [args.open_root, args.closed_root])
    bundle = resolve_case_bundle(case_dir)
    changed = update_focus_config(args.config, bundle)
    if not args.quiet:
        action = "Updated" if changed else "Already current"
        print(f"{action}: {args.config} -> {bundle}")
    return changed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Point Focus at the currently selected local MCGLAW case bundle."
    )
    parser.add_argument("--current-case-file", type=Path, default=CURRENT_CASE_FILE)
    parser.add_argument("--open-root", type=Path, default=OPEN_CASES_ROOT)
    parser.add_argument("--closed-root", type=Path, default=CLOSED_CASES_ROOT)
    parser.add_argument("--config", type=Path, default=FOCUS_CONFIG)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        refresh_focus_config(args)
    except CurrentCaseFocusError as exc:
        print(f"Warning: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
