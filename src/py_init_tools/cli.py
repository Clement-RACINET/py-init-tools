# Copyright (c) 2026 Clément RACINET
"""Command-line interface for py-init-tools."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path
from typing import cast

from py_init_tools.config import load_config
from py_init_tools.generator import generate_files
from py_init_tools.writer import apply_files, check_files


class CliArgs(argparse.Namespace):
    """Typed command-line arguments."""

    package_root: list[str]
    test_root: list[str]
    write: bool
    check: bool
    overwrite_manual: bool
    ignore_manual_in_check: bool
    skip_tests: bool


def _configure_stdout() -> None:
    """Configure stdout for robust UTF-8 output on Windows."""
    stdout = sys.stdout

    if isinstance(stdout, io.TextIOWrapper):
        stdout.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="pyinit",
        description="Safely audit and generate Python __init__.py files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--package-root",
        action="append",
        default=[],
        help=(
            "Package root to process. Can be passed multiple times. "
            "Overrides package_roots from pyproject.toml."
        ),
    )
    parser.add_argument(
        "--test-root",
        action="append",
        default=[],
        help=(
            "Test root to process. Can be passed multiple times. "
            "Overrides test_roots from pyproject.toml."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write generated files. Without this flag, the tool runs in dry-run mode.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated files and exit non-zero if they are outdated.",
    )
    parser.add_argument(
        "--overwrite-manual",
        action="store_true",
        help="Allow overwriting __init__.py files without the generated marker.",
    )
    parser.add_argument(
        "--ignore-manual-in-check",
        action="store_true",
        help="Treat manual __init__.py files as OK in --check mode.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip processing test package markers.",
    )

    return parser


def parse_args(parser: argparse.ArgumentParser) -> CliArgs:
    """Parse and type command-line arguments."""
    return cast("CliArgs", parser.parse_args())


def main() -> None:
    """Run the command-line interface."""
    _configure_stdout()

    parser = build_parser()
    args = parse_args(parser)

    if args.write and args.check:
        parser.error("--write and --check cannot be used together.")

    cfg = load_config(
        cwd=Path.cwd(),
        package_roots=tuple(args.package_root),
        test_roots=tuple(args.test_root),
    )

    dry_run = not args.write and not args.check
    generated_files = generate_files(cfg, include_tests=not args.skip_tests)

    print(f"Project root    : {cfg.project_root}")
    print("Package roots   :")

    for root in cfg.package_roots:
        print(f"  - {root}")

    print("Test roots      :")

    for root in cfg.test_roots:
        print(f"  - {root}")

    print(f"Generated files : {len(generated_files)}")
    print(f"Discovery mode  : {cfg.discovery_mode}")
    print("Re-export allowlist:")

    for package_key in sorted(cfg.reexport_allowlist):
        print(f"  - {package_key}")

    if args.check:
        print("\nChecking generated __init__.py files...\n")
        success = check_files(
            cfg,
            generated_files,
            ignore_manual=args.ignore_manual_in_check,
        )

        if not success:
            raise SystemExit(1)

        print("\nCheck passed.")
        return

    if dry_run:
        print("\nDry-run mode. No files will be written.\n")
    else:
        print("\nWriting generated __init__.py files...\n")

    success = apply_files(
        cfg,
        generated_files,
        dry_run=dry_run,
        overwrite_manual=args.overwrite_manual,
    )

    if not success and not args.overwrite_manual:
        print(
            "\nSome manual files were skipped. "
            "Use --overwrite-manual only if you intentionally want to replace them."
        )

    print("\nDone.")
