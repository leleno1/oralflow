"""Offline JSON Schema loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One stable, machine-readable validation failure."""

    code: str
    message: str
    instance_path: str = ""
    schema_path: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "instance_path": self.instance_path,
            "schema_path": self.schema_path,
        }


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Validation result suitable for CLI and test assertions."""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.as_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class SchemaBundle:
    """Known M0 Schemas and their offline reference registry."""

    schemas: dict[str, JsonObject]
    paths: dict[str, Path]
    registry: Registry[Any]


class SchemaLoadError(RuntimeError):
    """Raised when the local Schema set cannot be loaded safely."""


def _json_pointer(parts: Any) -> str:
    escaped = [
        str(part).replace("~", "~0").replace("/", "~1")
        for part in parts
    ]
    return "/" + "/".join(escaped) if escaped else ""


def load_json_object(path: Path) -> JsonObject:
    """Load one UTF-8 JSON object."""

    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise SchemaLoadError(f"Cannot load JSON from {path}: {error}") from error
    if not isinstance(value, dict):
        raise SchemaLoadError(f"Expected a JSON object in {path}")
    return value


def load_schema_bundle(schema_dir: Path) -> SchemaBundle:
    """Load and meta-validate every local Schema without network access."""

    paths = sorted(schema_dir.glob("*.schema.json"))
    if not paths:
        raise SchemaLoadError(f"No Schema files found in {schema_dir}")

    schemas: dict[str, JsonObject] = {}
    schema_paths: dict[str, Path] = {}
    resources: list[tuple[str, Resource[Any]]] = []

    for path in paths:
        schema = load_json_object(path)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise SchemaLoadError(f"Schema {path} has no non-empty $id")
        if schema_id in schemas:
            raise SchemaLoadError(
                f"Duplicate Schema $id {schema_id!r} in {path} and {schema_paths[schema_id]}"
            )
        try:
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema)
        except (SchemaError, Exception) as error:
            raise SchemaLoadError(f"Invalid Draft 2020-12 Schema {path}: {error}") from error
        schemas[schema_id] = schema
        schema_paths[schema_id] = path
        resources.append((schema_id, resource))

    registry: Registry[Any] = Registry().with_resources(resources)
    for schema_id in schemas:
        registry.contents(schema_id)

    return SchemaBundle(schemas=schemas, paths=schema_paths, registry=registry)


def validate_instance(
    instance: JsonObject,
    schema_id: str,
    bundle: SchemaBundle,
) -> ValidationReport:
    """Validate an instance against one known Schema."""

    schema = bundle.schemas.get(schema_id)
    if schema is None:
        return ValidationReport(
            (
                ValidationIssue(
                    code="SCHEMA_VERSION_UNKNOWN",
                    message=f"Unknown Schema identifier: {schema_id}",
                ),
            )
        )

    validator = Draft202012Validator(
        schema,
        registry=bundle.registry,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.message,
        ),
    )
    issues = tuple(
        ValidationIssue(
            code="SCHEMA_VALIDATION_FAILED",
            message=error.message,
            instance_path=_json_pointer(error.absolute_path),
            schema_path=_json_pointer(error.absolute_schema_path),
        )
        for error in errors
    )
    return ValidationReport(issues)
