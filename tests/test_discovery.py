# Copyright (c) 2026 Clément RACINET
"""Tests for filesystem and AST discovery helpers."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from py_init_tools.config import load_config
from py_init_tools.discovery import (
    blocklist_for_module,
    collect_public_names,
    collect_test_dirs,
    dedupe_names,
    extract_static_string_sequence,
    has_immediate_subpackages,
    is_get_logger_call,
    is_ignored_dir,
    is_package_dir,
    is_public_name,
    is_reexport_allowed,
    iter_all_package_dirs,
    iter_immediate_package_dirs,
    module_files_in_dir,
    relative_module_key,
    relative_package_key,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from py_init_tools.models import InitToolConfig


def make_config(  # noqa: PLR0913
    tmp_path: Path,
    *,
    discovery_mode: str = "classes_functions",
    export_constants: bool = False,
    export_type_aliases: bool = False,
    generate_root_reexports: bool = False,
    reexport_allowlist: list[str] | None = None,
    ignored_dir_names: list[str] | None = None,
    private_names_by_module: dict[str, list[str]] | None = None,
    private_names_by_dir: dict[str, list[str]] | None = None,
) -> InitToolConfig:
    """Create a test configuration through pyproject.toml loading."""
    pyproject = tmp_path / "pyproject.toml"

    lines = [
        "[tool.py-init-tools]",
        'package_roots = ["src/example_pkg"]',
        'test_roots = ["tests"]',
        f'discovery_mode = "{discovery_mode}"',
        f"export_constants = {str(export_constants).lower()}",
        f"export_type_aliases = {str(export_type_aliases).lower()}",
        f"generate_root_reexports = {str(generate_root_reexports).lower()}",
    ]

    if reexport_allowlist is not None:
        quoted_values = ", ".join(f'"{value}"' for value in reexport_allowlist)
        lines.append(f"reexport_allowlist = [{quoted_values}]")

    if ignored_dir_names is not None:
        quoted_values = ", ".join(f'"{value}"' for value in ignored_dir_names)
        lines.append(f"ignored_dir_names = [{quoted_values}]")

    if private_names_by_module is not None:
        lines.append("")
        lines.append("[tool.py-init-tools.private_names_by_module]")
        for key, values in private_names_by_module.items():
            quoted_values = ", ".join(f'"{value}"' for value in values)
            lines.append(f'"{key}" = [{quoted_values}]')

    if private_names_by_dir is not None:
        lines.append("")
        lines.append("[tool.py-init-tools.private_names_by_dir]")
        for key, values in private_names_by_dir.items():
            quoted_values = ", ".join(f'"{value}"' for value in values)
            lines.append(f'"{key}" = [{quoted_values}]')

    pyproject.write_text("\n".join(lines), encoding="utf-8")

    return load_config(
        cwd=tmp_path,
        package_roots=(),
        test_roots=(),
    )


def write_module(path: Path, content: str) -> Path:
    """Write a Python module for discovery tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_relative_package_key_returns_dot_for_root(tmp_path: Path) -> None:
    """Return dot for the package root itself."""
    pkg_root = tmp_path / "src" / "example_pkg"

    assert relative_package_key(pkg_root, pkg_root) == "."


def test_relative_package_key_returns_posix_subpath(tmp_path: Path) -> None:
    """Return a POSIX relative package key."""
    pkg_root = tmp_path / "src" / "example_pkg"
    pkg_dir = pkg_root / "subpkg" / "nested"

    assert relative_package_key(pkg_root, pkg_dir) == "subpkg/nested"


def test_relative_module_key_returns_posix_file_path(tmp_path: Path) -> None:
    """Return a POSIX relative module key."""
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = pkg_root / "subpkg" / "module.py"

    assert relative_module_key(pkg_root, py_file) == "subpkg/module.py"


def test_is_public_name_rejects_private_names() -> None:
    """Detect public names by naming convention."""
    assert is_public_name("PublicName") is True
    assert is_public_name("public_name") is True
    assert is_public_name("_PrivateName") is False
    assert is_public_name("__dunder__") is False


def test_dedupe_names_sorts_deduplicates_and_applies_blocklist() -> None:
    """Deduplicate names while excluding blocklisted names."""
    names = ["Beta", "Alpha", "Beta", "Internal", "Gamma"]

    assert dedupe_names(names, frozenset({"Internal"})) == [
        "Alpha",
        "Beta",
        "Gamma",
    ]


def test_extract_static_string_sequence_accepts_list() -> None:
    """Extract a static string list from AST."""

    node = ast.parse('__all__ = ["Alpha", "Beta"]').body[0]

    assert isinstance(node, ast.Assign)
    assert extract_static_string_sequence(node.value) == ["Alpha", "Beta"]


def test_extract_static_string_sequence_rejects_dynamic_values() -> None:
    """Reject non-static string sequences."""

    node = ast.parse('__all__ = ["Alpha", dynamic_name]').body[0]

    assert isinstance(node, ast.Assign)
    assert extract_static_string_sequence(node.value) is None


