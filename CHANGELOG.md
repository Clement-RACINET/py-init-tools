# Changelog

All notable changes to this project will be documented in this file.

This project follows the spirit of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and uses semantic versioning while the public API stabilizes.

## [0.2.2] - 2026-08-04

### Fixed

- Sort generated relative import blocks by module path to avoid Ruff `I001` in nested packages.

### Added

- Add regression tests for nested package import block ordering.

## [0.2.2] - 2026-08-04

### Added

- Add Ruff-compatible sorting for generated import members and `__all__` names.
- Add tests for Ruff-compatible sorting of generated imports and `__all__`.

## [0.2.0] - 2026-08-04

### Added

- Add comprehensive Pytest coverage for the command-line interface.
- Add tests for CLI parsing, dry-run mode, write mode, check mode, skipped test generation, and manual-file skip reporting.
- Add configuration loading tests for defaults, `pyproject.toml` values, CLI root overrides, and invalid value handling.
- Add filesystem and AST discovery tests.
- Add tests for public symbol discovery modes:
  - `explicit_all`
  - `classes_functions`
  - `all_public`
- Add tests for generated `__init__.py` rendering.
- Add tests for lightweight initializers, root package initializers, allowlisted re-export initializers, and test package markers.
- Add tests for file writing and checking helpers.
- Add tests for manual-file protection, dry-run output, unchanged files, updated files, missing files, outdated files, and generated marker detection.
- Add targeted coverage configuration for `py_init_tools`.

## [0.1.0] - 2026-08-04

### Added

- Add initial `pyinit` command-line interface.
- Add dry-run mode by default to preview generated `__init__.py` files without writing changes.
- Add `--write` mode to generate and update managed `__init__.py` files.
- Add `--check` mode for CI-friendly validation of generated files.
- Add support for package roots and test roots.
- Add configuration loading from `[tool.py-init-tools]` in `pyproject.toml`.
- Add support for CLI overrides of configured package roots and test roots.
- Add generated-file marker handling to avoid overwriting manual `__init__.py` files by default.
- Add optional manual-file overwrite through `--overwrite-manual`.
- Add optional manual-file ignoring in check mode through `--ignore-manual-in-check`.
- Add support for skipping test package processing through `--skip-tests`.
- Add configurable symbol discovery modes:
  - `explicit_all`
  - `classes_functions`
  - `all_public`
- Add support for root package re-exports.
- Add support for re-export allowlists.
- Add support for flat subdirectory handling.
- Add support for private-name filtering by module and by directory.
- Add support for exporting constants and type aliases through configuration.
- Add file generation, checking and writing workflows.
- Add Pixi-based development environment and tasks.
- Add Ruff configuration for linting and formatting.
- Add BasedPyright configuration for strict typing.
- Add Pytest-based test setup.
