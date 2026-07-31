"""Pure M1 input binding resolution."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, ClassVar

JsonObject = dict[str, Any]
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class NodeRuntimeError(RuntimeError):
    """Stable failure for deterministic M1 node preparation and execution."""

    default_code: ClassVar[str] = "NODE_RUNTIME_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or self.default_code


def _unavailable(reference: str) -> NodeRuntimeError:
    return NodeRuntimeError(
        f"Node input reference is unavailable: {reference!r}",
        code="NODE_INPUT_REFERENCE_UNAVAILABLE",
    )


def _resolve_reference(
    reference: str,
    workflow_inputs: Mapping[str, Any],
    node_outputs: Mapping[str, Mapping[str, Any]],
) -> Any:
    if reference.startswith("workflow-input://"):
        name = reference.removeprefix("workflow-input://")
        if not name or "/" in name:
            raise NodeRuntimeError(
                "Workflow input reference must contain exactly one non-empty name",
                code="NODE_INPUT_REFERENCE_INVALID",
            )
        if name not in workflow_inputs:
            raise _unavailable(reference)
        return deepcopy(workflow_inputs[name])

    if reference.startswith("node-output://"):
        target = reference.removeprefix("node-output://")
        parts = target.split("/")
        if len(parts) != 2 or not all(_IDENTIFIER.fullmatch(part) for part in parts):
            raise NodeRuntimeError(
                "Node output reference must be node-output://node_id/port",
                code="NODE_INPUT_REFERENCE_INVALID",
            )
        node_id, port = parts
        if node_id not in node_outputs or port not in node_outputs[node_id]:
            raise _unavailable(reference)
        return deepcopy(node_outputs[node_id][port])

    scheme = reference.split("://", maxsplit=1)[0] if "://" in reference else ""
    if scheme in {"artifact", "file"}:
        raise NodeRuntimeError(
            f"Reference scheme {scheme!r} is unsupported in M1",
            code="NODE_INPUT_REFERENCE_UNSUPPORTED",
        )
    raise NodeRuntimeError(
        "Node input reference has an invalid or unsupported scheme",
        code="NODE_INPUT_REFERENCE_INVALID",
    )


def resolve_bindings(
    bindings: Mapping[str, Any],
    workflow_inputs: Mapping[str, Any],
    node_outputs: Mapping[str, Mapping[str, Any]],
) -> JsonObject:
    """Resolve approved references and deep-copy JSON literal bindings."""

    resolved: JsonObject = {}
    for name, binding in bindings.items():
        if isinstance(binding, dict) and "ref" in binding:
            if set(binding) != {"ref"} or not isinstance(binding["ref"], str):
                raise NodeRuntimeError(
                    f"Binding {name!r} has an invalid reference object",
                    code="NODE_INPUT_REFERENCE_INVALID",
                )
            resolved[name] = _resolve_reference(
                binding["ref"],
                workflow_inputs,
                node_outputs,
            )
        else:
            resolved[name] = deepcopy(binding)
    return resolved


def resolve_node_inputs(
    node: Mapping[str, Any],
    workflow_inputs: Mapping[str, Any],
    node_outputs: Mapping[str, Mapping[str, Any]],
) -> JsonObject:
    """Resolve the bindings declared by one Node envelope."""

    inputs = node.get("inputs")
    bindings = inputs.get("bindings") if isinstance(inputs, dict) else None
    if not isinstance(bindings, dict):
        raise NodeRuntimeError(
            "Node inputs.bindings must be an object",
            code="NODE_INPUT_REFERENCE_INVALID",
        )
    return resolve_bindings(bindings, workflow_inputs, node_outputs)
