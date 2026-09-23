# Copyright (c) 2026 Clément RACINET
"""Generated-file identity and history registry."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, cast

from py_init_tools.constants import (
    REGISTRY_DIR_NAME,
    REGISTRY_FILE_NAME,
    REGISTRY_FORMAT_VERSION,
    SENTINEL_PREFIX,
)

if TYPE_CHECKING:
    from pathlib import Path

GenerationOperation = Literal[
    "created",
    "updated",
    "recreated",
    "repaired",
]

SENTINEL_PATTERN = re.compile(
    rf"^{re.escape(SENTINEL_PREFIX)} "
    r"id=(?P<file_id>[0-9a-f]{8}-"
    r"[0-9a-f]{4}-"
    r"[0-9a-f]{4}-"
    r"[0-9a-f]{4}-"
    r"[0-9a-f]{12}) "
    r"version=(?P<version>[1-9][0-9]*) "
    r"revision=(?P<revision>[1-9][0-9]*)$"
)


class GeneratedStatus(StrEnum):
    """Possible generated-file validation states."""

    VALID = "valid"
    NOT_GENERATED = "not-generated"
    UNKNOWN_PATH = "unknown-path"
    ID_MISMATCH = "id-mismatch"
    VERSION_MISMATCH = "version-mismatch"
    REVISION_MISMATCH = "revision-mismatch"
    MODIFIED = "modified"


@dataclass(frozen=True, slots=True)
class Sentinel:
    """Metadata extracted from a generated-file sentinel."""

    file_id: str
    version: int
    revision: int


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One meaningful generation event."""

    operation: GenerationOperation
    version: int
    revision: int
    generated_at: str
    body_sha256: str


@dataclass(slots=True)
class FileRecord:
    """Persistent information about one generated file."""

    file_id: str
    path: str
    version: int
    revision: int
    body_sha256: str
    created_at: str
    updated_at: str
    history: list[HistoryEntry] = field(default_factory=list)


@dataclass(slots=True)
class Registry:
    """Project-local registry of generated files."""

    format_version: int = REGISTRY_FORMAT_VERSION
    files: dict[str, FileRecord] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Result of registering an expected generated body."""

    record: FileRecord
    changed: bool


def registry_path(project_root: Path) -> Path:
    """Return the project registry path."""
    return project_root / REGISTRY_DIR_NAME / REGISTRY_FILE_NAME


def body_sha256(body: str) -> str:
    """Return the SHA-256 digest of a generated file body."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def utc_now() -> str:
    """Return the current UTC date in ISO 8601 format."""
    return (
        datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace(
            "+00:00",
            "Z",
        )
    )


def new_file_id() -> str:
    """Return a new generated-file identifier."""
    return str(uuid.uuid4())


def format_sentinel(record: FileRecord) -> str:
    """Format the sentinel for a generated-file record."""
    return (
        f"{SENTINEL_PREFIX} "
        f"id={record.file_id} "
        f"version={record.version} "
        f"revision={record.revision}"
    )


def compose_generated_content(record: FileRecord, body: str) -> str:
    """Combine a generated-file sentinel with its body."""
    return f"{format_sentinel(record)}\n{body}"


def parse_sentinel(content: str) -> Sentinel | None:
    """Parse a generated-file sentinel from the first line."""
    first_line, _separator, _body = content.partition("\n")
    normalized_line = first_line.rstrip("\r")
    match = SENTINEL_PATTERN.fullmatch(normalized_line)

    if match is None:
        return None

    return Sentinel(
        file_id=match.group("file_id"),
        version=int(match.group("version")),
        revision=int(match.group("revision")),
    )


def extract_body(content: str) -> str | None:
    """Return the body following a valid generated-file sentinel."""
    if parse_sentinel(content) is None:
        return None

    _first_line, separator, body = content.partition("\n")

    if not separator:
        return ""

    return body


def empty_registry() -> Registry:
    """Return an empty registry."""
    return Registry()


