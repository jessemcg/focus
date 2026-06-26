from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_app(args: argparse.Namespace) -> int:
    from .app import run

    return run(input_dir=args.directory)


def _cmd_refresh_current_case(args: argparse.Namespace) -> int:
    from .current_case import main as current_case_main

    argv: list[str] = []
    if args.current_case_file is not None:
        argv.extend(["--current-case-file", str(args.current_case_file)])
    if args.open_root is not None:
        argv.extend(["--open-root", str(args.open_root)])
    if args.closed_root is not None:
        argv.extend(["--closed-root", str(args.closed_root)])
    if args.config is not None:
        argv.extend(["--config", str(args.config)])
    if args.quiet:
        argv.append("--quiet")
    return current_case_main(argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="focus")
    subparsers = parser.add_subparsers(dest="command")

    app_parser = subparsers.add_parser("app", help="launch the GTK app")
    app_parser.add_argument("directory", nargs="?", type=Path)
    app_parser.set_defaults(func=_cmd_app)

    refresh_parser = subparsers.add_parser(
        "refresh-current-case",
        help="point Focus config at the currently selected case bundle",
    )
    refresh_parser.add_argument("--current-case-file", type=Path, default=None)
    refresh_parser.add_argument("--open-root", type=Path, default=None)
    refresh_parser.add_argument("--closed-root", type=Path, default=None)
    refresh_parser.add_argument("--config", type=Path, default=None)
    refresh_parser.add_argument("--quiet", action="store_true")
    refresh_parser.set_defaults(func=_cmd_refresh_current_case)
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0] not in {"app", "refresh-current-case", "-h", "--help"}:
        args_list.insert(0, "app")
    parser = build_parser()
    args = parser.parse_args(args_list)
    return int(args.func(args))
