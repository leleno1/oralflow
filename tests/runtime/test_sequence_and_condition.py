from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from oralflow.domain import Event, EventType, RunStatus
from oralflow.events import (
    EventFactory,
    EventSequenceConflict,
    EventStore,
    InMemoryEventStore,
)
from oralflow.runtime.engine import EngineError, execute_workflow
from oralflow.runtime.projection import project_run
from oralflow.validators.schema import SchemaBundle, load_schema_bundle

ROOT = Path(__file__).resolve().parents[2]
START = datetime.fromisoformat("2026-07-31T20:30:00+08:00")


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"event_exec_{self.value:03d}"


class _WallClock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> datetime:
        self.value += 1
        return START + timedelta(seconds=self.value)


class _Ticks:
    def __init__(self, values: list[float] | None = None) -> None:
        self.values = iter(values or [])
        self.last = 0.0

    def __call__(self) -> float:
        self.last = next(self.values, self.last)
        return self.last


class _ConflictingStore(EventStore):
    def append(self, event: Event, expected_last_sequence: int) -> None:
        raise EventSequenceConflict("synthetic conflict")

    def load(self, run_id: str) -> tuple[Event, ...]:
        return ()

    def last_sequence(self, run_id: str) -> int:
        return 0


@pytest.fixture
def schema_bundle() -> SchemaBundle:
    return load_schema_bundle(ROOT / "schemas")


def _contract(
    *,
    bindings: dict[str, Any],
    input_schema: dict[str, Any],
    config: dict[str, Any],
    config_schema: dict[str, Any],
    destinations: dict[str, str],
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    return {
        "inputs": {"bindings": bindings, "schema": input_schema},
        "config": {"values": config, "schema": config_schema},
        "outputs": {"destinations": destinations, "schema": output_schema},
        "error_contract": {
            "allowed_codes": ["NODE_INPUT_INVALID", "NODE_OUTPUT_INVALID"],
            "allowed_categories": ["validation"],
            "retryable_codes": [],
            "schema": {"type": "object"},
        },
        "execution_policy": {
            "timeout_seconds": 30,
            "max_attempts": 1,
            "exit_conditions": ["the deterministic handler succeeds or fails"],
            "escalation_condition": "the declared contract cannot be satisfied",
        },
        "permissions": {"write_paths": [], "command_classes": [], "network": False},
        "metadata": {},
    }


def _node(node_id: str, kind: str, name: str, **contract: Any) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "id": node_id,
        "kind": kind,
        "name": name,
        **contract,
    }


