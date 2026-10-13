# Copyright (C) 2026 Clément RACINET
# SPDX-FileCopyrightText: 2026 Clément RACINET
#
# SPDX-License-Identifier: X11
"""Filesystem and AST discovery helpers."""

from __future__ import annotations

import ast
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from py_init_tools.models import InitToolConfig


def relative_package_key(pkg_root: Path, pkg_dir: Path) -> str:
    """Return a package key relative to a package root."""
    if pkg_dir == pkg_root:
        return "."

    return pkg_dir.relative_to(pkg_root).as_posix()


def relative_module_key(pkg_root: Path, py_file: Path) -> str:
    """Return a module file key relative to a package root."""
    return py_file.relative_to(pkg_root).as_posix()


def is_reexport_allowed(cfg: InitToolConfig, pkg_root: Path, pkg_dir: Path) -> bool:
    """Return whether a package may receive generated eager re-exports.

    An entry ending with "/*" allows the directory and all its descendants.
    The entry "*" allows every package except the root.
    """
    key = relative_package_key(pkg_root, pkg_dir)

    if key in cfg.reexport_allowlist:
        return True

    if key == ".":
        return False

    if "*" in cfg.reexport_allowlist:
        return True

    return any(
        entry.endswith("/*") and (key == entry[:-2] or key.startswith(f"{entry[:-2]}/"))
        for entry in cfg.reexport_allowlist
    )


def is_public_name(name: str) -> bool:
    """Return whether a name is public by Python naming convention."""
    return not name.startswith("_")


def is_get_logger_call(node: ast.AST) -> bool:
    """Return whether an AST node calls get_logger."""
    if not isinstance(node, ast.Call):
        return False

    func = node.func

    if isinstance(func, ast.Name):
        return func.id == "get_logger"

    if isinstance(func, ast.Attribute):
        return func.attr == "get_logger"

    return False


def extract_static_string_sequence(node: ast.AST) -> list[str] | None:
    """Extract a static list or tuple of strings from an AST node."""
    if not isinstance(node, ast.List | ast.Tuple):
        return None

    names: list[str] = []

    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return None

        names.append(element.value)

    return names


def is_type_alias_assignment(node: ast.AnnAssign) -> bool:
    """Return whether an annotated assignment declares a TypeAlias."""
    annotation = node.annotation

    if isinstance(annotation, ast.Name):
        return annotation.id == "TypeAlias"

    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "TypeAlias"

    return False


def dedupe_names(names: list[str], blocklist: frozenset[str] | set[str]) -> list[str]:
    """Deduplicate names while applying a blocklist."""
    seen: set[str] = set()
    result: list[str] = []

    for name in names:
        if name in seen or name in blocklist:
            continue

        seen.add(name)
        result.append(name)

    return sorted(result)


def blocklist_for_module(
    cfg: InitToolConfig,
    pkg_root: Path,
    py_file: Path,
) -> frozenset[str]:
    """Return configured private-name blocklist for a module."""
    module_key = relative_module_key(pkg_root, py_file)
    package_key = relative_package_key(pkg_root, py_file.parent)

    return cfg.private_names_by_dir.get(package_key, frozenset()) | (
        cfg.private_names_by_module.get(module_key, frozenset())
    )


def _parse_python_module(py_file: Path) -> ast.Module | None:
    """Parse a Python module without importing it."""
    try:
        return ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        print(f"  [WARN] Cannot parse {py_file}: {exc}", file=sys.stderr)
        return None


