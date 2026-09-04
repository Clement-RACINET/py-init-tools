# Copyright (c) 2026 Clément RACINET
"""Generated __init__.py rendering logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from py_init_tools.discovery import (
    blocklist_for_module,
    collect_public_names,
    collect_test_dirs,
    has_immediate_subpackages,
    is_reexport_allowed,
    iter_all_package_dirs,
    iter_immediate_package_dirs,
    module_files_in_dir,
    relative_package_key,
)
from py_init_tools.models import GeneratedFile

if TYPE_CHECKING:
    from pathlib import Path

    from py_init_tools.models import InitToolConfig


MAX_SINGLE_LINE_IMPORT_LENGTH = 88


def ruff_all_name_sort_key(name: str) -> tuple[int, str]:
    """Return a Ruff-compatible sort key for __all__ names.

    Ruff RUF022 groups names broadly as constants, classes, then functions or
    lowercase names, while preserving case-sensitive ordering inside groups.
    """
    if name.upper() == name:
        group = 0
    elif name[:1].islower():
        group = 2
    else:
        group = 1

    return group, name


def ruff_import_name_sort_key(name: str) -> tuple[int, str]:
    """Return a Ruff/isort-compatible sort key for imported names.

    Import member sorting groups names similarly to __all__, but sorts
    case-insensitively inside each group.
    """
    if name.upper() == name:
        group = 0
    elif name[:1].islower():
        group = 2
    else:
        group = 1

    return group, name.lower()


@dataclass(frozen=True, slots=True)
class InitRenderSpec:
    """Specification used to render a generated __init__.py file."""

    generated_marker: str
    path_comment: str
    docstring: str
    imports_block: str
    all_names: list[str]
    version: str | None = None


def dedupe_import_entries(
    entries: list[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    """Remove duplicate public names across import entries."""
    seen: set[str] = set()
    deduped: list[tuple[str, list[str]]] = []

    for module, names in entries:
        unique_names = [name for name in names if name not in seen]
        seen.update(unique_names)

        if unique_names:
            deduped.append((module, unique_names))

    return deduped


def format_import(module: str, names: list[str]) -> str:
    """Format a relative import statement."""
    if not names:
        return ""

    sorted_names = sorted(names, key=ruff_import_name_sort_key)
    single_line = f"from {module} import {', '.join(sorted_names)}"

    if len(single_line) <= MAX_SINGLE_LINE_IMPORT_LENGTH:
        return single_line

    lines = [f"from {module} import ("]
    lines.extend(f"    {name}," for name in sorted_names)
    lines.append(")")

    return "\n".join(lines)


def format_all(names: list[str]) -> str:
    """Format names for __all__."""
    unique_names = sorted(set(names), key=ruff_all_name_sort_key)

    if not unique_names:
        return ""

    return "\n    ".join(f'"{name}",' for name in unique_names)


def render_init_file(spec: InitRenderSpec) -> str:
    """Render a generated __init__.py file."""
    version_block = ""

    if spec.version is not None:
        version_block = f'\n__version__ = "{spec.version}"\n'

    all_block = format_all(spec.all_names)
    formatted_all = f"\n    {all_block}\n" if all_block else "\n"

    return f'''\
{spec.path_comment}
"""{spec.docstring}