def _require_mapping(value: object, *, label: str) -> Mapping[str, object]:
    """Validate and return a string-keyed mapping."""
    if not isinstance(value, Mapping):
        message = f"{label} must be a JSON object."
        raise TypeError(message)

    raw_mapping = cast("Mapping[object, object]", value)

    if not all(isinstance(key, str) for key in raw_mapping):
        message = f"{label} contains a non-string key."
        raise TypeError(message)

    return cast("Mapping[str, object]", raw_mapping)


def _require_list(value: object, *, label: str) -> list[object]:
    """Validate and return a JSON list."""
    if not isinstance(value, list):
        message = f"{label} must be a JSON array."
        raise TypeError(message)

    return cast("list[object]", value)


def _require_str(
    mapping: Mapping[str, object],
    key: str,
    *,
    label: str,
) -> str:
    """Read a required string from a JSON mapping."""
    value = mapping.get(key)

    if not isinstance(value, str):
        message = f"{label}.{key} must be a string."
        raise TypeError(message)

    return value


def _require_int(
    mapping: Mapping[str, object],
    key: str,
    *,
    label: str,
) -> int:
    """Read a required positive integer from a JSON mapping."""
    value = mapping.get(key)

    if not isinstance(value, int) or isinstance(value, bool):
        message = f"{label}.{key} must be an integer."
        raise TypeError(message)

    if value < 1:
        message = f"{label}.{key} must be a positive integer."
        raise ValueError(message)

    return value


def _parse_operation(value: str, *, label: str) -> GenerationOperation:
    """Validate a generation operation."""
    valid_operations = {
        "created",
        "updated",
        "recreated",
        "repaired",
    }

    if value not in valid_operations:
        message = f"{label} has an unsupported operation: {value!r}."
        raise ValueError(message)

    return cast("GenerationOperation", value)


def _history_entry_from_json(
    value: object,
    *,
    label: str,
) -> HistoryEntry:
    """Build one history entry from JSON data."""
    mapping = _require_mapping(value, label=label)
    operation = _parse_operation(
        _require_str(mapping, "operation", label=label),
        label=label,
    )

    return HistoryEntry(
        operation=operation,
        version=_require_int(mapping, "version", label=label),
        revision=_require_int(mapping, "revision", label=label),
        generated_at=_require_str(mapping, "generated_at", label=label),
        body_sha256=_require_str(mapping, "body_sha256", label=label),
    )


def _file_record_from_json(
    relative_path: str,
    value: object,
) -> FileRecord:
    """Build a file record from JSON data."""
    label = f"files[{relative_path!r}]"
    mapping = _require_mapping(value, label=label)
    raw_history = _require_list(mapping.get("history"), label=f"{label}.history")

    history = [
        _history_entry_from_json(
            history_value,
            label=f"{label}.history[{index}]",
        )
        for index, history_value in enumerate(raw_history)
    ]

    recorded_path = _require_str(mapping, "path", label=label)

    if recorded_path != relative_path:
        message = (
            f"{label}.path is {recorded_path!r}, "
            f"but its registry key is {relative_path!r}."
        )
        raise ValueError(message)

    return FileRecord(
        file_id=_require_str(mapping, "file_id", label=label),
        path=recorded_path,
        version=_require_int(mapping, "version", label=label),
        revision=_require_int(mapping, "revision", label=label),
        body_sha256=_require_str(mapping, "body_sha256", label=label),
        created_at=_require_str(mapping, "created_at", label=label),
        updated_at=_require_str(mapping, "updated_at", label=label),
        history=history,
    )


def load_registry(project_root: Path) -> Registry:
    """Load and validate the project registry."""
    path = registry_path(project_root)

    if not path.exists():
        return empty_registry()

    raw_data: object = json.loads(path.read_text(encoding="utf-8"))
    mapping = _require_mapping(raw_data, label="registry")
    format_version = _require_int(
        mapping,
        "format_version",
        label="registry",
    )

    if format_version != REGISTRY_FORMAT_VERSION:
        message = (
            "Unsupported registry format version: "
            f"{format_version}. Expected {REGISTRY_FORMAT_VERSION}."
        )
        raise ValueError(message)

    raw_files = _require_mapping(
        mapping.get("files"),
        label="registry.files",
    )

    files = {
        relative_path: _file_record_from_json(
            relative_path,
            raw_record,
        )
        for relative_path, raw_record in raw_files.items()
    }

    return Registry(
        format_version=format_version,
        files=files,
    )


