# Copyright (C) 2026 Clément RACINET
# SPDX-FileCopyrightText: 2026 Clément RACINET
#
# SPDX-License-Identifier: X11
"""Shared data models for py-init-tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from py_init_tools.constants import (
    DEFAULT_GENERATED_MARKER,
    DEFAULT_SENTINEL_SEARCH_LINES,
)

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
        package_description: Root package docstring description.
        generated_marker: Human-readable generated-file marker.
        sentinel_search_lines: Number of initial lines searched for a sentinel.
        generate_root_reexports: Whether root packages may re-export names.
        reexport_allowlist: Package-relative directories allowed to re-export.
        discovery_mode: Public-symbol discovery strategy.
        export_constants: Whether public constants can be exported.
        export_type_aliases: Whether public type aliases can be exported.
        flat_subdirs: Directories forced to behave as flat packages.
        private_names_by_dir: Public-name exclusions by directory.
        private_names_by_module: Public-name exclusions by module.
        ignored_dir_names: Directory names ignored during discovery.

    """

    project_root: Path
    package_roots: tuple[Path, ...]
    test_roots: tuple[Path, ...]

    package_version: str | None = None
    package_description: str = "Python package."
    generated_marker: str = DEFAULT_GENERATED_MARKER
    sentinel_search_lines: int = DEFAULT_SENTINEL_SEARCH_LINES

    generate_root_reexports: bool = False
    reexport_allowlist: frozenset[str] = field(default_factory=frozenset)

    discovery_mode: DiscoveryMode = "classes_functions"
    export_constants: bool = False
    export_type_aliases: bool = False

    flat_subdirs: frozenset[str] = field(default_factory=frozenset)
    private_names_by_dir: dict[str, frozenset[str]] = field(
        default_factory=dict,
    )
    private_names_by_module: dict[str, frozenset[str]] = field(
        default_factory=dict,
    )
    ignored_dir_names: frozenset[str] = field(default_factory=frozenset)
