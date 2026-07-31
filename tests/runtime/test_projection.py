from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from oralflow.domain import (
    ErrorCategory,
    Event,
    EventPayload,
    EventType,
    NodeRunStatus,
    RunStatus,
    StructuredError,
    to_schema_instance,
    workflow_digest,
)
from oralflow.runtime import ProjectionError, project_run
from oralflow.validators.schema import SchemaBundle, load_schema_bundle, validate_instance

ROOT = Path(__file__).resolve().parents[2]
START = datetime.fromisoformat("2026-07-31T19:00:00+08:00")


@pytest.fixture
def schema_bundle() -> SchemaBundle:
    return load_schema_bundle(ROOT / "schemas")


@pytest.fixture
def workflow() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(
        (ROOT / "examples" / "minimal-child-workflow.json").read_text(encoding="utf-8")
    )
    return value


def _workflow_ref(workflow: dict[str, Any]) -> dict[str, str]:
    return {
        "workflow_id": workflow["workflow_id"],
        "workflow_version": workflow["workflow_version"],
        "revision": workflow["revision"],
        "digest": workflow_digest(workflow),
    }


def _runtime_payload(**runtime: Any) -> EventPayload:
    return EventPayload(details={"runtime": {"semantics_version": "0.1.0", **runtime}})


def _event(
    workflow: dict[str, Any],
    sequence: int,
    event_type: EventType,
    *,
    node_id: str | None = None,
    payload: EventPayload | None = None,
    run_id: str = "run_projection",
    event_id: str | None = None,
) -> Event:
    return Event(
        event_id=event_id or f"event_projection_{sequence:03d}",
        sequence=sequence,
        run_id=run_id,
        workflow_id=workflow["workflow_id"],
        workflow_revision=workflow["revision"],
        node_id=node_id,
        type=event_type,
        timestamp=START + timedelta(seconds=sequence),
        correlation_id=run_id,
        payload=payload or EventPayload(),
    )


def _success_events(workflow: dict[str, Any]) -> tuple[Event, ...]:
    return (
        _event(
            workflow,
            1,
            EventType.WORKFLOW_VALIDATION_STARTED,
            payload=_runtime_payload(workflow_ref=_workflow_ref(workflow)),
        ),
        _event(workflow, 2, EventType.WORKFLOW_VALIDATION_COMPLETED),
        _event(workflow, 3, EventType.RUN_STARTED),
        _event(
            workflow,
            4,
            EventType.NODE_QUEUED,
            node_id="child_input",
            payload=EventPayload(attempt=1),
        ),
        _event(workflow, 5, EventType.NODE_STARTED, node_id="child_input"),
        _event(workflow, 6, EventType.NODE_INPUT_VALIDATED, node_id="child_input"),
        _event(workflow, 7, EventType.NODE_OUTPUT_VALIDATED, node_id="child_input"),
        _event(
            workflow,
            8,
            EventType.NODE_SUCCEEDED,
            node_id="child_input",
            payload=EventPayload(artifact_refs=("artifact://projection/input.json",)),
        ),
        _event(
            workflow,
            9,
            EventType.NODE_QUEUED,
            node_id="child_complete",
            payload=EventPayload(
                attempt=1,
                details={
                    "runtime": {
                        "semantics_version": "0.1.0",
                        "incoming_edge_id": "edge_child_complete",
                        "transition_index": 1,
                        "budget": {
                            "elapsed_seconds": 2.5,
                            "used_transitions": 1,
                            "used_tool_calls": 0,
                        },
                    }
                },
            ),
        ),
        _event(workflow, 10, EventType.NODE_STARTED, node_id="child_complete"),
        _event(workflow, 11, EventType.NODE_SUCCEEDED, node_id="child_complete"),
        _event(workflow, 12, EventType.RUN_COMPLETED),
    )


