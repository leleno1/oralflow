"""Pure allowlisted M1 node handlers with embedded Schema gates."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from oralflow.runtime.bindings import JsonObject, NodeRuntimeError
from oralflow.runtime.expressions import evaluate_path
from oralflow.validators.schema import SchemaBundle, validate_instance

NODE_SCHEMA_ID = "urn:oralflow:schema:node:0.1.0"
SUPPORTED_NODE_KINDS = frozenset({"input", "transform", "gate", "terminal"})
SUPPORTED_TRANSFORMS = frozenset({"uppercase", "length_evaluation"})


@dataclass(frozen=True, slots=True)
class NodeHandlerResult:
    """Validated pure node output and optional terminal control fact."""

    output: JsonObject
    terminal_outcome: Literal["success", "failure", "cancelled"] | None = None


def _raise_schema_error(code: str, label: str, paths: list[str]) -> None:
    rendered = ", ".join(paths) if paths else "/"
    raise NodeRuntimeError(f"{label} Schema validation failed at: {rendered}", code=code)


def _reject_remote_references(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef"} and (
                not isinstance(item, str) or not item.startswith("#")
            ):
                raise NodeRuntimeError(
                    "Embedded Schemas may use local fragment references only",
                    code="NODE_SCHEMA_INVALID",
                )
            _reject_remote_references(item)
    elif isinstance(value, list):
        for item in value:
            _reject_remote_references(item)


def _validate_embedded(
    value: JsonObject,
    schema: JsonObject,
    *,
    error_code: str,
    label: str,
) -> None:
    _reject_remote_references(schema)
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(
            validator.iter_errors(value),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                error.message,
            ),
        )
    except SchemaError as error:
        raise NodeRuntimeError(
            f"{label} contains an invalid Draft 2020-12 Schema",
            code="NODE_SCHEMA_INVALID",
        ) from error
    except Exception as error:
        raise NodeRuntimeError(
            f"{label} contains an unresolvable local Schema reference",
            code="NODE_SCHEMA_INVALID",
        ) from error
    if errors:
        paths = [
            "/" + "/".join(str(part) for part in error.absolute_path)
            if error.absolute_path
            else "/"
            for error in errors
        ]
        _raise_schema_error(error_code, label, paths)


def _node_contract(node: JsonObject, schema_bundle: SchemaBundle) -> None:
    report = validate_instance(node, NODE_SCHEMA_ID, schema_bundle)
    if report.valid:
        return
    _raise_schema_error(
        "NODE_SCHEMA_INVALID",
        "Node envelope",
        [issue.instance_path or "/" for issue in report.issues],
    )


def _contract_object(node: JsonObject, section: str, field_name: str) -> JsonObject:
    contract = node.get(section)
    value = contract.get(field_name) if isinstance(contract, dict) else None
    if not isinstance(value, dict):
        raise NodeRuntimeError(
            f"Node {section}.{field_name} must be an object",
            code="NODE_SCHEMA_INVALID",
        )
    return value


def _input_handler(inputs: JsonObject, _: JsonObject, __: JsonObject) -> NodeHandlerResult:
    return NodeHandlerResult(output=deepcopy(inputs))


def _uppercase_handler(
    inputs: JsonObject,
    _: JsonObject,
    __: JsonObject,
) -> NodeHandlerResult:
    string_fields = [name for name, value in inputs.items() if isinstance(value, str)]
    if len(string_fields) != 1:
        raise NodeRuntimeError(
            "uppercase requires exactly one string input field",
            code="NODE_INPUT_INVALID",
        )
    output = deepcopy(inputs)
    field_name = string_fields[0]
    output[field_name] = inputs[field_name].upper()
    return NodeHandlerResult(output=output)


def _length_evaluation_handler(
    inputs: JsonObject,
    config: JsonObject,
    _: JsonObject,
) -> NodeHandlerResult:
    text = inputs.get("text")
    threshold = config.get("minimum_length")
    if not isinstance(text, str):
        raise NodeRuntimeError(
            "length_evaluation requires a text string",
            code="NODE_INPUT_INVALID",
        )
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 1:
        raise NodeRuntimeError(
            "length_evaluation requires a positive minimum_length",
            code="NODE_CONFIG_INVALID",
        )
    return NodeHandlerResult(
        output={
            "text": text,
            "length": len(text),
            "threshold": threshold,
            "case": "qualified" if len(text) >= threshold else "retry",
        }
    )


def _gate_handler(inputs: JsonObject, _: JsonObject, node: JsonObject) -> NodeHandlerResult:
    condition = node.get("condition")
    language = condition.get("language") if isinstance(condition, dict) else None
    expression = condition.get("expression") if isinstance(condition, dict) else None
    if language != "oralflow-expression-0.1" or not isinstance(expression, str):
        raise NodeRuntimeError(
            "Gate condition must use oralflow-expression-0.1",
            code="EXPRESSION_INVALID",
        )
    return NodeHandlerResult(output={"case": evaluate_path(expression, inputs)})


def _terminal_handler(
    _: JsonObject,
    __: JsonObject,
    node: JsonObject,
) -> NodeHandlerResult:
    outcome = node.get("outcome")
    if outcome not in {"success", "failure", "cancelled"}:
        raise NodeRuntimeError(
            "Terminal Node has an invalid outcome",
            code="NODE_CONFIG_INVALID",
        )
    return NodeHandlerResult(output={}, terminal_outcome=outcome)


def execute_node_handler(
    node: JsonObject,
    resolved_inputs: JsonObject,
    *,
    schema_bundle: SchemaBundle,
) -> NodeHandlerResult:
    """Validate and execute one pure allowlisted M1 handler."""

    node_copy = deepcopy(node)
    inputs_copy = deepcopy(resolved_inputs)
    _node_contract(node_copy, schema_bundle)
    kind = node_copy.get("kind")
    if kind not in SUPPORTED_NODE_KINDS:
        raise NodeRuntimeError(
            f"Node kind {kind!r} is unsupported in M1",
            code="NODE_KIND_UNSUPPORTED",
        )

    input_schema = _contract_object(node_copy, "inputs", "schema")
    config = _contract_object(node_copy, "config", "values")
    config_schema = _contract_object(node_copy, "config", "schema")
    output_schema = _contract_object(node_copy, "outputs", "schema")
    _validate_embedded(
        inputs_copy,
        input_schema,
        error_code="NODE_INPUT_INVALID",
        label="Node input",
    )
    _validate_embedded(
        config,
        config_schema,
        error_code="NODE_CONFIG_INVALID",
        label="Node config",
    )

    if kind == "input":
        result = _input_handler(inputs_copy, config, node_copy)
    elif kind == "gate":
        result = _gate_handler(inputs_copy, config, node_copy)
    elif kind == "terminal":
        result = _terminal_handler(inputs_copy, config, node_copy)
    else:
        transform_id = config.get("transform_id")
        if transform_id not in SUPPORTED_TRANSFORMS:
            raise NodeRuntimeError(
                f"Transform {transform_id!r} is not allowlisted",
                code="TRANSFORM_UNKNOWN",
            )
        if transform_id == "uppercase":
            result = _uppercase_handler(inputs_copy, config, node_copy)
        else:
            result = _length_evaluation_handler(inputs_copy, config, node_copy)

    _validate_embedded(
        result.output,
        output_schema,
        error_code="NODE_OUTPUT_INVALID",
        label="Node output",
    )
    return NodeHandlerResult(
        output=deepcopy(result.output),
        terminal_outcome=result.terminal_outcome,
    )
