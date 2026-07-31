"""Strict provider-neutral contracts for M1 Run and Event records."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from oralflow.domain.agent import FrozenContract

SCHEMA_VERSION: Literal["0.1.0"] = "0.1.0"

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z][A-Za-z0-9_-]*$",
    ),
]
SemanticVersion = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"),
]
Revision = Annotated[str, StringConstraints(min_length=1, max_length=128)]
WorkflowDigest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
ArtifactRef = Annotated[
    str,
    StringConstraints(pattern=r"^artifact://[A-Za-z0-9][A-Za-z0-9._/-]*$"),
]
ErrorCode = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]
ErrorMessage = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
EvidenceRef = Annotated[str, StringConstraints(min_length=1, max_length=512)]
LabelValue = Annotated[str, StringConstraints(max_length=256)]
ExtensionKey = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$"),
]
JsonObject = dict[str, Any]


class RuntimeContract(FrozenContract):
    """Strict and frozen base for serialized Runtime boundary objects."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        allow_inf_nan=False,
    )


class RunStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    PAUSED = "PAUSED"
    REPLANNING = "REPLANNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeRunStatus(StrEnum):
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    RETRYABLE_FAILED = "RETRYABLE_FAILED"
    TERMINAL_FAILED = "TERMINAL_FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    TOOL = "tool"
    PROVIDER = "provider"
    BUDGET = "budget"
    CANCELLED = "cancelled"
    INTERNAL = "internal"


class SupervisorDecision(StrEnum):
    CONTINUE = "CONTINUE"
    RETRY = "RETRY"
    REPLAN = "REPLAN"
    ROLLBACK = "ROLLBACK"
    ESCALATE = "ESCALATE"
    STOP = "STOP"
    ACCEPT = "ACCEPT"


class EventType(StrEnum):
    WORKFLOW_VALIDATION_STARTED = "WORKFLOW_VALIDATION_STARTED"
    WORKFLOW_VALIDATION_COMPLETED = "WORKFLOW_VALIDATION_COMPLETED"
    WORKFLOW_VALIDATION_FAILED = "WORKFLOW_VALIDATION_FAILED"
    RUN_STARTED = "RUN_STARTED"
    RUN_PAUSED = "RUN_PAUSED"
    RUN_RESUMED = "RUN_RESUMED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"
    NODE_QUEUED = "NODE_QUEUED"
    NODE_STARTED = "NODE_STARTED"
    NODE_INPUT_VALIDATED = "NODE_INPUT_VALIDATED"
    NODE_INPUT_REJECTED = "NODE_INPUT_REJECTED"
    NODE_OUTPUT_VALIDATED = "NODE_OUTPUT_VALIDATED"
    NODE_OUTPUT_REJECTED = "NODE_OUTPUT_REJECTED"
    NODE_SUCCEEDED = "NODE_SUCCEEDED"
    NODE_FAILED = "NODE_FAILED"
    NODE_SKIPPED = "NODE_SKIPPED"
    NODE_CANCELLED = "NODE_CANCELLED"
    NODE_WAITING_APPROVAL = "NODE_WAITING_APPROVAL"
    ROLE_STARTED = "ROLE_STARTED"
    ROLE_OUTPUT_ACCEPTED = "ROLE_OUTPUT_ACCEPTED"
    ROLE_OUTPUT_REJECTED = "ROLE_OUTPUT_REJECTED"
    ROLE_COMPLETED = "ROLE_COMPLETED"
    ROLE_FAILED = "ROLE_FAILED"
    HUMAN_APPROVAL_REQUESTED = "HUMAN_APPROVAL_REQUESTED"
    HUMAN_APPROVAL_RESOLVED = "HUMAN_APPROVAL_RESOLVED"
    SUPERVISOR_DECISION = "SUPERVISOR_DECISION"
    ARTIFACT_CREATED = "ARTIFACT_CREATED"
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"


NODE_EVENT_TYPES = frozenset(
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
        EventType.NODE_WAITING_APPROVAL,
    }
)
ROLE_EVENT_TYPES = frozenset(
    {
        EventType.ROLE_STARTED,
        EventType.ROLE_OUTPUT_ACCEPTED,
        EventType.ROLE_OUTPUT_REJECTED,
        EventType.ROLE_COMPLETED,
        EventType.ROLE_FAILED,
        EventType.OBSERVATION_RECORDED,
    }
)