def test_is_get_logger_call_detects_direct_call() -> None:
    """Detect a direct get_logger call."""

    node = ast.parse("LOGGER = get_logger(__name__)").body[0]

    assert isinstance(node, ast.Assign)
    assert is_get_logger_call(node.value) is True


def test_is_get_logger_call_detects_attribute_call() -> None:
    """Detect a get_logger attribute call."""

    node = ast.parse("LOGGER = logging.get_logger(__name__)").body[0]

    assert isinstance(node, ast.Assign)
    assert is_get_logger_call(node.value) is True


def test_collect_public_names_prefers_explicit_all(tmp_path: Path) -> None:
    """Prefer explicit static __all__ over discovered definitions."""
    cfg = make_config(tmp_path)
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
__all__ = ["ExportedClass", "exported_function"]

class ExportedClass:
    pass

def exported_function() -> None:
    pass

def ignored_function() -> None:
    pass
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == [
        "ExportedClass",
        "exported_function",
    ]


def test_collect_public_names_explicit_all_applies_blocklist(tmp_path: Path) -> None:
    """Apply blocklist to explicit __all__ names."""
    cfg = make_config(tmp_path)
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
__all__ = ["Allowed", "Blocked"]

class Allowed:
    pass

class Blocked:
    pass
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset({"Blocked"})) == [
        "Allowed"
    ]


def test_collect_public_names_explicit_all_mode_returns_empty_without_all(
    tmp_path: Path,
) -> None:
    """Return no names in explicit_all mode when __all__ is missing."""
    cfg = make_config(tmp_path, discovery_mode="explicit_all")
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
class PublicClass:
    pass

def public_function() -> None:
    pass
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == []


def test_collect_public_names_classes_functions_mode(tmp_path: Path) -> None:
    """Collect public classes and functions by default."""
    cfg = make_config(tmp_path, discovery_mode="classes_functions")
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
class PublicClass:
    pass

class _PrivateClass:
    pass

def public_function() -> None:
    pass

async def public_async_function() -> None:
    pass

def _private_function() -> None:
    pass

PUBLIC_CONSTANT = "ignored"
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == [
        "PublicClass",
        "public_async_function",
        "public_function",
    ]


def test_collect_public_names_all_public_can_include_constants(tmp_path: Path) -> None:
    """Collect constants in all_public mode when enabled."""
    cfg = make_config(
        tmp_path,
        discovery_mode="all_public",
        export_constants=True,
    )
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
class PublicClass:
    pass

def public_function() -> None:
    pass

PUBLIC_CONSTANT = "included"
_private_constant = "ignored"
LOGGER = get_logger(__name__)
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == [
        "PUBLIC_CONSTANT",
        "PublicClass",
        "public_function",
    ]


def test_collect_public_names_all_public_ignores_constants_when_disabled(
    tmp_path: Path,
) -> None:
    """Ignore constants in all_public mode when constant export is disabled."""
    cfg = make_config(
        tmp_path,
        discovery_mode="all_public",
        export_constants=False,
    )
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
PUBLIC_CONSTANT = "ignored"

class PublicClass:
    pass
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == ["PublicClass"]


def test_collect_public_names_all_public_can_include_type_aliases(
    tmp_path: Path,
) -> None:
    """Collect TypeAlias assignments in all_public mode when enabled."""
    cfg = make_config(
        tmp_path,
        discovery_mode="all_public",
        export_type_aliases=True,
    )
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
from typing import TypeAlias

PublicAlias: TypeAlias = str
_PrivateAlias: TypeAlias = str
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == ["PublicAlias"]


def test_collect_public_names_all_public_can_include_annotated_constants(
    tmp_path: Path,
) -> None:
    """Collect annotated constants in all_public mode when enabled."""
    cfg = make_config(
        tmp_path,
        discovery_mode="all_public",
        export_constants=True,
    )
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "module.py",
        """
PUBLIC_CONSTANT: str = "included"
_private_constant: str = "ignored"
""",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == [
        "PUBLIC_CONSTANT"
    ]


