from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from oralflow.domain import (
    Event,
    EventPayload,
    EventType,
    Run,
    RunStatus,
    SupervisorDecision,
    WorkflowDigestError,
    canonical_workflow_bytes,
    to_schema_instance,
    workflow_digest,
)
from oralflow.validators.schema import load_schema_bundle, validate_instance
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]


def _fixture_text(name: str) -> str:
    return (ROOT / "tests" / "contract" / "fixtures" / "valid" / name).read_text(
        encoding="utf-8"
    )


def _fixture_object(name: str) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(_fixture_text(name))
    return value


def test_valid_run_round_trips_through_frozen_schema() -> None:
    run = Run.model_validate_json(_fixture_text("run.json"))
    instance = to_schema_instance(run)
    bundle = load_schema_bundle(ROOT / "schemas")

    report = validate_instance(instance, "urn:oralflow:schema:run:0.1.0", bundle)

    assert report.valid, report.as_dict()
    assert run.status is RunStatus.READY
    assert instance["created_at"] == "2026-07-31T16:00:00+08:00"


def test_valid_event_round_trips_through_frozen_schema() -> None:
    event = Event.model_validate_json(_fixture_text("event.json"))
    instance = to_schema_instance(event)
    bundle = load_schema_bundle(ROOT / "schemas")

    report = validate_instance(instance, "urn:oralflow:schema:event:0.1.0", bundle)

    assert report.valid, report.as_dict()
    assert event.type is EventType.NODE_SUCCEEDED
    assert "causation_event_id" not in instance


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "UNKNOWN"),
        ("workflow_ref.digest", "A" * 64),
        ("workflow_ref.revision", ""),
        ("run_id", "1_invalid"),
        ("created_at", "2026-07-31T16:00:00"),
    ],
)
def test_run_rejects_invalid_contract_values(field: str, value: Any) -> None:
    data = _fixture_object("run.json")
    if "." in field:
        parent, child = field.split(".", maxsplit=1)
        data[parent][child] = value
    else:
        data[field] = value

    with pytest.raises(ValidationError):
        Run.model_validate_json(json.dumps(data))


def test_runtime_contracts_forbid_extra_fields_and_are_frozen() -> None:
    data = _fixture_object("run.json")
    data["unexpected"] = True

    with pytest.raises(ValidationError):
        Run.model_validate_json(json.dumps(data))

    run = Run.model_validate_json(_fixture_text("run.json"))
    with pytest.raises(ValidationError):
        run.status = RunStatus.RUNNING


def test_unique_schema_arrays_reject_duplicates() -> None:
    run_data = _fixture_object("run.json")
    run_data["artifact_refs"] = ["artifact://one", "artifact://one"]
    event_data = _fixture_object("event.json")
    event_data["payload"]["evidence_refs"] = ["test://same", "test://same"]

    with pytest.raises(ValidationError):
        Run.model_validate_json(json.dumps(run_data))
    with pytest.raises(ValidationError):
        Event.model_validate_json(json.dumps(event_data))


@pytest.mark.parametrize(
    "event_type",
    [
        EventType.NODE_STARTED,
        EventType.NODE_OUTPUT_REJECTED,
        EventType.NODE_CANCELLED,
    ],
)
def test_node_events_require_node_id(event_type: EventType) -> None:
    event_data = _fixture_object("event.json")
    event_data["type"] = event_type.value
    event_data.pop("node_id")

    with pytest.raises(ValidationError, match="requires node_id"):
        Event.model_validate_json(json.dumps(event_data))


@pytest.mark.parametrize(
    "event_type",
    [EventType.ROLE_STARTED, EventType.ROLE_FAILED, EventType.OBSERVATION_RECORDED],
)
def test_role_and_observation_events_require_role_id(event_type: EventType) -> None:
    event_data = _fixture_object("event.json")
    event_data["type"] = event_type.value
    event_data.pop("role_id")

    with pytest.raises(ValidationError, match="requires role_id"):
        Event.model_validate_json(json.dumps(event_data))


def test_supervisor_decision_requires_role_decision_and_reason() -> None:
    event_data = _fixture_object("event.json")
    event_data["type"] = EventType.SUPERVISOR_DECISION.value
    event_data.pop("role_id")
    event_data["payload"] = {}

    with pytest.raises(ValidationError, match="requires role_id"):
        Event.model_validate_json(json.dumps(event_data))

    event_data["role_id"] = "supervisor"
    with pytest.raises(ValidationError, match="requires payload decision and reason"):
        Event.model_validate_json(json.dumps(event_data))

    event = Event.model_validate_json(
        json.dumps(
            {
                **event_data,
                "payload": {
                    "decision": SupervisorDecision.ACCEPT.value,
                    "reason": "Contract evidence is complete.",
                },
            }
        )
    )
    assert event.payload.decision is SupervisorDecision.ACCEPT


def test_event_payload_rejects_non_finite_duration() -> None:
    with pytest.raises(ValidationError):
        EventPayload(duration_seconds=float("inf"))


def test_workflow_digest_is_canonical_and_covers_complete_object() -> None:
    workflow = json.loads((ROOT / "examples" / "minimal-workflow.json").read_text("utf-8"))
    reordered = dict(reversed(list(workflow.items())))
    changed = {**workflow, "revision": "rev_002"}

    assert workflow_digest(workflow) == workflow_digest(reordered)
    assert workflow_digest(workflow) != workflow_digest(changed)
    assert len(workflow_digest(workflow)) == 64
    assert b"M0 minimal contract workflow" in canonical_workflow_bytes(workflow)


@pytest.mark.parametrize(
    "invalid_value",
    [float("nan"), float("inf"), {"not_json"}],
)
def test_workflow_digest_rejects_non_json_values(invalid_value: Any) -> None:
    with pytest.raises(WorkflowDigestError):
        workflow_digest({"schema_version": "0.1.0", "invalid": invalid_value})


def test_workflow_digest_preserves_unicode_without_ascii_escaping() -> None:
    workflow = {"schema_version": "0.1.0", "name": "英语口语"}

    canonical = canonical_workflow_bytes(workflow)

    assert canonical.decode("utf-8") == '{"name":"英语口语","schema_version":"0.1.0"}'
