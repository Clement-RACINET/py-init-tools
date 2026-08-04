# Copyright (c) 2026 Clément RACINET
"""File writing and checking helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from py_init_tools.models import GeneratedFile, InitToolConfig


def is_generated_file(cfg: InitToolConfig, path: Path) -> bool:
    """Return whether a file contains the configured generated marker."""
    if not path.exists():
        return False

    return cfg.generated_marker in path.read_text(encoding="utf-8")


def write_file(
    cfg: InitToolConfig,
    generated_file: GeneratedFile,
    *,
    dry_run: bool,
    overwrite_manual: bool,
) -> bool:
    """Write a generated file if allowed."""
    path = generated_file.path
    content = generated_file.content
    rel = path.relative_to(cfg.project_root)

    if path.exists() and not is_generated_file(cfg, path) and not overwrite_manual:
        print(f"  [SKIP-MANUAL] {rel}")
        return False

    if dry_run:
        print(f"\n{'=' * 80}")
        print(f"[DRY-RUN] Would write: {rel}")
        print(f"{'=' * 80}")
        print(content)
        return True

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")

        if existing == content:
            print(f"  [UNCHANGED] {rel}")
            return True

        status = "UPDATED"
    else:
        status = "NEW"

    path.write_text(content, encoding="utf-8")
    print(f"  [{status}] {rel}")

    return True


def check_file(
    cfg: InitToolConfig,
    generated_file: GeneratedFile,
    *,
    ignore_manual: bool,
) -> bool:
    """Check whether a generated file is up to date."""
    path = generated_file.path
    rel = path.relative_to(cfg.project_root)

    if path.exists() and not is_generated_file(cfg, path):
        if ignore_manual:
            print(f"  [SKIP-MANUAL] {rel}")
            return True

        print(f"  [MANUAL] {rel}")
        return False

    if not path.exists():
        print(f"  [MISSING] {rel}")
        return False

    actual = path.read_text(encoding="utf-8")

    if actual != generated_file.content:
        print(f"  [OUTDATED] {rel}")
        return False

    print(f"  [OK] {rel}")

    return True


def apply_files(
    cfg: InitToolConfig,
    generated_files: list[GeneratedFile],
    *,
    dry_run: bool,
    overwrite_manual: bool,
) -> bool:
    """Apply generated files."""
    success = True

    for generated_file in generated_files:
        success = (
            write_file(
                cfg,
                generated_file,
                dry_run=dry_run,
                overwrite_manual=overwrite_manual,
            )
            and success
        )

    return success


def check_files(
    cfg: InitToolConfig,
    generated_files: list[GeneratedFile],
    *,
    ignore_manual: bool,
) -> bool:
    """Check generated files."""
    success = True

    for generated_file in generated_files:
        is_valid = check_file(
            cfg,
            generated_file,
            ignore_manual=ignore_manual,
        )
        success = is_valid and success

    return success
