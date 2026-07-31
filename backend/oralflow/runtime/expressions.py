"""Safe path-only evaluator for oralflow-expression-0.1."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from oralflow.runtime.bindings import NodeRuntimeError

_EXPRESSION = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_FORBIDDEN_SEGMENTS = frozenset({"constructor", "prototype", "__proto__"})


def evaluate_path(expression: str, values: Mapping[str, Any]) -> str | int | float | bool | None:
    """Resolve an own-key JSON object path without executing code or coercion."""

    if (
        not expression
        or len(expression) > 1024
        or _EXPRESSION.fullmatch(expression) is None
    ):
        raise NodeRuntimeError(
            "Expression is outside oralflow-expression-0.1",
            code="EXPRESSION_INVALID",
        )
    segments = expression.split(".")
    if any(segment.startswith("__") or segment in _FORBIDDEN_SEGMENTS for segment in segments):
        raise NodeRuntimeError(
            "Expression contains a forbidden path segment",
            code="EXPRESSION_INVALID",
        )

    current: Any = values
    for segment in segments:
        if not isinstance(current, dict) or segment not in current:
            raise NodeRuntimeError(
                f"Expression path is unavailable: {expression!r}",
                code="EXPRESSION_PATH_UNKNOWN",
            )
        current = current[segment]

    if current is None or isinstance(current, (str, bool, int)):
        return current
    if isinstance(current, float) and math.isfinite(current):
        return current
    raise NodeRuntimeError(
        "Expression result must be a finite JSON scalar",
        code="EXPRESSION_RESULT_INVALID",
    )
