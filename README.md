# py-init-tools

Safe audit and generation of Python package `__init__.py` files.

`py-init-tools` is a small development utility that creates, updates, and checks
Python package initializers without importing the target project's code.

It is conservative by default:

- dry-run unless `--write` is passed;
- manual files are not overwritten by default;
- generated files are tracked through a versioned sentinel and a JSON registry;
- public re-exports are enabled only for allowlisted packages;
- Python modules are analyzed statically with `ast`.

---

## Features

- Generate missing package `__init__.py` files.
- Generate lightweight initializers without eager imports.
- Generate public re-exports for explicitly allowlisted packages.
- Generate minimal test package markers.
- Discover public classes, functions, constants, and type aliases.
- Respect explicit static `__all__` declarations.
- Protect manually maintained files.
- Detect modified, outdated, deleted, or recreated generated files.
- Track file versions, revisions, hashes, and generation history.
- Configure projects through `pyproject.toml`.

---

## Usage

### Preview changes

Running `pyinit` without `--write` or `--check` performs a dry-run:

```bash
pyinit
```

Paths can also be provided explicitly:

```bash
pyinit --package-root src/my_package --test-root tests
```

### Write generated files

```bash
pyinit --write
```

### Check generated files

This exits with a non-zero status when generated files are missing, modified,
outdated, or inconsistent with the registry:

```bash
pyinit --check
```

It is suitable for CI pipelines.

### Skip test package markers

```bash
pyinit --write --skip-tests
```

### Overwrite manual or unrecognized files

Manual files are protected by default. To replace them intentionally:

```bash
pyinit --write --overwrite-manual
```

Use this option for the first migration from an older marker-based version of
`py-init-tools`.

### Ignore manual files during checks

```bash
pyinit --check --ignore-manual-in-check
```

This applies only to files without a generated sentinel. Invalid or inconsistent
generated files still fail validation.

### Show all options

```bash
pyinit --help
```

---

## Configuration

Projects can configure the tool in `pyproject.toml`:

```toml
[tool.py-init-tools]
package_roots = ["src/my_package"]
test_roots = ["tests"]

package_version = "0.2.2"
package_description = "My Python package."

generate_root_reexports = false

reexport_allowlist = [
  "api",
  "services/public"
]

discovery_mode = "classes_functions"
export_constants = false
export_type_aliases = false

flat_subdirs = []
```

Once configured, commands can be kept short:

```bash
pyinit
pyinit --write
pyinit --check
```

Command-line `--package-root` and `--test-root` values override their
corresponding configuration values.

### Configuration reference

| **Option**                | **Type**               | **Description**                                              |
| ------------------------- | ---------------------- | ------------------------------------------------------------ |
| `package_roots`           | `list[str]`            | Package roots to process.                                    |
| `test_roots`              | `list[str]`            | Test roots where package markers are generated.              |
| `package_version`         | `str \| null`          | Optional `__version__` written in root packages.             |
| `package_description`     | `str`                  | Root package docstring description.                          |
| `generated_marker`        | `str`                  | Human-readable notice included in generated files.           |
| `generate_root_reexports` | `bool`                 | Enable public re-exports from root packages.                 |
| `reexport_allowlist`      | `list[str]`            | Package-relative directories allowed to re-export symbols.   |
| `discovery_mode`          | `str`                  | Symbol discovery mode.                                       |
| `export_constants`        | `bool`                 | Export public constants in `all_public` mode.                |
| `export_type_aliases`     | `bool`                 | Export public `TypeAlias` declarations in `all_public` mode. |
| `flat_subdirs`            | `list[str]`            | Nested directories forced to behave as flat packages.        |
| `private_names_by_dir`    | `dict[str, list[str]]` | Names excluded by package-relative directory.                |
| `private_names_by_module` | `dict[str, list[str]]` | Names excluded by package-relative module.                   |
| `ignored_dir_names`       | `list[str]`            | Directory names ignored during discovery.                    |

`generated_marker` is only the human-readable notice. Generated-file identity
is managed separately through the sentinel and registry.

---

## Symbol discovery

`py-init-tools` never imports target modules. It parses their source code with
Python's `ast` module.

Three discovery modes are available.

### `explicit_all`

Only static module-level `__all__` declarations are used:

```python
__all__ = ["ApiClient", "ApiResponse"]
```

Lists, tuples, regular assignments, and annotated assignments are supported.

### `classes_functions`

This is the default mode.

An explicit `__all__` takes priority. Otherwise, public top-level classes and
functions are discovered:

```python
class ApiClient:
    pass


def create_client() -> ApiClient:
    return ApiClient()


class _InternalClient:
    pass
```

Here, `ApiClient` and `create_client` are public. `_InternalClient` is ignored.

### `all_public`

This mode can additionally export constants and type aliases:

```toml
[tool.py-init-tools]
discovery_mode = "all_public"
export_constants = true
export_type_aliases = true
```