{spec.generated_marker} — do not edit manually.
"""

from __future__ import annotations

{spec.imports_block}

__all__ = [{formatted_all}]
{version_block}'''


def entries_from_flat_package(
    cfg: InitToolConfig,
    pkg_root: Path,
    pkg_dir: Path,
) -> list[tuple[str, list[str]]]:
    """Build import entries for a flat package."""
    entries: list[tuple[str, list[str]]] = []

    for py_file in module_files_in_dir(pkg_dir):
        blocklist = blocklist_for_module(cfg, pkg_root, py_file)
        names = collect_public_names(cfg, pkg_root, py_file, blocklist)

        if names:
            entries.append((f".{py_file.stem}", names))

    return entries


def collect_generated_package_public_names(
    cfg: InitToolConfig,
    pkg_root: Path,
    pkg_dir: Path,
) -> list[str]:
    """Collect public names that the generated package initializer exports."""
    rel_key = relative_package_key(pkg_root, pkg_dir)

    if not is_reexport_allowed(cfg, pkg_root, pkg_dir):
        return []

    is_forced_flat = rel_key in cfg.flat_subdirs

    if has_immediate_subpackages(cfg, pkg_dir) and not is_forced_flat:
        entries = entries_from_nested_package(cfg, pkg_root, pkg_dir)
    else:
        entries = entries_from_flat_package(cfg, pkg_root, pkg_dir)

    _imports_block, all_names = entries_to_imports_and_all(entries)

    return sorted(set(all_names))


def entries_from_nested_package(
    cfg: InitToolConfig,
    pkg_root: Path,
    pkg_dir: Path,
) -> list[tuple[str, list[str]]]:
    """Build import entries for a package with immediate subpackages."""
    entries: list[tuple[str, list[str]]] = []

    for sub_dir in iter_immediate_package_dirs(cfg, pkg_dir):
        names = collect_generated_package_public_names(cfg, pkg_root, sub_dir)

        if names:
            entries.append((f".{sub_dir.name}", names))

    for py_file in module_files_in_dir(pkg_dir):
        blocklist = blocklist_for_module(cfg, pkg_root, py_file)
        names = collect_public_names(cfg, pkg_root, py_file, blocklist)

        if names:
            entries.append((f".{py_file.stem}", names))

    return entries


def entries_to_imports_and_all(
    entries: list[tuple[str, list[str]]],
) -> tuple[str, list[str]]:
    """Convert import entries into an import block and __all__ names."""
    deduped = sorted(dedupe_import_entries(entries), key=lambda entry: entry[0])

    import_blocks: list[str] = []
    all_names: list[str] = []

    for module, names in deduped:
        import_block = format_import(module, names)

        if import_block:
            import_blocks.append(import_block)

        all_names.extend(names)

    imports_block = "\n".join(import_blocks) if import_blocks else "# No public symbols"

    return imports_block, all_names


def gen_lightweight_init(
    cfg: InitToolConfig,
    pkg_root: Path,
    pkg_dir: Path,
) -> str:
    """Generate a lightweight __init__.py without eager imports."""
    rel_key = relative_package_key(pkg_root, pkg_dir)
    path_label = (
        f"{pkg_root.name}/__init__.py"
        if rel_key == "."
        else f"{pkg_root.name}/{rel_key}/__init__.py"
    )
    package_label = pkg_root.name if rel_key == "." else rel_key

    if rel_key == ".":
        all_names = ["__version__"] if cfg.package_version is not None else []

        return render_init_file(
            InitRenderSpec(
                generated_marker=cfg.generated_marker,
                path_comment=f"# {path_label}",
                docstring=cfg.package_description,
                imports_block="# Root re-exports are disabled by configuration",
                all_names=all_names,
                version=cfg.package_version,
            )
        )

    return render_init_file(
        InitRenderSpec(
            generated_marker=cfg.generated_marker,
            path_comment=f"# {path_label}",
            docstring=(
                f"Lightweight initializer for the {package_label} package.\n\n"
                "This file intentionally avoids eager public re-exports to prevent "
                "circular imports and expensive import side effects."
            ),
            imports_block="# No eager public re-exports",
            all_names=[],
        )
    )


def gen_subpkg_init(cfg: InitToolConfig, pkg_root: Path, pkg_dir: Path) -> str:
    """Generate __init__.py content for an allowlisted flat package."""
    rel = pkg_dir.relative_to(pkg_root).as_posix()
    entries = entries_from_flat_package(cfg, pkg_root, pkg_dir)
    imports_block, all_names = entries_to_imports_and_all(entries)

    return render_init_file(
        InitRenderSpec(
            generated_marker=cfg.generated_marker,
            path_comment=f"# {pkg_root.name}/{rel}/__init__.py",
            docstring=f"Public re-exports for the {rel} package.",
            imports_block=imports_block,
            all_names=all_names,
        )
    )


def gen_nested_subpkg_init(cfg: InitToolConfig, pkg_root: Path, pkg_dir: Path) -> str:
    """Generate __init__.py content for an allowlisted nested package."""
    rel = pkg_dir.relative_to(pkg_root).as_posix()
    entries = entries_from_nested_package(cfg, pkg_root, pkg_dir)
    imports_block, all_names = entries_to_imports_and_all(entries)

    return render_init_file(
        InitRenderSpec(
            generated_marker=cfg.generated_marker,
            path_comment=f"# {pkg_root.name}/{rel}/__init__.py",
            docstring=f"Public re-exports for the {rel} package.",
            imports_block=imports_block,
            all_names=all_names,
        )
    )


def gen_package_init(cfg: InitToolConfig, pkg_root: Path) -> str:
    """Generate top-level package __init__.py content."""
    if not cfg.generate_root_reexports:
        return gen_lightweight_init(cfg, pkg_root, pkg_root)

    entries = entries_from_nested_package(cfg, pkg_root, pkg_root)
    imports_block, all_names = entries_to_imports_and_all(entries)

    if cfg.package_version is not None:
        all_names = [*all_names, "__version__"]

    return render_init_file(
        InitRenderSpec(
            generated_marker=cfg.generated_marker,
            path_comment=f"# {pkg_root.name}/__init__.py",
            docstring=cfg.package_description,
            imports_block=imports_block,
            all_names=all_names,
            version=cfg.package_version,
        )
    )


def gen_test_init(cfg: InitToolConfig, directory: Path) -> str:
    """Generate a minimal test package marker."""
    rel = directory.relative_to(cfg.project_root).as_posix()

    return f"""\
