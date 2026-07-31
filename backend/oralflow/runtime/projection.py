"""Pure M1 Run projection from one Workflow definition and ordered Events."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, NoReturn

from pydantic import ValidationError

from oralflow.domain.runtime import (
    BudgetUsage,
    Event,
    EventType,
    JsonObject,
    NodeRun,
    NodeRunStatus,
    PinnedWorkflowRef,
    Run,
    RunError,
    RunMetadata,
    RunStatus,
    to_schema_instance,
    workflow_digest,
)
from oralflow.validators.schema import SchemaBundle, validate_instance

WORKFLOW_SCHEMA_ID = "urn:oralflow:schema:workflow:0.1.0"
EVENT_SCHEMA_ID = "urn:oralflow:schema:event:0.1.0"
RUN_SCHEMA_ID = "urn:oralflow:schema:run:0.1.0"

_VALIDATION_EVENT_TYPES = frozenset(
    {
        EventType.WORKFLOW_VALIDATION_STARTED,
        EventType.WORKFLOW_VALIDATION_COMPLETED,
        EventType.WORKFLOW_VALIDATION_FAILED,
    }
)
_RUN_EVENT_TYPES = frozenset(
    {
        EventType.RUN_STARTED,
        EventType.RUN_PAUSED,
        EventType.RUN_RESUMED,
        EventType.RUN_COMPLETED,
        EventType.RUN_FAILED,
        EventType.RUN_CANCELLED,
    }
)
_NODE_EVENT_TYPES = frozenset(
    {
        EventType.NODE_QUEUED,
        EventType.NODE_STARTED,
        EventType.NODE_INPUT_VALIDATED,
        EventType.NODE_INPUT_REJECTED,
        EventType.NODE_OUTPUT_VALIDATED,
        EventType.NODE_OUTPUT_REJECTED,
        EventType.NODE_SUCCEEDED,
        EventType.NODE_FAILED,
        EventType.NODE_SKIPPED,
        EventType.NODE_CANCELLED,
    }
)
_REQUEUEABLE_NODE_STATES = frozenset(
    {
        NodeRunStatus.IDLE,
        NodeRunStatus.SUCCEEDED,
        NodeRunStatus.REJECTED,
        NodeRunStatus.RETRYABLE_FAILED,
    }
)


class ProjectionError(RuntimeError):
    """Stable failure raised when an Event history cannot be projected."""

    default_code: ClassVar[str] = "PROJECTION_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or self.default_code


@dataclass(slots=True)
class _ProjectionState:
    status: RunStatus | None
    nodes: dict[str, NodeRun]
    node_order: tuple[str, ...]
    budget: BudgetUsage
    attempt_count: int = 0
    artifact_refs: list[str] = field(default_factory=list)
    completed_at: datetime | None = None
    retry_counts: dict[str, int] = field(default_factory=dict)


def _fail(code: str, message: str) -> NoReturn:
    raise ProjectionError(message, code=code)


def _schema_check(
    instance: JsonObject,
    schema_id: str,
    schema_bundle: SchemaBundle,
    error_code: str,
) -> None:
    report = validate_instance(instance, schema_id, schema_bundle)
    if report.valid:
        return
    paths = ", ".join(issue.instance_path or "/" for issue in report.issues)
    _fail(error_code, f"{schema_id} validation failed at: {paths}")


def _runtime_details(event: Event) -> JsonObject:
    details = event.payload.details
    if details is None or "runtime" not in details:
        return {}
    runtime = details["runtime"]
    if not isinstance(runtime, dict):
        _fail(
            "EVENT_TRANSITION_INVALID",
            f"Event sequence {event.sequence} has a non-object payload.details.runtime",
        )
    return runtime


def _read_workflow_identity(workflow: JsonObject) -> tuple[str, str, str]:
    workflow_id = workflow.get("workflow_id")
    workflow_version = workflow.get("workflow_version")
    revision = workflow.get("revision")
    if (
        not isinstance(workflow_id, str)
        or not isinstance(workflow_version, str)
        or not isinstance(revision, str)
    ):
        _fail("WORKFLOW_SCHEMA_INVALID", "Workflow identity fields must be strings")
    return workflow_id, workflow_version, revision


def _read_nodes(workflow: JsonObject) -> tuple[tuple[str, ...], dict[str, NodeRun]]:
    raw_nodes = workflow.get("nodes")
    if not isinstance(raw_nodes, list):
        _fail("WORKFLOW_SCHEMA_INVALID", "Workflow nodes must be an array")

    order: list[str] = []
    nodes: dict[str, NodeRun] = {}
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            _fail("WORKFLOW_SCHEMA_INVALID", "Every Workflow node must be an object")
        node_id = raw_node.get("id")
        role_id = raw_node.get("role_id")
        if not isinstance(node_id, str):
            _fail("WORKFLOW_SCHEMA_INVALID", "Every Workflow node must have a string ID")
        if role_id is not None and not isinstance(role_id, str):
            _fail("WORKFLOW_SCHEMA_INVALID", f"Node {node_id!r} has an invalid role ID")
        if node_id in nodes:
            _fail("WORKFLOW_SCHEMA_INVALID", f"Duplicate Workflow Node ID {node_id!r}")
        order.append(node_id)
        nodes[node_id] = NodeRun(
            node_id=node_id,
            role_id=role_id,
            status=NodeRunStatus.IDLE,
            attempt_count=0,
            artifact_refs=(),
        )
    return tuple(order), nodes


def _read_edges(workflow: JsonObject) -> dict[str, JsonObject]:
    raw_edges = workflow.get("edges")
    if not isinstance(raw_edges, list):
        _fail("WORKFLOW_SCHEMA_INVALID", "Workflow edges must be an array")
    edges: dict[str, JsonObject] = {}
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict) or not isinstance(raw_edge.get("id"), str):
            _fail("WORKFLOW_SCHEMA_INVALID", "Every Workflow edge must have a string ID")
        edge_id = raw_edge["id"]
        if edge_id in edges:
            _fail("WORKFLOW_SCHEMA_INVALID", f"Duplicate Workflow Edge ID {edge_id!r}")
        edges[edge_id] = raw_edge
    return edges


def _initial_budget(workflow: JsonObject) -> BudgetUsage:
    policies = workflow.get("policies")
    if not isinstance(policies, dict):
        _fail("WORKFLOW_SCHEMA_INVALID", "Workflow policies must be an object")
    max_duration = policies.get("max_duration_seconds")
    max_transitions = policies.get("max_total_transitions")
    if not isinstance(max_duration, int) or not isinstance(max_transitions, int):
        _fail("WORKFLOW_SCHEMA_INVALID", "Workflow budget policies must be integers")
    return BudgetUsage(
        max_duration_seconds=max_duration,
        elapsed_seconds=0.0,
        max_transitions=max_transitions,
        used_transitions=0,
        max_tool_calls=0,
        used_tool_calls=0,
    )


def _validate_stream(
    workflow_ref: PinnedWorkflowRef,
    events: Sequence[Event],
    schema_bundle: SchemaBundle,
) -> str:
    if not events:
        _fail("PROJECTION_EVENT_STREAM_EMPTY", "A persisted Run requires at least one Event")
    if events[0].type is not EventType.WORKFLOW_VALIDATION_STARTED:
        _fail(
            "EVENT_TRANSITION_INVALID",
            "The first Event must be WORKFLOW_VALIDATION_STARTED",
        )

    run_id = events[0].run_id
    event_ids: set[str] = set()
    for expected_sequence, event in enumerate(events, start=1):
        _schema_check(
            to_schema_instance(event),
            EVENT_SCHEMA_ID,
            schema_bundle,
            "EVENT_SCHEMA_INVALID",
        )
        if event.sequence != expected_sequence:
            _fail(
                "EVENT_SEQUENCE_CONFLICT",
                f"Expected Event sequence {expected_sequence}, got {event.sequence}",
            )
        if event.event_id in event_ids:
            _fail("EVENT_ID_CONFLICT", f"Duplicate Event ID {event.event_id!r}")
        event_ids.add(event.event_id)
        if event.run_id != run_id:
            _fail("EVENT_IDENTITY_CONFLICT", "Run ID changed inside one Event stream")
        if (
            event.workflow_id != workflow_ref.workflow_id
            or event.workflow_revision != workflow_ref.revision
        ):
            _fail(
                "EVENT_IDENTITY_CONFLICT",
                f"Event sequence {event.sequence} changed Workflow identity",
            )

    first_runtime = _runtime_details(events[0])
    raw_ref = first_runtime.get("workflow_ref")
    if not isinstance(raw_ref, dict):
        _fail(
            "WORKFLOW_DIGEST_MISMATCH",
            "The first Event must pin payload.details.runtime.workflow_ref",
        )
    try:
        event_ref = PinnedWorkflowRef.model_validate(raw_ref)
    except ValidationError as error:
        raise ProjectionError(
            "The first Event contains an invalid pinned Workflow reference",
            code="WORKFLOW_DIGEST_MISMATCH",
        ) from error
    if event_ref != workflow_ref:
        _fail("WORKFLOW_DIGEST_MISMATCH", "Pinned Workflow reference does not match definition")
    return run_id


def _append_unique(target: list[str], values: tuple[str, ...] | None) -> None:
    if values is None:
        return
    for value in values:
        if value not in target:
            target.append(value)


def _require_transition(
    current: NodeRunStatus,
    allowed: frozenset[NodeRunStatus],
    event: Event,
) -> None:
    if current not in allowed:
        _fail(
            "EVENT_TRANSITION_INVALID",
            f"{event.type.value} cannot follow Node status {current.value}",
        )


def _apply_run_event(state: _ProjectionState, event: Event, runtime: JsonObject) -> None:
    current = state.status
    if event.type is EventType.WORKFLOW_VALIDATION_STARTED:
        if current is not None:
            _fail("EVENT_TRANSITION_INVALID", "Workflow validation started more than once")
        state.status = RunStatus.VALIDATING
    elif event.type is EventType.WORKFLOW_VALIDATION_COMPLETED:
        if current is not RunStatus.VALIDATING:
            _fail("EVENT_TRANSITION_INVALID", "Validation completion requires VALIDATING")
        state.status = RunStatus.READY
    elif event.type is EventType.WORKFLOW_VALIDATION_FAILED:
        if current is not RunStatus.VALIDATING:
            _fail("EVENT_TRANSITION_INVALID", "Validation failure requires VALIDATING")
        state.status = RunStatus.FAILED
        state.completed_at = event.timestamp
    elif event.type is EventType.RUN_STARTED:
        if current is not RunStatus.READY:
            _fail("EVENT_TRANSITION_INVALID", "RUN_STARTED requires READY")
        state.status = RunStatus.RUNNING
        state.attempt_count += 1
    elif event.type is EventType.RUN_PAUSED:
        if current is not RunStatus.RUNNING:
            _fail("EVENT_TRANSITION_INVALID", "RUN_PAUSED requires RUNNING")
        pause = runtime.get("pause")
        reason = pause.get("reason") if isinstance(pause, dict) else None
        if reason == "input_required":
            state.status = RunStatus.WAITING_FOR_USER
        elif reason == "explicit_checkpoint":
            state.status = RunStatus.PAUSED
        else:
            _fail("EVENT_TRANSITION_INVALID", "RUN_PAUSED requires a supported pause reason")
    elif event.type is EventType.RUN_RESUMED:
        if current not in {RunStatus.WAITING_FOR_USER, RunStatus.PAUSED}:
            _fail("EVENT_TRANSITION_INVALID", "RUN_RESUMED requires a paused Run")
        state.status = RunStatus.RUNNING
    elif event.type is EventType.RUN_COMPLETED:
        if current is not RunStatus.RUNNING:
            _fail("EVENT_TRANSITION_INVALID", "RUN_COMPLETED requires RUNNING")
        state.status = RunStatus.COMPLETED
        state.completed_at = event.timestamp
    elif event.type is EventType.RUN_FAILED:
        if current is not RunStatus.RUNNING:
            _fail("EVENT_TRANSITION_INVALID", "RUN_FAILED requires RUNNING")
        state.status = RunStatus.FAILED
        state.completed_at = event.timestamp
    elif event.type is EventType.RUN_CANCELLED:
        if current not in {
            RunStatus.RUNNING,
            RunStatus.WAITING_FOR_USER,
            RunStatus.PAUSED,
        }:
            _fail("EVENT_TRANSITION_INVALID", "RUN_CANCELLED requires an active Run")
        state.status = RunStatus.CANCELLED
        state.completed_at = event.timestamp


def _run_error(event: Event) -> RunError:
    error = event.payload.error
    if error is None:
        _fail("EVENT_TRANSITION_INVALID", "NODE_FAILED requires payload.error")
    return RunError(
        code=error.code,
        message=error.message,
        category=error.category,
        retryable=error.retryable,
        details=deepcopy(error.details),
        cause_event_id=event.event_id,
    )


def _apply_node_event(state: _ProjectionState, event: Event) -> None:
    if state.status is not RunStatus.RUNNING:
        _fail("EVENT_TRANSITION_INVALID", f"{event.type.value} requires a RUNNING Run")
    node_id = event.node_id
    if node_id is None or node_id not in state.nodes:
        _fail("NODE_REFERENCE_UNKNOWN", f"Unknown Node reference: {node_id!r}")
    current = state.nodes[node_id]
    artifacts = list(current.artifact_refs)
    _append_unique(artifacts, event.payload.artifact_refs)
    updates: dict[str, Any] = {
        "artifact_refs": tuple(artifacts),
        "updated_at": event.timestamp,
    }

    if event.type is EventType.NODE_QUEUED:
        _require_transition(current.status, _REQUEUEABLE_NODE_STATES, event)
        attempt = current.attempt_count + 1
        if event.payload.attempt is not None and event.payload.attempt != attempt:
            _fail("EVENT_COUNTER_INVALID", "Node attempt counter is not continuous")
        updates.update(
            status=NodeRunStatus.QUEUED,
            attempt_count=attempt,
            started_at=None,
            completed_at=None,
            last_error=None,
        )
    elif event.type is EventType.NODE_STARTED:
        _require_transition(current.status, frozenset({NodeRunStatus.QUEUED}), event)
        updates.update(status=NodeRunStatus.RUNNING, started_at=event.timestamp)
    elif event.type in {EventType.NODE_INPUT_VALIDATED, EventType.NODE_OUTPUT_VALIDATED}:
        _require_transition(current.status, frozenset({NodeRunStatus.RUNNING}), event)
    elif event.type in {
        EventType.NODE_INPUT_REJECTED,
        EventType.NODE_OUTPUT_REJECTED,
    }:
        _require_transition(current.status, frozenset({NodeRunStatus.RUNNING}), event)
        updates.update(status=NodeRunStatus.REJECTED, completed_at=event.timestamp)
    elif event.type is EventType.NODE_SUCCEEDED:
        _require_transition(current.status, frozenset({NodeRunStatus.RUNNING}), event)
        updates.update(status=NodeRunStatus.SUCCEEDED, completed_at=event.timestamp)
    elif event.type is EventType.NODE_FAILED:
        _require_transition(current.status, frozenset({NodeRunStatus.RUNNING}), event)
        last_error = _run_error(event)
        status = (
            NodeRunStatus.RETRYABLE_FAILED
            if last_error.retryable
            else NodeRunStatus.TERMINAL_FAILED
        )
        updates.update(
            status=status,
            last_error=last_error,
            completed_at=event.timestamp,
        )
    elif event.type is EventType.NODE_SKIPPED:
        _require_transition(
            current.status,
            frozenset({NodeRunStatus.IDLE, NodeRunStatus.QUEUED}),
            event,
        )
        updates.update(status=NodeRunStatus.SKIPPED, completed_at=event.timestamp)
    elif event.type is EventType.NODE_CANCELLED:
        _require_transition(
            current.status,
            frozenset({NodeRunStatus.QUEUED, NodeRunStatus.RUNNING}),
            event,
        )
        updates.update(status=NodeRunStatus.CANCELLED, completed_at=event.timestamp)
    state.nodes[node_id] = current.model_copy(update=updates, deep=True)


def _integer_counter(value: Any, name: str, event: Event, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(
            "EVENT_COUNTER_INVALID",
            f"Event sequence {event.sequence} has invalid {name}",
        )
    return int(value)


def _apply_counters(
    state: _ProjectionState,
    event: Event,
    runtime: JsonObject,
    edges: dict[str, JsonObject],
) -> None:
    incoming_edge_id = runtime.get("incoming_edge_id")
    transition_index = runtime.get("transition_index")
    if incoming_edge_id is not None or transition_index is not None:
        if event.type is not EventType.NODE_QUEUED:
            _fail("EVENT_COUNTER_INVALID", "Transition facts belong on NODE_QUEUED")
        if not isinstance(incoming_edge_id, str) or incoming_edge_id not in edges:
            _fail("EVENT_COUNTER_INVALID", "Transition references an unknown edge")
        index = _integer_counter(transition_index, "transition_index", event, minimum=1)
        if index != state.budget.used_transitions + 1:
            _fail("EVENT_COUNTER_INVALID", "Transition counter is not continuous")
        edge = edges[incoming_edge_id]
        target = edge.get("to")
        if not isinstance(target, dict) or target.get("node_id") != event.node_id:
            _fail("EVENT_COUNTER_INVALID", "Incoming edge does not target the queued Node")
        if edge.get("kind") not in {"sequence", "conditional", "retry", "error"}:
            _fail("EVENT_COUNTER_INVALID", "Incoming edge kind is unsupported in M1")
        state.budget = state.budget.model_copy(update={"used_transitions": index})

    retry = runtime.get("retry")
    if retry is not None:
        if event.type is not EventType.NODE_QUEUED or not isinstance(retry, dict):
            _fail("EVENT_COUNTER_INVALID", "Retry facts belong on NODE_QUEUED")
        edge_id = retry.get("edge_id")
        if not isinstance(edge_id, str) or edge_id not in edges:
            _fail("EVENT_COUNTER_INVALID", "Retry references an unknown edge")
        edge = edges[edge_id]
        if edge.get("kind") != "retry" or incoming_edge_id != edge_id:
            _fail("EVENT_COUNTER_INVALID", "Retry facts do not match the incoming retry edge")
        traversal = _integer_counter(retry.get("traversal"), "retry.traversal", event, 1)
        max_traversals = _integer_counter(
            retry.get("max_traversals"),
            "retry.max_traversals",
            event,
            1,
        )
        policy = edge.get("retry")
        declared_max = policy.get("max_traversals") if isinstance(policy, dict) else None
        if max_traversals != declared_max or traversal > max_traversals:
            _fail("EVENT_COUNTER_INVALID", "Retry counter exceeds the declared edge bound")
        if traversal != state.retry_counts.get(edge_id, 0) + 1:
            _fail("EVENT_COUNTER_INVALID", "Retry counter is not continuous")
        state.retry_counts[edge_id] = traversal

    budget = runtime.get("budget")
    if budget is None:
        return
    if not isinstance(budget, dict):
        _fail("EVENT_COUNTER_INVALID", "Runtime budget facts must be an object")
    updates: dict[str, int | float] = {}
    if "elapsed_seconds" in budget:
        elapsed = budget["elapsed_seconds"]
        if (
            isinstance(elapsed, bool)
            or not isinstance(elapsed, (int, float))
            or elapsed < state.budget.elapsed_seconds
        ):
            _fail("EVENT_COUNTER_INVALID", "Elapsed budget counter decreased or is invalid")
        updates["elapsed_seconds"] = float(elapsed)
    if "used_transitions" in budget:
        used_transitions = _integer_counter(
            budget["used_transitions"], "budget.used_transitions", event
        )
        if used_transitions != state.budget.used_transitions:
            _fail("EVENT_COUNTER_INVALID", "Budget transition count disagrees with history")
    if "used_tool_calls" in budget:
        used_tool_calls = _integer_counter(
            budget["used_tool_calls"], "budget.used_tool_calls", event
        )
        if used_tool_calls != state.budget.used_tool_calls:
            _fail("EVENT_COUNTER_INVALID", "M1 cannot infer unrecorded tool calls")
    if updates:
        state.budget = state.budget.model_copy(update=updates)


def project_run(
    workflow_definition: JsonObject,
    ordered_events: Sequence[Event],
    *,
    schema_bundle: SchemaBundle,
) -> Run:
    """Fold a validated M1 Event history into its unique frozen Run projection."""

    workflow = deepcopy(workflow_definition)
    events = tuple(event.model_copy(deep=True) for event in ordered_events)
    _schema_check(
        workflow,
        WORKFLOW_SCHEMA_ID,
        schema_bundle,
        "WORKFLOW_SCHEMA_INVALID",
    )
    workflow_id, workflow_version, revision = _read_workflow_identity(workflow)
    workflow_ref = PinnedWorkflowRef(
        workflow_id=workflow_id,
        workflow_version=workflow_version,
        revision=revision,
        digest=workflow_digest(workflow),
    )
    run_id = _validate_stream(workflow_ref, events, schema_bundle)
    node_order, nodes = _read_nodes(workflow)
    edges = _read_edges(workflow)
    state = _ProjectionState(
        status=None,
        nodes=nodes,
        node_order=node_order,
        budget=_initial_budget(workflow),
    )

    for event in events:
        runtime = _runtime_details(event)
        _append_unique(state.artifact_refs, event.payload.artifact_refs)
        _apply_counters(state, event, runtime, edges)
        if event.type in _VALIDATION_EVENT_TYPES or event.type in _RUN_EVENT_TYPES:
            _apply_run_event(state, event, runtime)
        elif event.type in _NODE_EVENT_TYPES:
            _apply_node_event(state, event)
        else:
            _fail(
                "EVENT_TYPE_UNSUPPORTED",
                f"Event type {event.type.value} is outside the M1 projection subset",
            )

    if state.status is None:
        _fail("EVENT_TRANSITION_INVALID", "Event stream did not create a Run state")
    projected = Run(
        run_id=run_id,
        workflow_ref=workflow_ref,
        status=state.status,
        node_runs=tuple(state.nodes[node_id] for node_id in state.node_order),
        attempt_count=state.attempt_count,
        budget=state.budget,
        artifact_refs=tuple(state.artifact_refs),
        last_event_sequence=events[-1].sequence,
        created_at=events[0].timestamp,
        updated_at=events[-1].timestamp,
        completed_at=state.completed_at,
        metadata=RunMetadata(),
    )
    _schema_check(
        to_schema_instance(projected),
        RUN_SCHEMA_ID,
        schema_bundle,
        "RUN_SCHEMA_INVALID",
    )
    return projected
