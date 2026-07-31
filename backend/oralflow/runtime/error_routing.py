"""Pure structured-error normalization and deterministic M1 error routing."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, ClassVar

from jsonschema import Draft202012Validator

from oralflow.domain.runtime import ErrorCategory, JsonObject, StructuredError

_MAX_DETAIL_DEPTH = 4
_MAX_DETAIL_ENTRIES = 32
_MAX_LIST_ITEMS = 16
_MAX_STRING_LENGTH = 256
_SENSITIVE_PARTS = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
)


class ErrorRoutingError(RuntimeError):
    """Stable failure raised when an error edge cannot be selected safely."""

    default_code: ClassVar[str] = "ERROR_ROUTING_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or self.default_code


@dataclass(frozen=True, slots=True)
class NodeFailure:
    """One normalized node failure after its rejection/failure Event is appended."""

    error: StructuredError


@dataclass(slots=True)
class _DetailBudget:
    remaining: int = _MAX_DETAIL_ENTRIES


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def _sanitize(value: Any, *, depth: int, budget: _DetailBudget) -> Any:
    if budget.remaining <= 0:
        return "[TRUNCATED]"
    budget.remaining -= 1
    if depth > _MAX_DETAIL_DEPTH:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else "[NON_FINITE]"
    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]
    if isinstance(value, dict):
        sanitized: JsonObject = {}
        for raw_key in sorted(value, key=lambda item: str(item)):
            if budget.remaining <= 0:
                sanitized["_truncated"] = True
                break
            key = str(raw_key)[:128]
            if _is_sensitive(key):
                budget.remaining -= 1
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _sanitize(
                    value[raw_key],
                    depth=depth + 1,
                    budget=budget,
                )
        return sanitized
    if isinstance(value, (list, tuple)):
        items = [
            _sanitize(item, depth=depth + 1, budget=budget)
            for item in value[:_MAX_LIST_ITEMS]
            if budget.remaining > 0
        ]
        if len(value) > _MAX_LIST_ITEMS or budget.remaining <= 0:
            items.append("[TRUNCATED]")
        return items
    return "[UNSUPPORTED]"


def sanitize_error_details(details: JsonObject | None) -> JsonObject | None:
    """Return a deterministic, bounded copy with common secret fields redacted."""

    if details is None:
        return None
    sanitized = _sanitize(details, depth=0, budget=_DetailBudget())
    return sanitized if isinstance(sanitized, dict) else {"value": sanitized}


def _reject_remote_references(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef"} and (
                not isinstance(item, str) or not item.startswith("#")
            ):
                raise ValueError("remote error Schema reference")
            _reject_remote_references(item)
    elif isinstance(value, list):
        for item in value:
            _reject_remote_references(item)


def _declared_error_is_valid(node: JsonObject, error: StructuredError) -> bool:
    contract = node.get("error_contract")
    if not isinstance(contract, dict):
        return False
    codes = contract.get("allowed_codes")
    categories = contract.get("allowed_categories")
    if not isinstance(codes, list) or not isinstance(categories, list):
        return False
    if error.code not in codes and error.category.value not in categories:
        return False
    schema = contract.get("schema")
    if not isinstance(schema, dict):
        return False
    try:
        _reject_remote_references(schema)
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema).is_valid(
            error.model_dump(mode="json", exclude_none=True)
        )
    except Exception:
        return False


def _internal_error() -> StructuredError:
    return StructuredError(
        code="NODE_INTERNAL_ERROR",
        message="Node failed with NODE_INTERNAL_ERROR",
        category=ErrorCategory.INTERNAL,
        retryable=False,
    )


def normalize_node_failure(
    node: JsonObject,
    *,
    code: str,
    category: ErrorCategory,
    details: JsonObject | None = None,
) -> StructuredError:
    """Create one bounded error and enforce the Node's declared error contract."""

    contract = node.get("error_contract")
    retryable_codes = (
        contract.get("retryable_codes") if isinstance(contract, dict) else None
    )
    retryable = isinstance(retryable_codes, list) and code in retryable_codes
    try:
        candidate = StructuredError(
            code=code,
            message=f"Node failed with {code}",
            category=category,
            retryable=retryable,
            details=sanitize_error_details(details),
        )
    except Exception:
        return _internal_error()
    return candidate if _declared_error_is_valid(node, candidate) else _internal_error()


def normalize_unknown_failure() -> StructuredError:
    """Normalize an arbitrary exception without inspecting or serializing it."""

    return _internal_error()


def select_error_edge(
    outgoing_edges: tuple[JsonObject, ...],
    error: StructuredError,
) -> JsonObject | None:
    """Select one exact-code edge, otherwise one category edge, without fallback."""

    error_edges = [edge for edge in outgoing_edges if edge.get("kind") == "error"]
    exact = [
        edge
        for edge in error_edges
        if error.code in edge.get("match", {}).get("codes", [])
    ]
    if len(exact) > 1:
        raise ErrorRoutingError(
            "Multiple error edges match the normalized code",
            code="EDGE_SELECTION_AMBIGUOUS",
        )
    if exact:
        return deepcopy(exact[0])

    category = [
        edge
        for edge in error_edges
        if error.category.value in edge.get("match", {}).get("categories", [])
    ]
    if len(category) > 1:
        raise ErrorRoutingError(
            "Multiple error edges match the normalized category",
            code="EDGE_SELECTION_AMBIGUOUS",
        )
    return deepcopy(category[0]) if category else None


__all__ = [
    "ErrorRoutingError",
    "NodeFailure",
    "normalize_node_failure",
    "normalize_unknown_failure",
    "sanitize_error_details",
    "select_error_edge",
]