def _require_unique(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")
    return values


class PinnedWorkflowRef(RuntimeContract):
    workflow_id: Identifier
    workflow_version: SemanticVersion
    revision: Revision
    digest: WorkflowDigest


class StructuredError(RuntimeContract):
    code: ErrorCode
    message: ErrorMessage
    category: ErrorCategory
    retryable: bool
    details: JsonObject | None = None


class RunError(StructuredError):
    cause_event_id: Identifier | None = None


class BudgetUsage(RuntimeContract):
    max_duration_seconds: int = Field(ge=1)
    elapsed_seconds: float = Field(ge=0)
    max_transitions: int = Field(ge=1)
    used_transitions: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    used_tool_calls: int = Field(ge=0)


class NodeRun(RuntimeContract):
    node_id: Identifier
    role_id: Identifier | None = None
    status: NodeRunStatus
    attempt_count: int = Field(ge=0)
    artifact_refs: tuple[ArtifactRef, ...]
    last_error: RunError | None = None
    started_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None

    @field_validator("artifact_refs")
    @classmethod
    def artifact_refs_are_unique(
        cls,
        value: tuple[ArtifactRef, ...],
    ) -> tuple[ArtifactRef, ...]:
        return _require_unique(value, "artifact_refs")


class RunMetadata(RuntimeContract):
    labels: dict[str, LabelValue] | None = None
    extensions: dict[ExtensionKey, Any] | None = None


class Run(RuntimeContract):
    schema_version: Literal["0.1.0"] = SCHEMA_VERSION
    run_id: Identifier
    parent_run_id: Identifier | None = None
    workflow_ref: PinnedWorkflowRef
    status: RunStatus
    node_runs: tuple[NodeRun, ...]
    attempt_count: int = Field(ge=0)
    budget: BudgetUsage
    artifact_refs: tuple[ArtifactRef, ...]
    last_event_sequence: int = Field(ge=0)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    metadata: RunMetadata

    @field_validator("artifact_refs")
    @classmethod
    def artifact_refs_are_unique(
        cls,
        value: tuple[ArtifactRef, ...],
    ) -> tuple[ArtifactRef, ...]:
        return _require_unique(value, "artifact_refs")


class EventPayload(RuntimeContract):
    artifact_refs: tuple[ArtifactRef, ...] | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    attempt: int | None = Field(default=None, ge=0)
    error: StructuredError | None = None
    decision: SupervisorDecision | None = None
    reason: ErrorMessage | None = None
    evidence_refs: tuple[EvidenceRef, ...] | None = None
    remaining_budget: JsonObject | None = None
    details: JsonObject | None = None

    @field_validator("artifact_refs")
    @classmethod
    def artifact_refs_are_unique(
        cls,
        value: tuple[ArtifactRef, ...] | None,
    ) -> tuple[ArtifactRef, ...] | None:
        if value is None:
            return None
        return _require_unique(value, "artifact_refs")

    @field_validator("evidence_refs")
    @classmethod
    def evidence_refs_are_unique(
        cls,
        value: tuple[EvidenceRef, ...] | None,
    ) -> tuple[EvidenceRef, ...] | None:
        if value is None:
            return None
        return _require_unique(value, "evidence_refs")


class Event(RuntimeContract):
    schema_version: Literal["0.1.0"] = SCHEMA_VERSION
    event_id: Identifier
    sequence: int = Field(ge=1)
    run_id: Identifier
    workflow_id: Identifier
    workflow_revision: Revision
    node_id: Identifier | None = None
    role_id: Identifier | None = None
    type: EventType
    timestamp: AwareDatetime
    causation_event_id: Identifier | None = None
    correlation_id: Identifier | None = None
    payload: EventPayload

    @model_validator(mode="after")
    def enforce_event_type_requirements(self) -> Self:
        if self.type in NODE_EVENT_TYPES and self.node_id is None:
            raise ValueError(f"{self.type.value} requires node_id")
        if self.type in ROLE_EVENT_TYPES and self.role_id is None:
            raise ValueError(f"{self.type.value} requires role_id")
        if self.type is EventType.SUPERVISOR_DECISION:
            if self.role_id is None:
                raise ValueError("SUPERVISOR_DECISION requires role_id")
            if self.payload.decision is None or self.payload.reason is None:
                raise ValueError("SUPERVISOR_DECISION requires payload decision and reason")
        return self


class WorkflowDigestError(ValueError):
    """Raised when a Workflow cannot be represented as canonical JSON."""


def _ensure_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorkflowDigestError(f"Non-finite number at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _ensure_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise WorkflowDigestError(f"Non-string object key at {path}")
            _ensure_json_value(item, f"{path}.{key}")
        return
    raise WorkflowDigestError(f"Unsupported JSON value at {path}: {type(value).__name__}")


def canonical_workflow_bytes(workflow: JsonObject) -> bytes:
    """Serialize the complete Workflow using the M1 canonical JSON rules."""

    if not isinstance(workflow, dict):
        raise WorkflowDigestError("Workflow must be a JSON object")
    _ensure_json_value(workflow)
    try:
        canonical = json.dumps(
            workflow,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise WorkflowDigestError(f"Workflow is not canonical JSON: {error}") from error
    return canonical.encode("utf-8")


def workflow_digest(workflow: JsonObject) -> str:
    """Return the lowercase SHA-256 digest for one complete Workflow object."""

    return hashlib.sha256(canonical_workflow_bytes(workflow)).hexdigest()


def to_schema_instance(contract: RuntimeContract) -> JsonObject:
    """Serialize a Runtime contract into a frozen-Schema-compatible JSON object."""

    return contract.model_dump(mode="json", exclude_none=True)