def _history_entry_to_json(entry: HistoryEntry) -> dict[str, object]:
    """Convert one history entry to JSON-compatible data."""
    return {
        "operation": entry.operation,
        "version": entry.version,
        "revision": entry.revision,
        "generated_at": entry.generated_at,
        "body_sha256": entry.body_sha256,
    }


def _file_record_to_json(record: FileRecord) -> dict[str, object]:
    """Convert one file record to JSON-compatible data."""
    return {
        "file_id": record.file_id,
        "path": record.path,
        "version": record.version,
        "revision": record.revision,
        "body_sha256": record.body_sha256,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "history": [_history_entry_to_json(entry) for entry in record.history],
    }


def registry_to_json(registry: Registry) -> dict[str, object]:
    """Convert a registry to JSON-compatible data."""
    return {
        "format_version": registry.format_version,
        "files": {
            relative_path: _file_record_to_json(record)
            for relative_path, record in sorted(registry.files.items())
        },
    }


def save_registry(project_root: Path, registry: Registry) -> None:
    """Write the project registry atomically."""
    path = registry_path(project_root)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    raw_data = registry_to_json(registry)

    serialized = json.dumps(
        raw_data,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path.write_text(f"{serialized}\n", encoding="utf-8")
    temporary_path.replace(path)


def validate_generated_content(
    registry: Registry,
    *,
    relative_path: str,
    content: str,
) -> GeneratedStatus:
    """Validate generated content against the project registry."""
    sentinel = parse_sentinel(content)
    status = GeneratedStatus.VALID

    if sentinel is None:
        status = GeneratedStatus.NOT_GENERATED
    else:
        record = registry.files.get(relative_path)

        if record is None:
            status = GeneratedStatus.UNKNOWN_PATH
        elif sentinel.file_id != record.file_id:
            status = GeneratedStatus.ID_MISMATCH
        elif sentinel.version != record.version:
            status = GeneratedStatus.VERSION_MISMATCH
        elif sentinel.revision != record.revision:
            status = GeneratedStatus.REVISION_MISMATCH
        else:
            body = extract_body(content)

            if body is None or body_sha256(body) != record.body_sha256:
                status = GeneratedStatus.MODIFIED

    return status


def register_generated_body(
    registry: Registry,
    *,
    relative_path: str,
    body: str,
    recreate: bool,
    repair: bool,
) -> GenerationResult:
    """Register a generated body and update its generation history."""
    digest = body_sha256(body)
    now = utc_now()
    record = registry.files.get(relative_path)

    if record is None:
        history_entry = HistoryEntry(
            operation="created",
            version=1,
            revision=1,
            generated_at=now,
            body_sha256=digest,
        )
        record = FileRecord(
            file_id=new_file_id(),
            path=relative_path,
            version=1,
            revision=1,
            body_sha256=digest,
            created_at=now,
            updated_at=now,
            history=[history_entry],
        )
        registry.files[relative_path] = record

        return GenerationResult(record=record, changed=True)

    if recreate:
        record.version += 1
        record.revision = 1
        operation: GenerationOperation = "recreated"
    elif repair:
        record.revision += 1
        operation = "repaired"
    elif digest != record.body_sha256:
        record.revision += 1
        operation = "updated"
    else:
        return GenerationResult(record=record, changed=False)

    record.body_sha256 = digest
    record.updated_at = now
    record.history.append(
        HistoryEntry(
            operation=operation,
            version=record.version,
            revision=record.revision,
            generated_at=now,
            body_sha256=digest,
        )
    )

    return GenerationResult(record=record, changed=True)
