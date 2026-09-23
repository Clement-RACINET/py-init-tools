# Copyright (c) 2026 Clément RACINET
"""Shared data models for py-init-tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from py_init_tools.constants import DEFAULT_GENERATED_MARKER

if TYPE_CHECKING:
    from pathlib import Path

DiscoveryMode = Literal["explicit_all", "classes_functions", "all_public"]

VALID_DISCOVERY_MODES: frozenset[str] = frozenset(
    {"explicit_all", "classes_functions", "all_public"}
)


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """Generated file candidate.

    Attributes:
        path: Destination path.
        content: Expected generated content.

    """

    path: Path
    content: str


@dataclass(frozen=True, slots=True)
class InitToolConfig:
    """Configuration for __init__.py generation.

    Attributes:
        project_root: Root directory of the project being processed.
        package_roots: Python package root directories.
        test_roots: Test root directories.
        package_version: Optional package version written in root packages.
        package_description: Description used in root package docstrings.
        generated_marker: Stable marker used to identify generated files.
        generate_root_reexports: Whether root packages can re-export public names.
        reexport_allowlist: Package directories allowed to receive eager re-exports.
        discovery_mode: Public symbol discovery strategy.
        export_constants: Whether constants can be exported in all_public mode.
        export_type_aliases: Whether TypeAlias declarations can be exported.
        private_names_by_dir: Public-name blocklist by package-relative directory.
        private_names_by_module: Public-name blocklist by package-relative module path.
        flat_subdirs: Package directories forced to be treated as flat packages.
        ignored_dir_names: Directory names ignored during scanning.

    """

    project_root: Path
    package_roots: tuple[Path, ...]
    test_roots: tuple[Path, ...] = ()

    package_version: str | None = None
    package_description: str = "Python package."
    generated_marker: str = DEFAULT_GENERATED_MARKER

    generate_root_reexports: bool = False
    reexport_allowlist: frozenset[str] = frozenset()
    discovery_mode: DiscoveryMode = "classes_functions"

    export_constants: bool = False
    export_type_aliases: bool = False

    private_names_by_dir: dict[str, frozenset[str]] = field(default_factory=dict)
    private_names_by_module: dict[str, frozenset[str]] = field(default_factory=dict)
    flat_subdirs: frozenset[str] = frozenset()

    ignored_dir_names: frozenset[str] = frozenset(
        {
            "__pycache__",
            ".git",
            ".hg",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "venv",
            "build",
            "dist",
        }
    )
