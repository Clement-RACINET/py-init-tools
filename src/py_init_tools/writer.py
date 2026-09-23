# Copyright (c) 2026 Clément RACINET
"""File writing and checking helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from py_init_tools.registry import (
    GeneratedStatus,
    Registry,
    compose_generated_content,
    extract_body,
    load_registry,
    parse_sentinel,
    register_generated_body,
    save_registry,
    validate_generated_content,
)

if TYPE_CHECKING:
    from pathlib import Path

    from py_init_tools.models import GeneratedFile, InitToolConfig


def is_generated_file(
    registry: Registry,
    *,
    project_root: Path,
    path: Path,
) -> bool:
    """Return whether a file is valid according to the registry."""
    if not path.is_file():
        return False

    content = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(project_root).as_posix()
    status = validate_generated_content(
        registry,
        relative_path=relative_path,
        content=content,
    )

    return status is GeneratedStatus.VALID


def _print_invalid_generated_status(
    relative_path: str,
    status: GeneratedStatus,
) -> None:
    """Print a generated-file validation failure."""
    label = status.value.upper().replace("-", "_")
    print(f"  [{label}] {relative_path}")


def _write_file(
    cfg: InitToolConfig,
    generated_file: GeneratedFile,
    registry: Registry,
    *,
    dry_run: bool,
    overwrite_manual: bool,
) -> tuple[bool, bool]:
    """Write one generated file and update its registry record."""
    path = generated_file.path
    body = generated_file.content
    relative_path = path.relative_to(cfg.project_root).as_posix()
    existed_before = path.exists()

    recreate = False
    repair = False
    existing_content: str | None = None

    if existed_before:
        existing_content = path.read_text(encoding="utf-8")
        sentinel = parse_sentinel(existing_content)

        if sentinel is None:
            if not overwrite_manual:
                print(f"  [SKIP-MANUAL] {relative_path}")
                return False, False

            recreate = relative_path in registry.files
        else:
            status = validate_generated_content(
                registry,
                relative_path=relative_path,
                content=existing_content,
            )

            if status is GeneratedStatus.MODIFIED:
                repair = True
            elif status is not GeneratedStatus.VALID:
                if not overwrite_manual:
                    _print_invalid_generated_status(relative_path, status)
                    return False, False

                recreate = relative_path in registry.files
    else:
        recreate = relative_path in registry.files

    generation = register_generated_body(
        registry,
        relative_path=relative_path,
        body=body,
        recreate=recreate,
        repair=repair,
    )
    complete_content = compose_generated_content(
        generation.record,
        body,
    )

    if dry_run:
        print(f"\n{'=' * 80}")
        print(f"[DRY-RUN] Would write: {relative_path}")
        print(f"{'=' * 80}")
        print(complete_content)

        # Le registre n'est jamais sauvegardé en dry-run.
        return True, False

    if existing_content == complete_content:
        print(f"  [UNCHANGED] {relative_path}")
        return True, generation.changed

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(complete_content, encoding="utf-8")

    status_label = "UPDATED" if existed_before else "NEW"
    print(
        f"  [{status_label}] {relative_path} "
        f"(v{generation.record.version}, "
        f"r{generation.record.revision})"
    )

    return True, generation.changed


def write_file(
    cfg: InitToolConfig,
    generated_file: GeneratedFile,
    *,
    dry_run: bool,
    overwrite_manual: bool,
) -> bool:
    """Write one generated file using the project registry."""
    registry = load_registry(cfg.project_root)
    success, registry_changed = _write_file(
        cfg,
        generated_file,
        registry,
        dry_run=dry_run,
        overwrite_manual=overwrite_manual,
    )

    if success and registry_changed and not dry_run:
        save_registry(cfg.project_root, registry)

    return success


def _check_file(
    cfg: InitToolConfig,
    generated_file: GeneratedFile,
    registry: Registry,
    *,
    ignore_manual: bool,
) -> bool:
    """Check one generated file against its expected body and registry."""
    path = generated_file.path
    relative_path = path.relative_to(cfg.project_root).as_posix()

    if not path.exists():
        record = registry.files.get(relative_path)

        if record is None:
            print(f"  [MISSING] {relative_path}")
        else:
            print(
                f"  [MISSING] {relative_path} "
                f"(last known: v{record.version}, r{record.revision})"
            )

        return False

    actual_content = path.read_text(encoding="utf-8")
    sentinel = parse_sentinel(actual_content)

    if sentinel is None:
        if ignore_manual:
            print(f"  [SKIP-MANUAL] {relative_path}")
            return True

        print(f"  [MANUAL] {relative_path}")
        return False

    status = validate_generated_content(
        registry,
        relative_path=relative_path,
        content=actual_content,
    )

    if status is not GeneratedStatus.VALID:
        _print_invalid_generated_status(relative_path, status)
        return False

    actual_body = extract_body(actual_content)

    if actual_body != generated_file.content:
        print(f"  [OUTDATED] {relative_path}")
        return False

    print(f"  [OK] {relative_path} (v{sentinel.version}, r{sentinel.revision})")

    return True


def check_file(
    cfg: InitToolConfig,
    generated_file: GeneratedFile,
    *,
    ignore_manual: bool,
) -> bool:
    """Check one generated file using the project registry."""
    registry = load_registry(cfg.project_root)

    return _check_file(
        cfg,
        generated_file,
        registry,
        ignore_manual=ignore_manual,
    )


def apply_files(
    cfg: InitToolConfig,
    generated_files: list[GeneratedFile],
    *,
    dry_run: bool,
    overwrite_manual: bool,
) -> bool:
    """Apply generated files and update the project registry."""
    registry = load_registry(cfg.project_root)
    success = True

    for generated_file in generated_files:
        file_success, registry_changed = _write_file(
            cfg,
            generated_file,
            registry,
            dry_run=dry_run,
            overwrite_manual=overwrite_manual,
        )
        success = file_success and success

        if file_success and registry_changed and not dry_run:
            save_registry(cfg.project_root, registry)

    return success


def check_files(
    cfg: InitToolConfig,
    generated_files: list[GeneratedFile],
    *,
    ignore_manual: bool,
) -> bool:
    """Check all generated files against the project registry."""
    registry = load_registry(cfg.project_root)
    success = True

    for generated_file in generated_files:
        file_success = _check_file(
            cfg,
            generated_file,
            registry,
            ignore_manual=ignore_manual,
        )
        success = file_success and success

    return success