def test_complete_history_projects_one_schema_valid_run(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    events = _success_events(workflow)

    projected = project_run(workflow, events, schema_bundle=schema_bundle)

    assert projected.status is RunStatus.COMPLETED
    assert projected.attempt_count == 1
    assert projected.last_event_sequence == 12
    assert projected.budget.used_transitions == 1
    assert projected.budget.elapsed_seconds == 2.5
    assert projected.artifact_refs == ("artifact://projection/input.json",)
    assert tuple(node.status for node in projected.node_runs) == (
        NodeRunStatus.SUCCEEDED,
        NodeRunStatus.SUCCEEDED,
    )
    report = validate_instance(
        to_schema_instance(projected),
        "urn:oralflow:schema:run:0.1.0",
        schema_bundle,
    )
    assert report.valid, report.as_dict()


@pytest.mark.parametrize(
    ("length", "run_status", "node_status"),
    [
        (1, RunStatus.VALIDATING, NodeRunStatus.IDLE),
        (2, RunStatus.READY, NodeRunStatus.IDLE),
        (5, RunStatus.RUNNING, NodeRunStatus.RUNNING),
    ],
)
def test_truncated_history_projects_exact_checkpoint(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
    length: int,
    run_status: RunStatus,
    node_status: NodeRunStatus,
) -> None:
    projected = project_run(
        workflow,
        _success_events(workflow)[:length],
        schema_bundle=schema_bundle,
    )

    assert projected.status is run_status
    assert projected.node_runs[0].status is node_status
    assert projected.last_event_sequence == length


def test_replay_is_deterministic_and_does_not_mutate_inputs(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    events = _success_events(workflow)
    original_workflow = deepcopy(workflow)
    original_events = tuple(event.model_copy(deep=True) for event in events)

    first = project_run(workflow, events, schema_bundle=schema_bundle)
    second = project_run(workflow, events, schema_bundle=schema_bundle)

    assert first == second
    assert to_schema_instance(first) == to_schema_instance(second)
    assert workflow == original_workflow
    assert events == original_events


def test_pause_and_resume_project_waiting_and_running_states(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    prefix = _success_events(workflow)[:4]
    paused = _event(
        workflow,
        5,
        EventType.RUN_PAUSED,
        payload=_runtime_payload(pause={"reason": "input_required"}),
    )
    resumed = _event(workflow, 6, EventType.RUN_RESUMED)

    waiting = project_run(workflow, (*prefix, paused), schema_bundle=schema_bundle)
    running = project_run(
        workflow,
        (*prefix, paused, resumed),
        schema_bundle=schema_bundle,
    )

    assert waiting.status is RunStatus.WAITING_FOR_USER
    assert running.status is RunStatus.RUNNING


def test_node_failure_projects_structured_last_error(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    prefix = _success_events(workflow)[:5]
    failed = _event(
        workflow,
        6,
        EventType.NODE_FAILED,
        node_id="child_input",
        payload=EventPayload(
            error=StructuredError(
                code="NODE_INPUT_INVALID",
                message="Synthetic invalid input.",
                category=ErrorCategory.VALIDATION,
                retryable=True,
            )
        ),
    )
    run_failed = _event(workflow, 7, EventType.RUN_FAILED)

    projected = project_run(
        workflow,
        (*prefix, failed, run_failed),
        schema_bundle=schema_bundle,
    )

    node = projected.node_runs[0]
    assert projected.status is RunStatus.FAILED
    assert node.status is NodeRunStatus.RETRYABLE_FAILED
    assert node.last_error is not None
    assert node.last_error.code == "NODE_INPUT_INVALID"
    assert node.last_error.cause_event_id == failed.event_id


def test_empty_history_is_rejected(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    with pytest.raises(ProjectionError) as captured:
        project_run(workflow, (), schema_bundle=schema_bundle)
    assert captured.value.code == "PROJECTION_EVENT_STREAM_EMPTY"


@pytest.mark.parametrize("bad_sequence", [0, 2, 3])
def test_non_continuous_sequence_is_rejected(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
    bad_sequence: int,
) -> None:
    first = _success_events(workflow)[0].model_copy(update={"sequence": bad_sequence})
    with pytest.raises(ProjectionError) as captured:
        project_run(workflow, (first,), schema_bundle=schema_bundle)
    assert captured.value.code in {"EVENT_SCHEMA_INVALID", "EVENT_SEQUENCE_CONFLICT"}


def test_duplicate_event_id_and_identity_drift_are_rejected(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    first, second = _success_events(workflow)[:2]
    duplicate = second.model_copy(update={"event_id": first.event_id})
    with pytest.raises(ProjectionError) as duplicate_error:
        project_run(workflow, (first, duplicate), schema_bundle=schema_bundle)
    assert duplicate_error.value.code == "EVENT_ID_CONFLICT"

    drifted = second.model_copy(update={"run_id": "run_other"})
    with pytest.raises(ProjectionError) as identity_error:
        project_run(workflow, (first, drifted), schema_bundle=schema_bundle)
    assert identity_error.value.code == "EVENT_IDENTITY_CONFLICT"


def test_pinned_digest_mismatch_is_rejected(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    first = _success_events(workflow)[0]
    bad_ref = {**_workflow_ref(workflow), "digest": "0" * 64}
    changed = first.model_copy(
        update={"payload": _runtime_payload(workflow_ref=bad_ref)},
        deep=True,
    )

    with pytest.raises(ProjectionError) as captured:
        project_run(workflow, (changed,), schema_bundle=schema_bundle)
    assert captured.value.code == "WORKFLOW_DIGEST_MISMATCH"


def test_unknown_node_and_illegal_run_transition_are_rejected(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    events = list(_success_events(workflow)[:4])
    events[-1] = events[-1].model_copy(update={"node_id": "unknown_node"})
    with pytest.raises(ProjectionError) as node_error:
        project_run(workflow, events, schema_bundle=schema_bundle)
    assert node_error.value.code == "NODE_REFERENCE_UNKNOWN"

    first, second = _success_events(workflow)[:2]
    completed = _event(workflow, 3, EventType.RUN_COMPLETED)
    with pytest.raises(ProjectionError) as transition_error:
        project_run(workflow, (first, second, completed), schema_bundle=schema_bundle)
    assert transition_error.value.code == "EVENT_TRANSITION_INVALID"


def test_terminal_run_rejects_later_events(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    events = _success_events(workflow)
    resumed = _event(workflow, 13, EventType.RUN_RESUMED)

    with pytest.raises(ProjectionError) as captured:
        project_run(workflow, (*events, resumed), schema_bundle=schema_bundle)
    assert captured.value.code == "EVENT_TRANSITION_INVALID"


def test_node_failed_requires_error_and_unsupported_event_is_rejected(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    prefix = _success_events(workflow)[:5]
    missing_error = _event(
        workflow,
        6,
        EventType.NODE_FAILED,
        node_id="child_input",
    )
    with pytest.raises(ProjectionError) as error_required:
        project_run(workflow, (*prefix, missing_error), schema_bundle=schema_bundle)
    assert error_required.value.code == "EVENT_TRANSITION_INVALID"

    observation = Event(
        event_id="event_observation",
        sequence=4,
        run_id="run_projection",
        workflow_id=workflow["workflow_id"],
        workflow_revision=workflow["revision"],
        role_id="observer",
        type=EventType.OBSERVATION_RECORDED,
        timestamp=START + timedelta(seconds=4),
        payload=EventPayload(),
    )
    with pytest.raises(ProjectionError) as unsupported:
        project_run(
            workflow,
            (*_success_events(workflow)[:3], observation),
            schema_bundle=schema_bundle,
        )
    assert unsupported.value.code == "EVENT_TYPE_UNSUPPORTED"


def test_transition_and_budget_counters_cannot_disagree_or_decrease(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    events = list(_success_events(workflow)[:9])
    bad_payload = EventPayload(
        attempt=1,
        details={
            "runtime": {
                "incoming_edge_id": "edge_child_complete",
                "transition_index": 1,
                "budget": {"used_transitions": 0},
            }
        },
    )
    events[-1] = events[-1].model_copy(update={"payload": bad_payload}, deep=True)

    with pytest.raises(ProjectionError) as captured:
        project_run(workflow, events, schema_bundle=schema_bundle)
    assert captured.value.code == "EVENT_COUNTER_INVALID"


def test_retry_counter_is_replayed_and_cannot_exceed_declared_bound(
    schema_bundle: SchemaBundle,
) -> None:
    workflow: dict[str, Any] = json.loads(
        (ROOT / "examples" / "minimal-workflow.json").read_text(encoding="utf-8")
    )
    prefix = (
        _event(
            workflow,
            1,
            EventType.WORKFLOW_VALIDATION_STARTED,
            payload=_runtime_payload(workflow_ref=_workflow_ref(workflow)),
        ),
        _event(workflow, 2, EventType.WORKFLOW_VALIDATION_COMPLETED),
        _event(workflow, 3, EventType.RUN_STARTED),
        _event(
            workflow,
            4,
            EventType.NODE_QUEUED,
            node_id="mock_review",
            payload=EventPayload(attempt=1),
        ),
        _event(workflow, 5, EventType.NODE_STARTED, node_id="mock_review"),
        _event(
            workflow,
            6,
            EventType.NODE_FAILED,
            node_id="mock_review",
            payload=EventPayload(
                error=StructuredError(
                    code="MOCK_PROVIDER_FAILURE",
                    message="Synthetic retryable failure.",
                    category=ErrorCategory.PROVIDER,
                    retryable=True,
                )
            ),
        ),
    )
    retry_payload = EventPayload(
        attempt=2,
        details={
            "runtime": {
                "incoming_edge_id": "edge_gate_retry",
                "transition_index": 1,
                "retry": {
                    "edge_id": "edge_gate_retry",
                    "traversal": 1,
                    "max_traversals": 1,
                },
            }
        },
    )
    retry_event = _event(
        workflow,
        7,
        EventType.NODE_QUEUED,
        node_id="mock_review",
        payload=retry_payload,
    )

    projected = project_run(
        workflow,
        (*prefix, retry_event),
        schema_bundle=schema_bundle,
    )
    review_node = next(node for node in projected.node_runs if node.node_id == "mock_review")
    assert review_node.status is NodeRunStatus.QUEUED
    assert review_node.attempt_count == 2
    assert projected.budget.used_transitions == 1

    exceeded = retry_event.model_copy(
        update={
            "payload": EventPayload(
                attempt=2,
                details={
                    "runtime": {
                        "incoming_edge_id": "edge_gate_retry",
                        "transition_index": 1,
                        "retry": {
                            "edge_id": "edge_gate_retry",
                            "traversal": 2,
                            "max_traversals": 1,
                        },
                    }
                },
            )
        },
        deep=True,
    )
    with pytest.raises(ProjectionError) as captured:
        project_run(workflow, (*prefix, exceeded), schema_bundle=schema_bundle)
    assert captured.value.code == "EVENT_COUNTER_INVALID"


def test_duplicate_workflow_node_ids_are_rejected_during_replay(
    workflow: dict[str, Any],
    schema_bundle: SchemaBundle,
) -> None:
    duplicated = deepcopy(workflow)
    duplicated["nodes"].append(deepcopy(duplicated["nodes"][0]))
    events = _success_events(duplicated)[:1]

    with pytest.raises(ProjectionError) as captured:
        project_run(duplicated, events, schema_bundle=schema_bundle)
    assert captured.value.code == "WORKFLOW_SCHEMA_INVALID"
