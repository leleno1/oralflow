"""Bounded deterministic M1 sequence and conditional Workflow executor."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, ClassVar, NoReturn

from oralflow.domain.runtime import (
    ErrorCategory,
    Event,
    EventPayload,
    EventType,
    JsonObject,
    PinnedWorkflowRef,
    Run,
    StructuredError,
    to_schema_instance,
    workflow_digest,
)
from oralflow.events import EventFactory, EventStore, EventStoreError
from oralflow.runtime.bindings import NodeRuntimeError, resolve_node_inputs
from oralflow.runtime.expressions import evaluate_path
from oralflow.runtime.handlers import (
    SUPPORTED_NODE_KINDS,
    SUPPORTED_TRANSFORMS,
    NodeHandlerResult,
    execute_node_handler,
)
from oralflow.runtime.projection import ProjectionError, project_run
from oralflow.validators import SchemaBundle, validate_instance, validate_workflow

RUNTIME_SEMANTICS_VERSION = "0.1.0"
WORKFLOW_SCHEMA_ID = "urn:oralflow:schema:workflow:0.1.0"
_SUPPORTED_EDGE_KINDS = frozenset({"sequence", "conditional"})
_INLINE_EVENT_LIMIT = 16 * 1024


class EngineError(RuntimeError):
    """Stable failure raised when execution cannot safely create a Run result."""

    default_code: ClassVar[str] = "ENGINE_FAILED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code or self.default_code


@dataclass(frozen=True, slots=True)
class _PreparedWorkflow:
    nodes: dict[str, JsonObject]
    outgoing: dict[str, tuple[JsonObject, ...]]
    entry_id: str
    max_transitions: int
    max_duration_seconds: int


def _fail(code: str, message: str) -> NoReturn:
    raise EngineError(message, code=code)


def _error(
    code: str,
    message: str,
    category: ErrorCategory,
    *,
    details: JsonObject | None = None,
) -> StructuredError:
    return StructuredError(
        code=code,
        message=message[:4096],
        category=category,
        retryable=False,
        details=deepcopy(details),
    )


def _schema_validated_workflow(
    workflow_definition: Mapping[str, Any],
    schema_bundle: SchemaBundle,
) -> tuple[JsonObject, PinnedWorkflowRef]:
    workflow = deepcopy(dict(workflow_definition))
    report = validate_instance(workflow, WORKFLOW_SCHEMA_ID, schema_bundle)
    if not report.valid:
        paths = ", ".join(issue.instance_path or "/" for issue in report.issues)
        _fail("WORKFLOW_SCHEMA_INVALID", f"Workflow Schema validation failed at: {paths}")

    workflow_id = workflow.get("workflow_id")
    workflow_version = workflow.get("workflow_version")
    revision = workflow.get("revision")
    if (
        not isinstance(workflow_id, str)
        or not isinstance(workflow_version, str)
        or not isinstance(revision, str)
    ):
        _fail("WORKFLOW_SCHEMA_INVALID", "Workflow identity is invalid")
    workflow_ref = PinnedWorkflowRef(
        workflow_id=workflow_id,
        workflow_version=workflow_version,
        revision=revision,
        digest=workflow_digest(workflow),
    )
    return workflow, workflow_ref


def _validate_expression_syntax(expression: Any) -> None:
    if not isinstance(expression, str):
        _fail("EXPRESSION_INVALID", "Gate expression must be a string")
    segments = expression.split(".")
    probe: Any = "case"
    for segment in reversed(segments):
        probe = {segment: probe}
    try:
        evaluate_path(expression, probe)
    except NodeRuntimeError as error:
        _fail(error.code, "Gate expression is outside oralflow-expression-0.1")


def _reference_scheme(binding: Any) -> str | None:
    if not isinstance(binding, dict) or set(binding) != {"ref"}:
        return None
    reference = binding.get("ref")
    if not isinstance(reference, str) or "://" not in reference:
        return None
    return reference.split("://", maxsplit=1)[0]


def _prepare_workflow(
    workflow: JsonObject,
    schema_bundle: SchemaBundle,
) -> _PreparedWorkflow:
    static_report = validate_workflow(workflow, schema_bundle)
    if not static_report.valid:
        _fail(
            "WORKFLOW_VALIDATION_FAILED",
            "Static Workflow validation failed",
        )

    raw_nodes = workflow["nodes"]
    nodes: dict[str, JsonObject] = {node["id"]: node for node in raw_nodes}
    entries = [node["id"] for node in raw_nodes if node["kind"] == "input"]
    if len(entries) != 1:
        _fail(
            "WORKFLOW_ENTRY_COUNT_INVALID",
            f"M1 requires exactly one input entry; found {len(entries)}",
        )

    for node in raw_nodes:
        kind = node["kind"]
        if kind not in SUPPORTED_NODE_KINDS:
            _fail("NODE_KIND_UNSUPPORTED", f"Node kind {kind!r} is unsupported")
        for binding in node["inputs"]["bindings"].values():
            if _reference_scheme(binding) in {"artifact", "file"}:
                _fail(
                    "NODE_INPUT_REFERENCE_UNSUPPORTED",
                    "Artifact and file bindings are unsupported in M1",
                )
        if kind == "transform":
            transform_id = node["config"]["values"].get("transform_id")
            if transform_id not in SUPPORTED_TRANSFORMS:
                _fail("TRANSFORM_UNKNOWN", "Transform is not allowlisted")
        if kind == "gate":
            condition = node.get("condition")
            if not isinstance(condition, dict):
                _fail("EXPRESSION_INVALID", "Gate condition is missing")
            if condition.get("language") != "oralflow-expression-0.1":
                _fail("EXPRESSION_INVALID", "Gate expression language is unsupported")
            _validate_expression_syntax(condition.get("expression"))

    outgoing_lists: dict[str, list[JsonObject]] = {node_id: [] for node_id in nodes}
    for edge in workflow["edges"]:
        kind = edge["kind"]
        if kind not in _SUPPORTED_EDGE_KINDS:
            _fail("EDGE_KIND_UNSUPPORTED", f"Edge kind {kind!r} is unavailable in this loop")
        outgoing_lists[edge["from"]["node_id"]].append(edge)

    for node_id, node in nodes.items():
        outgoing = outgoing_lists[node_id]
        kind = node["kind"]
        if kind == "terminal":
            continue
        if kind == "gate":
            if any(edge["kind"] != "conditional" for edge in outgoing):
                _fail("EDGE_KIND_UNSUPPORTED", "Gate nodes require conditional edges")
            expression = node["condition"]["expression"]
            if any(edge["condition"]["expression"] != expression for edge in outgoing):
                _fail(
                    "EXPRESSION_INVALID",
                    "Conditional edge expression must equal its gate expression",
                )
            cases = [edge["condition"]["case"] for edge in outgoing]
            if not cases:
                _fail("EDGE_SELECTION_NONE", f"Gate {node_id!r} has no conditional edge")
            if len(cases) != len(set(cases)):
                _fail(
                    "EDGE_SELECTION_AMBIGUOUS",
                    f"Gate {node_id!r} has duplicate conditional cases",
                )
        else:
            candidates = [edge for edge in outgoing if edge["kind"] == "sequence"]
            if len(candidates) == 0:
                _fail("EDGE_SELECTION_NONE", f"Node {node_id!r} has no sequence edge")
            if len(candidates) > 1 or len(candidates) != len(outgoing):
                _fail(
                    "EDGE_SELECTION_AMBIGUOUS",
                    f"Node {node_id!r} does not have one unique sequence edge",
                )

    policies = workflow["policies"]
    return _PreparedWorkflow(
        nodes=nodes,
        outgoing={
            node_id: tuple(sorted(edges, key=lambda edge: edge["id"]))
            for node_id, edges in outgoing_lists.items()
        },
        entry_id=entries[0],
        max_transitions=policies["max_total_transitions"],
        max_duration_seconds=policies["max_duration_seconds"],
    )


def _inline_value(value: JsonObject, label: str) -> JsonObject:
    try:
        serialized = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise EngineError(
            f"{label} is not finite JSON",
            code="INLINE_EVENT_DATA_FORBIDDEN",
        ) from error
    if len(serialized) > _INLINE_EVENT_LIMIT:
        _fail("INLINE_EVENT_DATA_LIMIT_EXCEEDED", f"{label} exceeds 16 KiB")
    return deepcopy(value)


class _Execution:
    def __init__(
        self,
        *,
        workflow: JsonObject,
        workflow_ref: PinnedWorkflowRef,
        run_id: str,
        initial_inputs: Mapping[str, Any],
        event_store: EventStore,
        event_factory: EventFactory,
        schema_bundle: SchemaBundle,
        monotonic_clock: Callable[[], float],
    ) -> None:
        if event_store.last_sequence(run_id) != 0 or event_store.load(run_id):
            _fail("RUN_ALREADY_EXISTS", "A new execution requires an empty Run stream")
        self.workflow = workflow
        self.workflow_ref = workflow_ref
        self.run_id = run_id
        self.initial_inputs = deepcopy(dict(initial_inputs))
        self.event_store = event_store
        self.event_factory = event_factory
        self.schema_bundle = schema_bundle
        self.monotonic_clock = monotonic_clock
        self.events: tuple[Event, ...] = ()
        self.last_event_id: str | None = None
        self.transitions = 0
        self.elapsed_seconds = 0.0
        self._start_tick = self._read_tick()
        self.node_outputs: dict[str, JsonObject] = {}

    def _read_tick(self) -> float:
        tick = self.monotonic_clock()
        if isinstance(tick, bool) or not isinstance(tick, (int, float)) or not math.isfinite(tick):
            _fail("ENGINE_CLOCK_INVALID", "Monotonic clock must return a finite number")
        return float(tick)

    def refresh_elapsed(self) -> float:
        elapsed = self._read_tick() - self._start_tick
        if elapsed < self.elapsed_seconds or elapsed < 0:
            _fail("ENGINE_CLOCK_INVALID", "Monotonic clock moved backwards")
        self.elapsed_seconds = elapsed
        return elapsed

    def _runtime_details(self, extra: JsonObject | None = None) -> JsonObject:
        runtime: JsonObject = {
            "semantics_version": RUNTIME_SEMANTICS_VERSION,
            "budget": {
                "elapsed_seconds": self.elapsed_seconds,
                "used_transitions": self.transitions,
                "used_tool_calls": 0,
            },
        }
        if extra:
            runtime.update(deepcopy(extra))
        return {"runtime": runtime}

    def append(
        self,
        event_type: EventType,
        *,
        node_id: str | None = None,
        attempt: int | None = None,
        error: StructuredError | None = None,
        reason: str | None = None,
        runtime: JsonObject | None = None,
    ) -> Run:
        expected = len(self.events)
        event = self.event_factory.create(
            sequence=expected + 1,
            run_id=self.run_id,
            workflow_id=self.workflow_ref.workflow_id,
            workflow_revision=self.workflow_ref.revision,
            event_type=event_type,
            node_id=node_id,
            causation_event_id=self.last_event_id,
            payload=EventPayload(
                attempt=attempt,
                error=error,
                reason=reason,
                details=self._runtime_details(runtime),
            ),
        )
        proposed = (*self.events, event)
        try:
            projected = project_run(
                self.workflow,
                proposed,
                schema_bundle=self.schema_bundle,
            )
        except ProjectionError as projection_error:
            raise EngineError(
                "Proposed Event violates the frozen projection",
                code=projection_error.code,
            ) from projection_error
        try:
            self.event_store.append(event, expected_last_sequence=expected)
        except EventStoreError as store_error:
            raise EngineError(
                f"Event append failed with {store_error.code}",
                code=store_error.code,
            ) from store_error
        self.events = proposed
        self.last_event_id = event.event_id
        return projected

    def fail_run(self, error: EngineError, category: ErrorCategory) -> Run:
        return self.append(
            EventType.RUN_FAILED,
            error=_error(error.code, f"Execution failed with {error.code}", category),
        )

    def fail_validation(self, error: EngineError) -> Run:
        return self.append(
            EventType.WORKFLOW_VALIDATION_FAILED,
            error=_error(
                error.code,
                f"Workflow preflight failed with {error.code}",
                ErrorCategory.VALIDATION,
            ),
        )

    def budget_error(self, prepared: _PreparedWorkflow) -> EngineError | None:
        self.refresh_elapsed()
        if self.elapsed_seconds > prepared.max_duration_seconds:
            return EngineError(
                "Workflow duration budget is exhausted",
                code="RUN_BUDGET_EXHAUSTED",
            )
        return None

    def execute_node(
        self,
        node: JsonObject,
    ) -> NodeHandlerResult | Run:
        node_id = node["id"]
        self.append(EventType.NODE_STARTED, node_id=node_id)
        try:
            resolved = resolve_node_inputs(node, self.initial_inputs, self.node_outputs)
        except NodeRuntimeError as node_error:
            normalized = _error(
                node_error.code,
                f"Node execution failed with {node_error.code}",
                ErrorCategory.VALIDATION,
            )
            self.append(
                EventType.NODE_INPUT_REJECTED,
                node_id=node_id,
                error=normalized,
            )
            return self.append(EventType.RUN_FAILED, error=normalized)

        try:
            resolved_inline = _inline_value(resolved, "Node input")
        except EngineError as inline_error:
            normalized = _error(
                inline_error.code,
                f"Node input was rejected with {inline_error.code}",
                ErrorCategory.VALIDATION,
            )
            self.append(
                EventType.NODE_INPUT_REJECTED,
                node_id=node_id,
                error=normalized,
            )
            return self.append(EventType.RUN_FAILED, error=normalized)

        try:
            result = execute_node_handler(
                node,
                resolved,
                schema_bundle=self.schema_bundle,
            )
        except NodeRuntimeError as node_error:
            normalized = _error(
                node_error.code,
                f"Node execution failed with {node_error.code}",
                ErrorCategory.VALIDATION,
            )
            if node_error.code.startswith("NODE_INPUT_"):
                self.append(
                    EventType.NODE_INPUT_REJECTED,
                    node_id=node_id,
                    error=normalized,
                )
            elif node_error.code == "NODE_OUTPUT_INVALID":
                self.append(
                    EventType.NODE_OUTPUT_REJECTED,
                    node_id=node_id,
                    error=normalized,
                )
            else:
                self.append(EventType.NODE_FAILED, node_id=node_id, error=normalized)
            return self.append(EventType.RUN_FAILED, error=normalized)
        except Exception:
            normalized = _error(
                "NODE_INTERNAL_ERROR",
                "Node execution failed with NODE_INTERNAL_ERROR",
                ErrorCategory.INTERNAL,
            )
            self.append(EventType.NODE_FAILED, node_id=node_id, error=normalized)
            return self.append(EventType.RUN_FAILED, error=normalized)

        try:
            output_inline = _inline_value(result.output, "Node output")
        except EngineError as inline_error:
            normalized = _error(
                inline_error.code,
                f"Node output was rejected with {inline_error.code}",
                ErrorCategory.VALIDATION,
            )
            self.append(
                EventType.NODE_INPUT_VALIDATED,
                node_id=node_id,
                runtime={"input": resolved_inline},
            )
            self.append(
                EventType.NODE_OUTPUT_REJECTED,
                node_id=node_id,
                error=normalized,
            )
            return self.append(EventType.RUN_FAILED, error=normalized)
        self.append(
            EventType.NODE_INPUT_VALIDATED,
            node_id=node_id,
            runtime={"input": resolved_inline},
        )
        self.append(
            EventType.NODE_OUTPUT_VALIDATED,
            node_id=node_id,
            runtime={"output": output_inline},
        )
        self.append(EventType.NODE_SUCCEEDED, node_id=node_id)
        self.node_outputs[node_id] = deepcopy(result.output)
        return result


def _select_edge(
    node: JsonObject,
    result: NodeHandlerResult,
    outgoing: tuple[JsonObject, ...],
) -> JsonObject:
    if node["kind"] != "gate":
        candidates = [edge for edge in outgoing if edge["kind"] == "sequence"]
    else:
        case = result.output.get("case")
        expression = node["condition"]["expression"]
        candidates = [
            edge
            for edge in outgoing
            if edge["kind"] == "conditional"
            and edge["condition"]["expression"] == expression
            and edge["condition"]["case"] == case
        ]
    if not candidates:
        _fail("EDGE_SELECTION_NONE", f"Node {node['id']!r} selected no edge")
    if len(candidates) > 1:
        _fail("EDGE_SELECTION_AMBIGUOUS", f"Node {node['id']!r} selected multiple edges")
    return candidates[0]


def execute_workflow(
    workflow_definition: Mapping[str, Any],
    initial_inputs: Mapping[str, Any],
    *,
    run_id: str,
    event_store: EventStore,
    event_factory: EventFactory,
    schema_bundle: SchemaBundle,
    monotonic_clock: Callable[[], float],
) -> Run:
    """Execute one new M1 Run through sequence and conditional success paths."""

    workflow, workflow_ref = _schema_validated_workflow(workflow_definition, schema_bundle)
    execution = _Execution(
        workflow=workflow,
        workflow_ref=workflow_ref,
        run_id=run_id,
        initial_inputs=initial_inputs,
        event_store=event_store,
        event_factory=event_factory,
        schema_bundle=schema_bundle,
        monotonic_clock=monotonic_clock,
    )
    execution.append(
        EventType.WORKFLOW_VALIDATION_STARTED,
        runtime={"workflow_ref": to_schema_instance(workflow_ref)},
    )
    try:
        prepared = _prepare_workflow(workflow, schema_bundle)
    except EngineError as preflight_error:
        return execution.fail_validation(preflight_error)

    execution.append(EventType.WORKFLOW_VALIDATION_COMPLETED)
    execution.append(EventType.RUN_STARTED)
    budget_error = execution.budget_error(prepared)
    if budget_error is not None:
        return execution.fail_run(budget_error, ErrorCategory.BUDGET)

    current_id = prepared.entry_id
    execution.append(EventType.NODE_QUEUED, node_id=current_id, attempt=1)
    visited: set[str] = set()
    while True:
        if current_id in visited:
            return execution.fail_run(
                EngineError("Runtime cycle detected", code="EVENT_TRANSITION_INVALID"),
                ErrorCategory.INTERNAL,
            )
        visited.add(current_id)
        node = prepared.nodes[current_id]
        outcome = execution.execute_node(node)
        if isinstance(outcome, Run):
            return outcome

        budget_error = execution.budget_error(prepared)
        if budget_error is not None:
            return execution.fail_run(budget_error, ErrorCategory.BUDGET)

        if outcome.terminal_outcome is not None:
            if outcome.terminal_outcome == "success":
                return execution.append(EventType.RUN_COMPLETED)
            if outcome.terminal_outcome == "failure":
                return execution.append(
                    EventType.RUN_FAILED,
                    reason="Terminal node declared failure",
                )
            return execution.append(
                EventType.RUN_CANCELLED,
                reason="Terminal node declared cancellation",
            )

        try:
            edge = _select_edge(node, outcome, prepared.outgoing[current_id])
        except EngineError as selection_error:
            return execution.fail_run(selection_error, ErrorCategory.VALIDATION)
        next_transition = execution.transitions + 1
        if next_transition > prepared.max_transitions:
            return execution.fail_run(
                EngineError(
                    "Workflow transition budget is exhausted",
                    code="RUN_BUDGET_EXHAUSTED",
                ),
                ErrorCategory.BUDGET,
            )
        execution.transitions = next_transition
        current_id = edge["to"]["node_id"]
        execution.append(
            EventType.NODE_QUEUED,
            node_id=current_id,
            attempt=1,
            runtime={
                "incoming_edge_id": edge["id"],
                "transition_index": execution.transitions,
            },
        )
