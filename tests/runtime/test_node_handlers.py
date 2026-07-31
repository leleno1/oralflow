from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from oralflow.runtime import (
    NodeRuntimeError,
    evaluate_path,
    execute_node_handler,
    resolve_bindings,
    resolve_node_inputs,
)
from oralflow.validators.schema import SchemaBundle, load_schema_bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def schema_bundle() -> SchemaBundle:
    return load_schema_bundle(ROOT / "schemas")


@pytest.fixture
def child_workflow() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (ROOT / "examples" / "minimal-child-workflow.json").read_text(encoding="utf-8")
    )
    return value


def _input_node(workflow: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(workflow["nodes"][0])


def _terminal_node(workflow: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(workflow["nodes"][1])


def _transform_node(workflow: dict[str, Any], transform_id: str) -> dict[str, Any]:
    node = _input_node(workflow)
    node["id"] = f"transform_{transform_id}"
    node["kind"] = "transform"
    node.pop("source")
    node["inputs"] = {
        "bindings": {"text": {"ref": "workflow-input://text"}},
        "schema": {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
    }
    node["config"] = {
        "values": {"transform_id": transform_id},
        "schema": {
            "type": "object",
            "required": ["transform_id"],
            "properties": {"transform_id": {"type": "string"}},
            "additionalProperties": transform_id == "length_evaluation",
        },
    }
    node["outputs"] = {
        "destinations": {"text": f"node-output://transform_{transform_id}/text"},
        "schema": {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
    }
    return node


def _length_node(workflow: dict[str, Any], minimum_length: int = 5) -> dict[str, Any]:
    node = _transform_node(workflow, "length_evaluation")
    node["config"] = {
        "values": {
            "transform_id": "length_evaluation",
            "minimum_length": minimum_length,
        },
        "schema": {
            "type": "object",
            "required": ["transform_id", "minimum_length"],
            "properties": {
                "transform_id": {"const": "length_evaluation"},
                "minimum_length": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
    }
    node["outputs"]["schema"] = {
        "type": "object",
        "required": ["text", "length", "threshold", "case"],
        "properties": {
            "text": {"type": "string"},
            "length": {"type": "integer", "minimum": 0},
            "threshold": {"type": "integer", "minimum": 1},
            "case": {"enum": ["qualified", "retry"]},
        },
        "additionalProperties": False,
    }
    return node


def _gate_node(workflow: dict[str, Any]) -> dict[str, Any]:
    node = _input_node(workflow)
    node["id"] = "evaluation_gate"
    node["kind"] = "gate"
    node.pop("source")
    node["condition"] = {
        "language": "oralflow-expression-0.1",
        "expression": "evaluation.case",
    }
    node["inputs"] = {
        "bindings": {},
        "schema": {"type": "object", "required": ["evaluation"]},
    }
    node["config"] = {
        "values": {},
        "schema": {"type": "object", "additionalProperties": False},
    }
    node["outputs"] = {
        "destinations": {"case": "node-output://evaluation_gate/case"},
        "schema": {
            "type": "object",
            "required": ["case"],
            "properties": {"case": {"enum": ["qualified", "retry"]}},
            "additionalProperties": False,
        },
    }
    return node


def test_bindings_resolve_literals_workflow_inputs_and_node_outputs() -> None:
    literal = {"nested": [1, 2]}
    bindings = {
        "request": {"ref": "workflow-input://request"},
        "case": {"ref": "node-output://gate_1/case"},
        "literal": literal,
    }

    resolved = resolve_bindings(
        bindings,
        {"request": "hello"},
        {"gate_1": {"case": "qualified"}},
    )

    assert resolved == {
        "request": "hello",
        "case": "qualified",
        "literal": literal,
    }
    resolved["literal"]["nested"].append(3)
    assert literal == {"nested": [1, 2]}


def test_resolve_node_inputs_uses_declared_bindings(child_workflow: dict[str, Any]) -> None:
    resolved = resolve_node_inputs(
        _input_node(child_workflow),
        {"report": {"summary": "ok"}},
        {},
    )
    assert resolved == {"report": {"summary": "ok"}}


@pytest.mark.parametrize(
    ("reference", "code"),
    [
        ("workflow-input://missing", "NODE_INPUT_REFERENCE_UNAVAILABLE"),
        ("node-output://unknown/value", "NODE_INPUT_REFERENCE_UNAVAILABLE"),
        ("node-output://node/", "NODE_INPUT_REFERENCE_INVALID"),
        ("artifact://report.json", "NODE_INPUT_REFERENCE_UNSUPPORTED"),
        ("file://notes.txt", "NODE_INPUT_REFERENCE_UNSUPPORTED"),
        ("https://example.test/value", "NODE_INPUT_REFERENCE_INVALID"),
    ],
)
def test_binding_failures_have_stable_codes(reference: str, code: str) -> None:
    with pytest.raises(NodeRuntimeError) as captured:
        resolve_bindings({"value": {"ref": reference}}, {}, {})
    assert captured.value.code == code


def test_expression_resolves_scalar_path_without_coercion() -> None:
    assert evaluate_path("evaluation.case", {"evaluation": {"case": "qualified"}}) == (
        "qualified"
    )
    assert evaluate_path("metrics.length", {"metrics": {"length": 5}}) == 5
    assert evaluate_path("result.ok", {"result": {"ok": False}}) is False
    assert evaluate_path("result.value", {"result": {"value": None}}) is None


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "items[0]",
        "func()",
        "a + b",
        "a b",
        "'quoted'",
        "__class__",
        "constructor.value",
        "safe.__proto__",
        "prototype.value",
        ".leading",
        "trailing.",
    ],
)
def test_expression_rejects_executable_or_magic_syntax(expression: str) -> None:
    with pytest.raises(NodeRuntimeError) as captured:
        evaluate_path(expression, {"safe": {"value": 1}})
    assert captured.value.code == "EXPRESSION_INVALID"


def test_expression_rejects_unknown_paths_containers_and_non_finite_numbers() -> None:
    with pytest.raises(NodeRuntimeError) as unknown:
        evaluate_path("missing.value", {})
    assert unknown.value.code == "EXPRESSION_PATH_UNKNOWN"

    for value in ({"nested": True}, [1], float("inf"), float("nan")):
        with pytest.raises(NodeRuntimeError) as invalid:
            evaluate_path("value", {"value": value})
        assert invalid.value.code == "EXPRESSION_RESULT_INVALID"


def test_input_and_terminal_handlers_are_pure_and_validated(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    input_node = _input_node(child_workflow)
    input_node["outputs"] = {
        "destinations": {"report": "node-output://child_input/report"},
        "schema": {
            "type": "object",
            "required": ["report"],
            "properties": {"report": {"type": "object"}},
            "additionalProperties": False,
        },
    }
    terminal_node = _terminal_node(child_workflow)
    values = {"report": {"summary": "synthetic"}}
    original = deepcopy(values)

    input_result = execute_node_handler(input_node, values, schema_bundle=schema_bundle)
    terminal_result = execute_node_handler(
        terminal_node,
        {"summary": "synthetic"},
        schema_bundle=schema_bundle,
    )

    assert input_result.output == values
    assert input_result.output is not values
    assert values == original
    assert terminal_result.output == {}
    assert terminal_result.terminal_outcome == "success"


def test_uppercase_transform_is_deterministic(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    node = _transform_node(child_workflow, "uppercase")
    inputs = {"text": "Hello, 世界"}

    first = execute_node_handler(node, inputs, schema_bundle=schema_bundle)
    second = execute_node_handler(node, inputs, schema_bundle=schema_bundle)

    assert first == second
    assert first.output == {"text": "HELLO, 世界"}
    assert inputs == {"text": "Hello, 世界"}


@pytest.mark.parametrize(
    ("text", "expected_case"),
    [("hello", "qualified"), ("hi", "retry")],
)
def test_length_evaluation_emits_declared_evidence(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
    text: str,
    expected_case: str,
) -> None:
    result = execute_node_handler(
        _length_node(child_workflow),
        {"text": text},
        schema_bundle=schema_bundle,
    )
    assert result.output == {
        "text": text,
        "length": len(text),
        "threshold": 5,
        "case": expected_case,
    }


def test_gate_uses_only_path_expression(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    result = execute_node_handler(
        _gate_node(child_workflow),
        {"evaluation": {"case": "qualified"}},
        schema_bundle=schema_bundle,
    )
    assert result.output == {"case": "qualified"}


def test_unknown_kind_and_transform_are_rejected(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    unsupported = _input_node(child_workflow)
    unsupported["kind"] = "agent_task"
    unsupported["role_id"] = "mock_role"
    unsupported.pop("source")
    with pytest.raises(NodeRuntimeError) as kind_error:
        execute_node_handler(
            unsupported,
            {"report": {}},
            schema_bundle=schema_bundle,
        )
    assert kind_error.value.code == "NODE_KIND_UNSUPPORTED"

    unknown = _transform_node(child_workflow, "unknown")
    with pytest.raises(NodeRuntimeError) as transform_error:
        execute_node_handler(unknown, {"text": "hello"}, schema_bundle=schema_bundle)
    assert transform_error.value.code == "TRANSFORM_UNKNOWN"


def test_input_config_and_output_schema_failures_are_separate(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    uppercase = _transform_node(child_workflow, "uppercase")
    with pytest.raises(NodeRuntimeError) as input_error:
        execute_node_handler(uppercase, {"text": 42}, schema_bundle=schema_bundle)
    assert input_error.value.code == "NODE_INPUT_INVALID"

    length = _length_node(child_workflow, minimum_length=0)
    with pytest.raises(NodeRuntimeError) as config_error:
        execute_node_handler(length, {"text": "hello"}, schema_bundle=schema_bundle)
    assert config_error.value.code == "NODE_CONFIG_INVALID"

    wrong_output = _transform_node(child_workflow, "uppercase")
    wrong_output["outputs"]["schema"] = {
        "type": "object",
        "required": ["length"],
        "properties": {"length": {"type": "integer"}},
        "additionalProperties": False,
    }
    with pytest.raises(NodeRuntimeError) as output_error:
        execute_node_handler(wrong_output, {"text": "hello"}, schema_bundle=schema_bundle)
    assert output_error.value.code == "NODE_OUTPUT_INVALID"


def test_remote_embedded_schema_reference_is_rejected_before_resolution(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    node = _input_node(child_workflow)
    node["inputs"]["schema"] = {"$ref": "https://example.test/schema.json"}

    with pytest.raises(NodeRuntimeError) as captured:
        execute_node_handler(node, {"report": {}}, schema_bundle=schema_bundle)
    assert captured.value.code == "NODE_SCHEMA_INVALID"


def test_unresolvable_local_schema_reference_is_normalized(
    child_workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    node = _input_node(child_workflow)
    node["inputs"]["schema"] = {"$ref": "#/$defs/missing"}

    with pytest.raises(NodeRuntimeError) as captured:
        execute_node_handler(node, {"report": {}}, schema_bundle=schema_bundle)
    assert captured.value.code == "NODE_SCHEMA_INVALID"