# {rel}/__init__.py
# Package marker — do not add imports here.
# {cfg.generated_marker} — do not edit manually.
"""


def generate_package_files_for_root(
    cfg: InitToolConfig,
    pkg_root: Path,
) -> list[GeneratedFile]:
    """Generate all package file candidates for one package root."""
    generated: list[GeneratedFile] = []

    for pkg_dir in iter_all_package_dirs(cfg, pkg_root):
        rel_key = relative_package_key(pkg_root, pkg_dir)

        if rel_key == ".":
            content = gen_package_init(cfg, pkg_root)
        elif not is_reexport_allowed(cfg, pkg_root, pkg_dir):
            content = gen_lightweight_init(cfg, pkg_root, pkg_dir)
        else:
            is_forced_flat = rel_key in cfg.flat_subdirs

            if has_immediate_subpackages(cfg, pkg_dir) and not is_forced_flat:
                content = gen_nested_subpkg_init(cfg, pkg_root, pkg_dir)
            else:
                content = gen_subpkg_init(cfg, pkg_root, pkg_dir)

        generated.append(GeneratedFile(path=pkg_dir / "__init__.py", content=content))

    return generated


def generate_package_files(cfg: InitToolConfig) -> list[GeneratedFile]:
    """Generate package file candidates for all configured package roots."""
    generated: list[GeneratedFile] = []

    for pkg_root in cfg.package_roots:
        if not pkg_root.exists():
            print(f"  [WARN] Package root does not exist: {pkg_root}")
            continue

        generated.extend(generate_package_files_for_root(cfg, pkg_root))

    return generated


def generate_test_files(cfg: InitToolConfig) -> list[GeneratedFile]:
    """Generate test marker file candidates."""
    generated: list[GeneratedFile] = []

    for test_root in cfg.test_roots:
        generated.extend(
            GeneratedFile(
                path=directory / "__init__.py",
                content=gen_test_init(cfg, directory),
            )
            for directory in collect_test_dirs(cfg, test_root)
        )

    return generated


def generate_files(cfg: InitToolConfig, *, include_tests: bool) -> list[GeneratedFile]:
    """Generate all file candidates."""
    package_files = generate_package_files(cfg)
    test_files = generate_test_files(cfg) if include_tests else []

    return [*package_files, *test_files]