```python
from typing import TypeAlias

ClientName: TypeAlias = str
DEFAULT_TIMEOUT = 30
```

---

## Re-exports

Eager public re-exports are disabled unless a package is explicitly allowlisted:

```toml
[tool.py-init-tools]
reexport_allowlist = ["api"]
```

A generated initializer may then contain:

```python
from .client import ApiClient
from .models import ApiResponse

__all__ = [
    "ApiClient",
    "ApiResponse",
]
```

Packages outside the allowlist receive lightweight initializers without eager
imports. This helps avoid circular imports and import-time side effects.

Root re-exports are controlled separately:

```toml
[tool.py-init-tools]
generate_root_reexports = true
```

They are disabled by default.

---

## Excluding public-looking names

Names that look public but belong to the internal API can be excluded.

### By directory

```toml
[tool.py-init-tools.private_names_by_dir]
"services/internal" = [
  "InternalClient",
  "LegacyService"
]
```

### By module

```toml
[tool.py-init-tools.private_names_by_module]
"api/client.py" = [
  "InternalClient"
]
```

Paths are relative to the configured package root.

---

## Generated-file tracking

Each generated file starts with a technical sentinel:

```python
# @generated py-init-tools format=1 id=... version=1 revision=1
```

The remaining docstring contains a human-readable notice and the project URL:

```python
"""My Python package.

Generated by py-init-tools — do not edit manually.
Source: https://gitlab.com/dev-tools-cr/python/py-init-tools
"""
```

The sentinel is checked against:

```text
.py-init-tools/state.json
```

The registry stores:

- the generated file's UUID;
- its project-relative path;
- its version and revision;
- a SHA-256 hash of its generated body;
- creation and update dates;
- a short generation history.

The registry contains no secret and uses only JSON. It should normally be
committed alongside the generated files:

```bash
git add .py-init-tools/state.json
```

Temporary registry files can be ignored:

```gitignore
.py-init-tools/*.tmp
```

### Versions and revisions

- **Version** identifies an incarnation of a file.
- **Revision** identifies a content change within that incarnation.
- The version increases when a tracked file is deleted and recreated.
- The revision increases when its generated content changes or is repaired.
- Running the tool without any content change increments neither value.

Examples:

| **Event**                              | **Result**            |
| -------------------------------------- | --------------------- |
| First generation                       | version 1, revision 1 |
| Generated content changes              | version 1, revision 2 |
| File is manually modified and repaired | version 1, revision 3 |
| File is deleted and regenerated        | version 2, revision 1 |
| Nothing changes                        | no increment          |

The sentinel format version is independent from the generated file's version
and revision.

---

## Manual file protection

A file is accepted as generated only when:

1. its sentinel has the expected format;
2. its path exists in the registry;
3. its UUID, version, and revision match the registry;
4. its body matches the registered SHA-256 hash.

A random UUID or copied sentinel is therefore not enough to make a file appear
valid.

Files without a valid generated identity are not overwritten unless
`--overwrite-manual` is passed.

For the initial migration from older generated files, run:

```bash
pyinit --write --overwrite-manual
```

After migration, regular updates only require:

```bash
pyinit --write
```

---

## Test package markers

Configured test roots receive minimal package markers:

```python
# @generated py-init-tools format=1 id=... version=1 revision=1
# tests/unit/__init__.py
# Package marker — do not add imports here.
# Generated by py-init-tools — do not edit manually.
# Source: https://gitlab.com/dev-tools-cr/python/py-init-tools
```

These files intentionally contain no imports.

Use `--skip-tests` to disable their generation for one command.

---

## Recommended workflow

During development:

```bash
pyinit
```

Review the dry-run, then apply it:

```bash
pyinit --write
```

Before committing:

```bash
pyinit --check
```

Commit both the generated files and their registry:

```bash
git add .py-init-tools/state.json
git add --all
```

In CI:

```bash
pyinit --check
```

---

## Development

This project uses Pixi for its development environment and task execution.

Run all checks:

```bash
pixi run check
```

Run the tests:

```bash
pixi run pytest
```

Run tests with coverage:

```bash
pixi run pytest --cov=py_init_tools --cov-branch
```

The quality checks include:

- Ruff linting and formatting;
- BasedPyright strict type checking;
- Pytest.

---

## Design principles

- **Safe by default**: no writes without `--write`.
- **Static analysis only**: target project modules are never imported.
- **Manual files are protected**: overwriting requires an explicit option.
- **Deterministic generation**: unchanged inputs produce unchanged files.
- **Explicit API exposure**: eager re-exports are allowlisted.
- **Transparent tracking**: generated metadata is stored as readable JSON.
- **Lightweight implementation**: no database, secret, or external runtime dependency.

---

## License

This project is distributed under the MIT License with an additional
no-endorsement clause.

See [`LICENSE`](LICENSE) for details.
