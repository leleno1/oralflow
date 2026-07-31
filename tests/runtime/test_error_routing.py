from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest
from oralflow.domain import EventType, RunStatus
from oralflow.events import EventFactory, InMemoryEventStore
from oralflow.runtime import engine as engine_module
from oralflow.runtime.engine import execute_workflow
from oralflow.runtime.error_routing import sanitize_error_details
from oralflow.runtime.projection import project_run
from oralflow.validators.schema import SchemaBundle, load_schema_bundle

from tests.runtime import test_sequence_and_condition as sequence_fixture


@pytest.fixture
def schema_bundle() -> SchemaBundle:
    return load_schema_bundle(sequence_fixture.ROOT / "schemas")


def _error_terminal(node_id: str) -> dict[str, Any]:
    node = deepcopy(sequence_fixture._workflow()["nodes"][-1])
    node["id"] = node_id
    node["name"] = f"Error terminal {node_id}"
    node["inputs"] = {
        "bindings": {},
        "schema": {"type": "object", "additionalProperties": False},
    }
    return node


def _error_workflow() -> dict[str, Any]:
    workflow = sequence_fixture._workflow()
    workflow["workflow_id"] = "wf_error_routing"
    workflow["revision"] = "rev_error_001"
    evaluation = workflow["nodes"][2]
    evaluation["outputs"]["schema"]["properties"]["case"] = {
        "const": "impossible"
    }
    workflow["nodes"].extend(
        [
            _error_terminal("code_error_terminal"),
            _error_terminal("category_error_terminal"),
        ]
    )
    workflow["edges"].extend(
        [
            {
                "id": "edge_error_code",
                "kind": "error",
                "from": {"node_id": "evaluation", "port": "error"},
                "to": {"node_id": "code_error_terminal", "port": "error"},
                "match": {"codes": ["NODE_OUTPUT_INVALID"]},
            },
            {
                "id": "edge_error_category",
                "kind": "error",
                "from": {"node_id": "evaluation", "port": "error"},
                "to": {"node_id": "category_error_terminal", "port": "error"},
                "match": {"categories": ["validation"]},
            },
        ]
    )
    return workflow


def _execute(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> tuple[Any, InMemoryEventStore]:
    store = InMemoryEventStore(schema_bundle)
    run = execute_workflow(
        workflow,
        {"text": "hello world"},
        run_id="run_error",
        event_store=store,
        event_factory=EventFactory(
            clock=sequence_fixture._WallClock(),
            event_id_factory=sequence_fixture._Ids(),
        ),
        schema_bundle=schema_bundle,
        monotonic_clock=sequence_fixture._Ticks(),
    )
    return run, store


def _queued_nodes(store: InMemoryEventStore) -> list[str | None]:
    return [
        event.node_id
        for event in store.load("run_error")
        if event.type is EventType.NODE_QUEUED
    ]


def _event_error_codes(store: InMemoryEventStore) -> list[str]:
    return [
        event.payload.error.code
        for event in store.load("run_error")
        if event.payload.error is not None
    ]


def test_exact_code_has_priority_over_matching_category(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _error_workflow()
    run, store = _execute(workflow, schema_bundle)

    assert run.status is RunStatus.FAILED
    assert "code_error_terminal" in _queued_nodes(store)
    assert "category_error_terminal" not in _queued_nodes(store)
    error_queue = next(
        event
        for event in store.load("run_error")
        if event.type is EventType.NODE_QUEUED
        and event.node_id == "code_error_terminal"
    )
    runtime = error_queue.payload.details["runtime"]
    assert runtime["incoming_edge_id"] == "edge_error_code"
    assert runtime["normalized_error_code"] == "NODE_OUTPUT_INVALID"
    assert project_run(
        workflow,
        store.load("run_error"),
        schema_bundle=schema_bundle,
    ) == run


def test_category_is_used_only_when_no_exact_code_matches(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _error_workflow()
    workflow["edges"][-2]["match"] = {"codes": ["OTHER_ERROR"]}
    _, store = _execute(workflow, schema_bundle)

    assert "category_error_terminal" in _queued_nodes(store)
    assert "code_error_terminal" not in _queued_nodes(store)


def test_no_error_match_terminates_with_the_normalized_node_error(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _error_workflow()
    workflow["edges"][-2]["match"] = {"codes": ["OTHER_ERROR"]}
    workflow["edges"][-1]["match"] = {"categories": ["internal"]}
    run, store = _execute(workflow, schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _event_error_codes(store)[-1] == "NODE_OUTPUT_INVALID"
    assert "code_error_terminal" not in _queued_nodes(store)
    assert "category_error_terminal" not in _queued_nodes(store)


def test_multiple_exact_matches_fail_without_category_fallback(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _error_workflow()
    workflow["edges"][-1]["match"] = {"codes": ["NODE_OUTPUT_INVALID"]}
    run, store = _execute(workflow, schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _event_error_codes(store)[-1] == "EDGE_SELECTION_AMBIGUOUS"
    assert "code_error_terminal" not in _queued_nodes(store)
    assert "category_error_terminal" not in _queued_nodes(store)


def test_multiple_category_matches_are_ambiguous(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _error_workflow()
    workflow["edges"][-2]["match"] = {"categories": ["validation"]}
    run, store = _execute(workflow, schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _event_error_codes(store)[-1] == "EDGE_SELECTION_AMBIGUOUS"


def test_output_rejection_never_queues_the_success_gate(
    schema_bundle: SchemaBundle,
) -> None:
    _, store = _execute(_error_workflow(), schema_bundle)
    events = store.load("run_error")
    event_types = [event.type for event in events if event.node_id == "evaluation"]

    assert EventType.NODE_INPUT_VALIDATED in event_types
    assert EventType.NODE_OUTPUT_REJECTED in event_types
    assert EventType.NODE_OUTPUT_VALIDATED not in event_types
    assert EventType.NODE_SUCCEEDED not in event_types
    assert "length_gate" not in _queued_nodes(store)


def test_unknown_exception_is_normalized_without_raw_text(
    schema_bundle: SchemaBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _error_workflow()
    workflow["nodes"][2]["outputs"]["schema"]["properties"]["case"] = {
        "enum": ["qualified", "retry"]
    }
    workflow["edges"][-2]["match"] = {"codes": ["NODE_INTERNAL_ERROR"]}
    workflow["edges"][-1]["match"] = {"categories": ["internal"]}
    original = engine_module.execute_node_handler

    def explode(node: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        if node["id"] == "evaluation":
            raise RuntimeError("password=never-store-this C:/private/path")
        return original(node, *args, **kwargs)

    monkeypatch.setattr(engine_module, "execute_node_handler", explode)
    _, store = _execute(workflow, schema_bundle)
    serialized = json.dumps(
        [event.model_dump(mode="json") for event in store.load("run_error")],
        ensure_ascii=False,
    )

    assert "NODE_INTERNAL_ERROR" in _event_error_codes(store)
    assert "never-store-this" not in serialized
    assert "C:/private/path" not in serialized
    assert "code_error_terminal" in _queued_nodes(store)


def test_error_details_are_redacted_and_bounded() -> None:
    details = {
        "token": "sensitive-token",
        "nested": {"password": "sensitive-password", "safe": "x" * 400},
        "items": list(range(40)),
    }

    sanitized = sanitize_error_details(details)

    assert sanitized is not None
    assert sanitized["token"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert len(sanitized["nested"]["safe"]) == 256
    assert sanitized["items"][-1] == "[TRUNCATED]"