def test_collect_public_names_returns_empty_for_invalid_python(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return an empty list and warn when a module cannot be parsed."""
    cfg = make_config(tmp_path)
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = write_module(
        pkg_root / "broken.py",
        "def broken(:\n",
    )

    assert collect_public_names(cfg, pkg_root, py_file, frozenset()) == []

    captured = capsys.readouterr()

    assert "[WARN] Cannot parse" in captured.err


def test_blocklist_for_module_combines_module_and_directory_rules(
    tmp_path: Path,
) -> None:
    """Combine module-level and directory-level private-name blocklists."""
    cfg = make_config(
        tmp_path,
        private_names_by_module={
            "subpkg/module.py": ["ModulePrivate"],
        },
        private_names_by_dir={
            "subpkg": ["DirectoryPrivate"],
        },
    )
    pkg_root = tmp_path / "src" / "example_pkg"
    py_file = pkg_root / "subpkg" / "module.py"

    assert blocklist_for_module(cfg, pkg_root, py_file) == frozenset(
        {"DirectoryPrivate", "ModulePrivate"}
    )


def test_is_reexport_allowed_uses_relative_package_key(tmp_path: Path) -> None:
    """Allow re-export only for configured package keys."""
    cfg = make_config(
        tmp_path,
        reexport_allowlist=[".", "subpkg"],
    )
    pkg_root = tmp_path / "src" / "example_pkg"

    assert is_reexport_allowed(cfg, pkg_root, pkg_root) is True
    assert is_reexport_allowed(cfg, pkg_root, pkg_root / "subpkg") is True
    assert is_reexport_allowed(cfg, pkg_root, pkg_root / "other") is False


def test_is_ignored_dir_matches_configured_and_hidden_parts(tmp_path: Path) -> None:
    """Ignore configured directory names and hidden directories."""
    cfg = make_config(
        tmp_path,
        ignored_dir_names=["__pycache__", "build"],
    )

    assert is_ignored_dir(cfg, tmp_path / "src" / "__pycache__") is True
    assert is_ignored_dir(cfg, tmp_path / "src" / "build") is True
    assert is_ignored_dir(cfg, tmp_path / "src" / ".hidden") is True
    assert is_ignored_dir(cfg, tmp_path / "src" / "package") is False


def test_module_files_in_dir_returns_python_modules_without_init(
    tmp_path: Path,
) -> None:
    """Return direct Python module files except __init__.py."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "a.py").write_text("", encoding="utf-8")
    (pkg_dir / "b.py").write_text("", encoding="utf-8")
    (pkg_dir / "README.md").write_text("", encoding="utf-8")

    assert module_files_in_dir(pkg_dir) == [
        pkg_dir / "a.py",
        pkg_dir / "b.py",
    ]


def test_is_package_dir_detects_directory_with_python_module(tmp_path: Path) -> None:
    """Detect a package-like directory containing a Python module."""
    cfg = make_config(tmp_path)
    directory = tmp_path / "pkg"
    write_module(directory / "module.py", "")

    assert is_package_dir(cfg, directory) is True


def test_is_package_dir_detects_directory_with_nested_package(tmp_path: Path) -> None:
    """Detect a package-like directory through nested Python content."""
    cfg = make_config(tmp_path)
    directory = tmp_path / "pkg"
    write_module(directory / "subpkg" / "module.py", "")

    assert is_package_dir(cfg, directory) is True


def test_is_package_dir_rejects_empty_directory(tmp_path: Path) -> None:
    """Reject a directory without package-like Python content."""
    cfg = make_config(tmp_path)
    directory = tmp_path / "pkg"
    directory.mkdir()

    assert is_package_dir(cfg, directory) is False


def test_iter_immediate_package_dirs_returns_package_like_children(
    tmp_path: Path,
) -> None:
    """Return immediate package-like child directories."""
    cfg = make_config(tmp_path)
    root = tmp_path / "src"

    write_module(root / "pkg_a" / "module.py", "")
    write_module(root / "pkg_b" / "module.py", "")
    (root / "not_a_pkg").mkdir(parents=True)

    assert iter_immediate_package_dirs(cfg, root) == [
        root / "pkg_a",
        root / "pkg_b",
    ]


def test_iter_all_package_dirs_returns_deepest_first(tmp_path: Path) -> None:
    """Return package-like directories recursively, deepest first."""
    cfg = make_config(tmp_path)
    root = tmp_path / "src" / "example_pkg"

    write_module(root / "module.py", "")
    write_module(root / "subpkg" / "module.py", "")
    write_module(root / "subpkg" / "nested" / "module.py", "")

    assert iter_all_package_dirs(cfg, root) == [
        root / "subpkg" / "nested",
        root / "subpkg",
        root,
    ]


def test_collect_test_dirs_returns_directories_containing_python_files(
    tmp_path: Path,
) -> None:
    """Collect test directories containing Python files."""
    cfg = make_config(tmp_path)
    root = tmp_path / "tests"

    write_module(root / "test_root.py", "")
    write_module(root / "unit" / "test_unit.py", "")
    write_module(root / "integration" / "test_integration.py", "")
    (root / "data").mkdir()

    assert collect_test_dirs(cfg, root) == [
        root,
        root / "integration",
        root / "unit",
    ]


def test_collect_test_dirs_returns_empty_for_missing_root(tmp_path: Path) -> None:
    """Return no test directories when the root does not exist."""
    cfg = make_config(tmp_path)

    assert collect_test_dirs(cfg, tmp_path / "missing_tests") == []


def test_has_immediate_subpackages_detects_package_like_children(
    tmp_path: Path,
) -> None:
    """Detect immediate package-like subdirectories."""
    cfg = make_config(tmp_path)
    directory = tmp_path / "pkg"

    write_module(directory / "subpkg" / "module.py", "")

    assert has_immediate_subpackages(cfg, directory) is True