def _extract_all_value(node: ast.AST) -> list[str] | None:
    """Extract strings from a list, tuple or concatenation of those."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _extract_all_value(node.left)
        right = _extract_all_value(node.right)

        if left is None or right is None:
            return None

        return [*left, *right]

    return extract_static_string_sequence(node)


def _is_all_name(node: ast.AST) -> bool:
    """Return whether a node is the name __all__."""
    return isinstance(node, ast.Name) and node.id == "__all__"


def _extract_all_mutation(node: ast.AST) -> list[str] | None:
    """Extract names from __all__.extend([...]) or __all__.append("x")."""
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return None

    func = node.value.func

    if not isinstance(func, ast.Attribute) or not _is_all_name(func.value):
        return None

    if len(node.value.args) != 1:
        return None

    argument = node.value.args[0]

    if func.attr == "extend":
        return _extract_all_value(argument)

    if (
        func.attr == "append"
        and isinstance(argument, ast.Constant)
        and isinstance(argument.value, str)
    ):
        return [argument.value]

    return None


def extract_all_from_node(node: ast.AST) -> list[str] | None:
    """Extract a static top-level __all__ assignment."""
    if isinstance(node, ast.Assign):
        if not any(_is_all_name(target) for target in node.targets):
            return None

        return _extract_all_value(node.value)

    if isinstance(node, ast.AnnAssign):
        if not _is_all_name(node.target) or node.value is None:
            return None

        return _extract_all_value(node.value)

    return None


def _iter_toplevel_nodes(body: list[ast.stmt]) -> list[ast.stmt]:
    """Flatten top-level statements, including if/try blocks."""
    result: list[ast.stmt] = []

    for node in body:
        result.append(node)

        if isinstance(node, ast.If):
            result.extend(_iter_toplevel_nodes(node.body))
            result.extend(_iter_toplevel_nodes(node.orelse))
        elif isinstance(node, ast.Try):
            result.extend(_iter_toplevel_nodes(node.body))

    return result


def _collect_explicit_all(
    tree: ast.Module,
    blocklist: frozenset[str],
) -> list[str] | None:
    """Collect names from every static __all__ declaration of a module."""
    names: list[str] | None = None

    for node in _iter_toplevel_nodes(tree.body):
        if isinstance(node, ast.AugAssign):
            if _is_all_name(node.target) and isinstance(node.op, ast.Add):
                added = _extract_all_value(node.value)

                if added is not None:
                    names = [*(names or []), *added]

            continue

        mutation = _extract_all_mutation(node)

        if mutation is not None:
            names = [*(names or []), *mutation]
            continue

        declared = extract_all_from_node(node)

        if declared is not None:
            names = declared

    if names is None:
        return None

    return dedupe_names(names, blocklist)


def _collect_definition_name(node: ast.AST) -> str | None:
    """Collect a public class or function name from a top-level AST node."""
    match node:
        case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name):
            if is_public_name(name):
                return name

        case ast.ClassDef(name=name):
            if is_public_name(name):
                return name

        case _:
            return None

    return None


def _collect_assignment_names(cfg: InitToolConfig, node: ast.Assign) -> list[str]:
    """Collect public constant names from an assignment node."""
    if cfg.discovery_mode != "all_public" or not cfg.export_constants:
        return []

    if is_get_logger_call(node.value):
        return []

    return [
        target.id
        for target in node.targets
        if isinstance(target, ast.Name) and is_public_name(target.id)
    ]


def _collect_annotated_assignment_name(
    cfg: InitToolConfig,
    node: ast.AnnAssign,
) -> str | None:
    """Collect a public name from an annotated assignment node."""
    if cfg.discovery_mode != "all_public":
        return None

    if not isinstance(node.target, ast.Name):
        return None

    name = node.target.id

    if is_type_alias_assignment(node):
        if cfg.export_type_aliases and is_public_name(name):
            return name

        return None

    if cfg.export_constants and is_public_name(name):
        return name

    return None


def _collect_public_names_from_body(cfg: InitToolConfig, tree: ast.Module) -> list[str]:
    """Collect public names from top-level AST nodes."""
    names: list[str] = []

    for node in tree.body:
        definition_name = _collect_definition_name(node)

        if definition_name is not None:
            names.append(definition_name)
            continue

        if isinstance(node, ast.Assign):
            names.extend(_collect_assignment_names(cfg, node))
            continue

        if isinstance(node, ast.AnnAssign):
            annotated_name = _collect_annotated_assignment_name(cfg, node)

            if annotated_name is not None:
                names.append(annotated_name)

    return names


def collect_public_names(
    cfg: InitToolConfig,
    _pkg_root: Path,
    py_file: Path,
    blocklist: frozenset[str],
) -> list[str]:
    """Collect public names from a Python module without importing it."""
    tree = _parse_python_module(py_file)

    if tree is None:
        return []

    explicit_all = _collect_explicit_all(tree, blocklist)

    if explicit_all is not None:
        return explicit_all

    if cfg.discovery_mode == "explicit_all":
        return []

    names = _collect_public_names_from_body(cfg, tree)

    return dedupe_names(names, blocklist)


def is_ignored_dir(cfg: InitToolConfig, path: Path) -> bool:
    """Return whether a directory must be ignored."""
    return any(
        part in cfg.ignored_dir_names or part.startswith(".") for part in path.parts
    )


def module_files_in_dir(pkg_dir: Path) -> list[Path]:
    """Return Python module files directly contained in a package directory."""
    return sorted(
        path
        for path in pkg_dir.iterdir()
        if path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
    )


def is_package_dir(cfg: InitToolConfig, directory: Path) -> bool:
    """Return whether a directory contains Python package-like content."""
    if not directory.is_dir() or is_ignored_dir(cfg, directory):
        return False

    has_py_file = any(
        path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
        for path in directory.iterdir()
    )

    if has_py_file:
        return True

    return any(
        is_package_dir(cfg, path)
        for path in directory.iterdir()
        if path.is_dir() and not is_ignored_dir(cfg, path)
    )


def iter_immediate_package_dirs(cfg: InitToolConfig, root: Path) -> list[Path]:
    """Return immediate package-like child directories."""
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and not is_ignored_dir(cfg, path) and is_package_dir(cfg, path)
    )


def iter_all_package_dirs(cfg: InitToolConfig, root: Path) -> list[Path]:
    """Return all package-like directories recursively, deepest first."""
    package_dirs: set[Path] = set()

    if is_package_dir(cfg, root):
        package_dirs.add(root)

    for path in root.rglob("*"):
        is_valid_package_dir = (
            path.is_dir()
            and not is_ignored_dir(cfg, path)
            and is_package_dir(cfg, path)
        )

        if is_valid_package_dir:
            package_dirs.add(path)

    return sorted(
        package_dirs,
        key=lambda path: len(path.relative_to(root).parts),
        reverse=True,
    )


def collect_test_dirs(cfg: InitToolConfig, root: Path) -> list[Path]:
    """Collect test directories containing Python files."""
    if not root.exists():
        return []

    result: list[Path] = []

    if any(path.is_file() and path.suffix == ".py" for path in root.iterdir()):
        result.append(root)

    for directory in sorted(root.rglob("*")):
        if not directory.is_dir() or is_ignored_dir(cfg, directory):
            continue

        has_python_file = any(
            path.is_file() and path.suffix == ".py" for path in directory.iterdir()
        )

        if has_python_file:
            result.append(directory)

    return sorted(set(result))


def has_immediate_subpackages(cfg: InitToolConfig, directory: Path) -> bool:
    """Return whether a directory contains immediate package-like subdirectories."""
    return bool(iter_immediate_package_dirs(cfg, directory))