def _workflow() -> dict[str, Any]:
    text_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {"text": {"type": "string"}},
        "additionalProperties": False,
    }
    evaluation_schema = {
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
    case_schema = {
        "type": "object",
        "required": ["case"],
        "properties": {"case": {"enum": ["qualified", "retry"]}},
        "additionalProperties": False,
    }
    empty_schema = {"type": "object", "additionalProperties": False}
    entry = _node(
        "text_input",
        "input",
        "Receive text",
        source="system",
        **_contract(
            bindings={"text": {"ref": "workflow-input://text"}},
            input_schema=text_schema,
            config={},
            config_schema=empty_schema,
            destinations={"text": "node-output://text_input/text"},
            output_schema=text_schema,
        ),
    )
    uppercase = _node(
        "uppercase",
        "transform",
        "Uppercase text",
        **_contract(
            bindings={"text": {"ref": "node-output://text_input/text"}},
            input_schema=text_schema,
            config={"transform_id": "uppercase"},
            config_schema={
                "type": "object",
                "required": ["transform_id"],
                "properties": {"transform_id": {"const": "uppercase"}},
                "additionalProperties": False,
            },
            destinations={"text": "node-output://uppercase/text"},
            output_schema=text_schema,
        ),
    )
    evaluation = _node(
        "evaluation",
        "transform",
        "Evaluate length",
        **_contract(
            bindings={"text": {"ref": "node-output://uppercase/text"}},
            input_schema=text_schema,
            config={"transform_id": "length_evaluation", "minimum_length": 5},
            config_schema={
                "type": "object",
                "required": ["transform_id", "minimum_length"],
                "properties": {
                    "transform_id": {"const": "length_evaluation"},
                    "minimum_length": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            destinations={
                "text": "node-output://evaluation/text",
                "length": "node-output://evaluation/length",
                "threshold": "node-output://evaluation/threshold",
                "case": "node-output://evaluation/case",
            },
            output_schema=evaluation_schema,
        ),
    )
    gate = _node(
        "length_gate",
        "gate",
        "Select length branch",
        condition={"language": "oralflow-expression-0.1", "expression": "case"},
        **_contract(
            bindings={"case": {"ref": "node-output://evaluation/case"}},
            input_schema=case_schema,
            config={},
            config_schema=empty_schema,
            destinations={"case": "node-output://length_gate/case"},
            output_schema=case_schema,
        ),
    )

    def terminal(node_id: str, outcome: str) -> dict[str, Any]:
        return _node(
            node_id,
            "terminal",
            f"Terminal {outcome}",
            outcome=outcome,
            **_contract(
                bindings={"case": {"ref": "node-output://length_gate/case"}},
                input_schema=case_schema,
                config={},
                config_schema=empty_schema,
                destinations={},
                output_schema=empty_schema,
            ),
        )

    edges = [
        {
            "id": "edge_input_uppercase",
            "kind": "sequence",
            "from": {"node_id": "text_input", "port": "text"},
            "to": {"node_id": "uppercase", "port": "text"},
        },
        {
            "id": "edge_uppercase_evaluation",
            "kind": "sequence",
            "from": {"node_id": "uppercase", "port": "text"},
            "to": {"node_id": "evaluation", "port": "text"},
        },
        {
            "id": "edge_evaluation_gate",
            "kind": "sequence",
            "from": {"node_id": "evaluation", "port": "case"},
            "to": {"node_id": "length_gate", "port": "case"},
        },
        {
            "id": "edge_gate_complete",
            "kind": "conditional",
            "from": {"node_id": "length_gate", "port": "case"},
            "to": {"node_id": "complete", "port": "case"},
            "condition": {
                "language": "oralflow-expression-0.1",
                "expression": "case",
                "case": "qualified",
            },
        },
        {
            "id": "edge_gate_failed",
            "kind": "conditional",
            "from": {"node_id": "length_gate", "port": "case"},
            "to": {"node_id": "failed", "port": "case"},
            "condition": {
                "language": "oralflow-expression-0.1",
                "expression": "case",
                "case": "retry",
            },
        },
    ]
    return {
        "schema_version": "0.1.0",
        "workflow_id": "wf_sequence_condition",
        "workflow_version": "0.1.0",
        "revision": "rev_001",
        "name": "M1 sequence and condition fixture",
        "goal": "Exercise deterministic sequence and conditional routing.",
        "status": "draft",
        "inputs": {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
        "roles": [],
        "nodes": [
            entry,
            uppercase,
            evaluation,
            gate,
            terminal("complete", "success"),
            terminal("failed", "failure"),
        ],
        "edges": edges,
        "policies": {
            "max_total_transitions": 6,
            "max_duration_seconds": 60,
            "max_failures": 1,
            "max_replans": 0,
            "max_children": 0,
            "max_subworkflow_depth": 3,
            "human_escalation_condition": "a deterministic boundary cannot continue",
        },
        "success_criteria": [
            {
                "id": "terminal_reached",
                "description": "One declared terminal is reached.",
                "verification": "automatic",
                "expression": "terminal.outcome == 'success'",
            }
        ],
        "metadata": {"description": "Synthetic M1 executor fixture", "tags": ["m1"]},
    }


def _execute(
    workflow: dict[str, Any],
    text: str,
    schema_bundle: SchemaBundle,
    *,
    run_id: str = "run_exec",
    store: EventStore | None = None,
    ticks: _Ticks | None = None,
) -> tuple[Any, EventStore]:
    selected_store = store or InMemoryEventStore(schema_bundle)
    run = execute_workflow(
        workflow,
        {"text": text},
        run_id=run_id,
        event_store=selected_store,
        event_factory=EventFactory(clock=_WallClock(), event_id_factory=_Ids()),
        schema_bundle=schema_bundle,
        monotonic_clock=ticks or _Ticks(),
    )
    return run, selected_store


def _failure_code(store: EventStore, run_id: str = "run_exec") -> str | None:
    error = store.load(run_id)[-1].payload.error
    return error.code if error is not None else None


def test_qualifying_input_completes_with_replayable_transition_facts(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    run, store = _execute(workflow, "hello world", schema_bundle)
    events = store.load(run.run_id)

    assert run.status is RunStatus.COMPLETED
    assert run.budget.used_transitions == 4
    assert [event.type for event in events[:3]] == [
        EventType.WORKFLOW_VALIDATION_STARTED,
        EventType.WORKFLOW_VALIDATION_COMPLETED,
        EventType.RUN_STARTED,
    ]
    queued = [event for event in events if event.type is EventType.NODE_QUEUED]
    assert [event.node_id for event in queued] == [
        "text_input",
        "uppercase",
        "evaluation",
        "length_gate",
        "complete",
    ]
    assert [
        event.payload.details["runtime"].get("transition_index")
        for event in queued
    ] == [None, 1, 2, 3, 4]
    assert project_run(workflow, events, schema_bundle=schema_bundle) == run


def test_short_input_selects_the_exact_failure_case(schema_bundle: SchemaBundle) -> None:
    run, store = _execute(_workflow(), "x", schema_bundle)
    events = store.load(run.run_id)

    assert run.status is RunStatus.FAILED
    failed_queue = next(
        event
        for event in events
        if event.type is EventType.NODE_QUEUED and event.node_id == "failed"
    )
    assert failed_queue.payload.details["runtime"]["incoming_edge_id"] == (
        "edge_gate_failed"
    )
    assert events[-1].payload.reason == "Terminal node declared failure"


def test_repeat_execution_is_equal_and_inputs_are_immutable(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    inputs = {"text": "hello world"}
    original_workflow = deepcopy(workflow)
    original_inputs = deepcopy(inputs)

    first_store = InMemoryEventStore(schema_bundle)
    first = execute_workflow(
        workflow,
        inputs,
        run_id="run_exec",
        event_store=first_store,
        event_factory=EventFactory(clock=_WallClock(), event_id_factory=_Ids()),
        schema_bundle=schema_bundle,
        monotonic_clock=_Ticks(),
    )
    second_store = InMemoryEventStore(schema_bundle)
    second = execute_workflow(
        workflow,
        inputs,
        run_id="run_exec",
        event_store=second_store,
        event_factory=EventFactory(clock=_WallClock(), event_id_factory=_Ids()),
        schema_bundle=schema_bundle,
        monotonic_clock=_Ticks(),
    )

    assert first == second
    assert first_store.load("run_exec") == second_store.load("run_exec")
    assert workflow == original_workflow
    assert inputs == original_inputs


def test_gate_case_without_a_match_fails_without_queueing_a_terminal(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    workflow["edges"][4]["condition"]["case"] = "other"
    workflow["nodes"][3]["outputs"]["schema"]["properties"]["case"]["enum"].append(
        "other"
    )
    run, store = _execute(workflow, "x", schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _failure_code(store) == "EDGE_SELECTION_NONE"
    assert all(
        event.node_id not in {"complete", "failed"}
        for event in store.load(run.run_id)
        if event.type is EventType.NODE_QUEUED
    )


def test_duplicate_sequence_candidates_fail_during_preflight(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    duplicate = deepcopy(workflow["edges"][0])
    duplicate["id"] = "edge_input_evaluation"
    duplicate["to"] = {"node_id": "evaluation", "port": "text"}
    workflow["edges"].append(duplicate)
    run, store = _execute(workflow, "hello", schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _failure_code(store) == "EDGE_SELECTION_AMBIGUOUS"
    assert [event.type for event in store.load(run.run_id)] == [
        EventType.WORKFLOW_VALIDATION_STARTED,
        EventType.WORKFLOW_VALIDATION_FAILED,
    ]


def test_duplicate_conditional_case_fails_during_preflight(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    workflow["edges"][4]["condition"]["case"] = "qualified"
    run, store = _execute(workflow, "hello", schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _failure_code(store) == "EDGE_SELECTION_AMBIGUOUS"


def test_zero_exit_is_a_stable_static_preflight_failure(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    workflow["edges"] = [
        edge for edge in workflow["edges"] if edge["from"]["node_id"] != "uppercase"
    ]
    run, store = _execute(workflow, "hello", schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _failure_code(store) == "WORKFLOW_VALIDATION_FAILED"


def test_transition_budget_fails_before_queueing_the_next_node(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    workflow["policies"]["max_total_transitions"] = 3
    run, store = _execute(workflow, "hello world", schema_bundle)

    assert run.status is RunStatus.FAILED
    assert run.budget.used_transitions == 3
    assert _failure_code(store) == "RUN_BUDGET_EXHAUSTED"
    assert all(event.node_id != "complete" for event in store.load(run.run_id))


def test_duration_budget_fails_at_a_node_boundary(schema_bundle: SchemaBundle) -> None:
    workflow = _workflow()
    workflow["policies"]["max_duration_seconds"] = 1
    ticks = _Ticks([0.0, 0.0, 0.0, 2.0])
    run, store = _execute(workflow, "hello world", schema_bundle, ticks=ticks)

    assert run.status is RunStatus.FAILED
    assert run.budget.elapsed_seconds == 2.0
    assert _failure_code(store) == "RUN_BUDGET_EXHAUSTED"


def test_oversized_inline_input_is_rejected_with_complete_failure_events(
    schema_bundle: SchemaBundle,
) -> None:
    run, store = _execute(_workflow(), "x" * (16 * 1024), schema_bundle)
    events = store.load(run.run_id)

    assert run.status is RunStatus.FAILED
    assert _failure_code(store) == "INLINE_EVENT_DATA_LIMIT_EXCEEDED"
    assert EventType.NODE_INPUT_REJECTED in [event.type for event in events]
    assert events[-1].type is EventType.RUN_FAILED


def test_unsupported_node_is_rejected_before_any_node_event(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    workflow["nodes"][1]["kind"] = "command"
    workflow["nodes"][1]["command_id"] = "synthetic_command"
    run, store = _execute(workflow, "hello", schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _failure_code(store) == "NODE_KIND_UNSUPPORTED"
    assert not any(event.node_id for event in store.load(run.run_id))


def test_retry_edge_is_rejected_in_the_sequence_condition_loop(
    schema_bundle: SchemaBundle,
) -> None:
    workflow = _workflow()
    edge = workflow["edges"][0]
    edge["kind"] = "retry"
    edge["retry"] = {
        "max_traversals": 1,
        "backoff": {"strategy": "none", "initial_seconds": 0, "max_seconds": 0},
        "on_exhausted": "fail",
    }
    run, store = _execute(workflow, "hello", schema_bundle)

    assert run.status is RunStatus.FAILED
    assert _failure_code(store) == "EDGE_KIND_UNSUPPORTED"


def test_schema_failure_appends_nothing(schema_bundle: SchemaBundle) -> None:
    workflow = _workflow()
    del workflow["goal"]
    store = InMemoryEventStore(schema_bundle)

    with pytest.raises(EngineError) as captured:
        _execute(workflow, "hello", schema_bundle, store=store)

    assert captured.value.code == "WORKFLOW_SCHEMA_INVALID"
    assert store.load("run_exec") == ()


def test_event_sequence_conflict_is_not_retried(schema_bundle: SchemaBundle) -> None:
    store = _ConflictingStore()

    with pytest.raises(EngineError) as captured:
        _execute(_workflow(), "hello", schema_bundle, store=store)

    assert captured.value.code == "EVENT_SEQUENCE_CONFLICT"
