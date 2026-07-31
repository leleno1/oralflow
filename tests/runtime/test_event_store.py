from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from oralflow.domain import Event, EventPayload, EventType
from oralflow.events import (
    EventFactory,
    EventIdConflict,
    EventIdentityConflict,
    EventSchemaInvalid,
    EventSequenceConflict,
    EventStore,
    InMemoryEventStore,
)
from oralflow.validators.schema import SchemaBundle, load_schema_bundle
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = datetime.fromisoformat("2026-07-31T18:00:00+08:00")


@pytest.fixture
def schema_bundle() -> SchemaBundle:
    return load_schema_bundle(ROOT / "schemas")


def _accepts_event_store(store: EventStore) -> EventStore:
    return store


def _event(
    *,
    event_id: str,
    sequence: int,
    run_id: str = "run_store_001",
    workflow_id: str = "workflow_store",
    workflow_revision: str = "rev_001",
    payload: EventPayload | None = None,
) -> Event:
    return Event(
        event_id=event_id,
        sequence=sequence,
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_revision=workflow_revision,
        type=EventType.RUN_STARTED,
        timestamp=FIXED_TIME,
        correlation_id=run_id,
        payload=payload or EventPayload(),
    )


def test_in_memory_store_satisfies_protocol_and_appends_in_order(
    schema_bundle: SchemaBundle,
) -> None:
    store = _accepts_event_store(InMemoryEventStore(schema_bundle))
    first = _event(event_id="event_store_001", sequence=1)
    second = _event(event_id="event_store_002", sequence=2)

    assert store.last_sequence(first.run_id) == 0
    assert store.load(first.run_id) == ()

    store.append(first, expected_last_sequence=0)
    store.append(second, expected_last_sequence=1)

    assert store.last_sequence(first.run_id) == 2
    assert store.load(first.run_id) == (first, second)


def test_streams_are_isolated_by_run(schema_bundle: SchemaBundle) -> None:
    store = InMemoryEventStore(schema_bundle)
    first = _event(event_id="event_run_a", sequence=1, run_id="run_a")
    second = _event(event_id="event_run_b", sequence=1, run_id="run_b")

    store.append(first, expected_last_sequence=0)
    store.append(second, expected_last_sequence=0)

    assert store.load("run_a") == (first,)
    assert store.load("run_b") == (second,)


@pytest.mark.parametrize(
    ("event_sequence", "expected_last_sequence"),
    [(2, 0), (1, 1), (3, 1)],
)
def test_sequence_conflicts_are_explicit_and_do_not_mutate_store(
    schema_bundle: SchemaBundle,
    event_sequence: int,
    expected_last_sequence: int,
) -> None:
    store = InMemoryEventStore(schema_bundle)
    candidate = _event(event_id="event_sequence_conflict", sequence=event_sequence)

    with pytest.raises(EventSequenceConflict) as captured:
        store.append(candidate, expected_last_sequence=expected_last_sequence)

    assert captured.value.code == "EVENT_SEQUENCE_CONFLICT"
    assert store.last_sequence(candidate.run_id) == 0
    assert store.load(candidate.run_id) == ()


def test_duplicate_event_id_is_rejected_globally_without_partial_append(
    schema_bundle: SchemaBundle,
) -> None:
    store = InMemoryEventStore(schema_bundle)
    first = _event(event_id="event_global", sequence=1, run_id="run_a")
    duplicate = _event(event_id="event_global", sequence=1, run_id="run_b")
    store.append(first, expected_last_sequence=0)

    with pytest.raises(EventIdConflict) as captured:
        store.append(duplicate, expected_last_sequence=0)

    assert captured.value.code == "EVENT_ID_CONFLICT"
    assert store.load("run_a") == (first,)
    assert store.load("run_b") == ()


def test_duplicate_event_id_is_rejected_in_the_same_run(
    schema_bundle: SchemaBundle,
) -> None:
    store = InMemoryEventStore(schema_bundle)
    first = _event(event_id="event_same_run", sequence=1)
    duplicate = _event(event_id="event_same_run", sequence=2)
    store.append(first, expected_last_sequence=0)

    with pytest.raises(EventIdConflict):
        store.append(duplicate, expected_last_sequence=1)

    assert store.load(first.run_id) == (first,)


def test_boolean_expected_sequence_is_not_accepted_as_an_integer(
    schema_bundle: SchemaBundle,
) -> None:
    store = InMemoryEventStore(schema_bundle)
    candidate = _event(event_id="event_boolean_expected", sequence=1)

    with pytest.raises(EventSequenceConflict):
        store.append(candidate, expected_last_sequence=True)

    assert store.load(candidate.run_id) == ()


@pytest.mark.parametrize(
    ("workflow_id", "workflow_revision"),
    [("workflow_other", "rev_001"), ("workflow_store", "rev_002")],
)
def test_run_stream_rejects_workflow_identity_drift(
    schema_bundle: SchemaBundle,
    workflow_id: str,
    workflow_revision: str,
) -> None:
    store = InMemoryEventStore(schema_bundle)
    first = _event(event_id="event_identity_001", sequence=1)
    drifted = _event(
        event_id="event_identity_002",
        sequence=2,
        workflow_id=workflow_id,
        workflow_revision=workflow_revision,
    )
    store.append(first, expected_last_sequence=0)

    with pytest.raises(EventIdentityConflict) as captured:
        store.append(drifted, expected_last_sequence=1)

    assert captured.value.code == "EVENT_IDENTITY_CONFLICT"
    assert store.load(first.run_id) == (first,)


def test_schema_validation_happens_before_append(schema_bundle: SchemaBundle) -> None:
    store = InMemoryEventStore(schema_bundle)
    valid = _event(event_id="event_invalid_schema", sequence=1)
    invalid = valid.model_copy(update={"sequence": 0})

    with pytest.raises(EventSchemaInvalid) as captured:
        store.append(invalid, expected_last_sequence=0)

    assert captured.value.code == "EVENT_SCHEMA_INVALID"
    assert store.last_sequence(valid.run_id) == 0
    assert store.load(valid.run_id) == ()


def test_store_snapshots_nested_payload_on_append_and_load(
    schema_bundle: SchemaBundle,
) -> None:
    source_details: dict[str, Any] = {"runtime": {"transition_index": 1}}
    event = _event(
        event_id="event_snapshot",
        sequence=1,
        payload=EventPayload(details=source_details),
    )
    store = InMemoryEventStore(schema_bundle)
    store.append(event, expected_last_sequence=0)

    source_details["runtime"]["transition_index"] = 999
    loaded = store.load(event.run_id)
    assert loaded[0].payload.details == {"runtime": {"transition_index": 1}}

    assert loaded[0].payload.details is not None
    loaded[0].payload.details["runtime"]["transition_index"] = 500
    assert store.load(event.run_id)[0].payload.details == {
        "runtime": {"transition_index": 1}
    }


def test_expected_sequence_check_is_atomic_under_competing_appends(
    schema_bundle: SchemaBundle,
) -> None:
    store = InMemoryEventStore(schema_bundle)
    barrier = Barrier(2)
    candidates = (
        _event(event_id="event_compete_a", sequence=1),
        _event(event_id="event_compete_b", sequence=1),
    )

    def append(candidate: Event) -> str:
        barrier.wait()
        try:
            store.append(candidate, expected_last_sequence=0)
        except EventSequenceConflict:
            return "conflict"
        return "stored"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(append, candidates))

    assert sorted(results) == ["conflict", "stored"]
    assert store.last_sequence("run_store_001") == 1
    assert len(store.load("run_store_001")) == 1


def test_event_factory_uses_only_injected_identity_and_clock() -> None:
    identifiers = iter(("event_factory_001", "event_factory_002"))
    factory = EventFactory(
        clock=lambda: FIXED_TIME,
        event_id_factory=lambda: next(identifiers),
    )

    first = factory.create(
        sequence=1,
        run_id="run_factory",
        workflow_id="workflow_factory",
        workflow_revision="rev_001",
        event_type=EventType.RUN_STARTED,
        payload=EventPayload(),
    )
    second = factory.create(
        sequence=2,
        run_id="run_factory",
        workflow_id="workflow_factory",
        workflow_revision="rev_001",
        event_type=EventType.RUN_PAUSED,
        payload=EventPayload(reason="Explicit checkpoint."),
        causation_event_id=first.event_id,
        correlation_id="correlation_factory",
    )

    assert first.event_id == "event_factory_001"
    assert first.timestamp == FIXED_TIME
    assert first.correlation_id == first.run_id
    assert second.event_id == "event_factory_002"
    assert second.correlation_id == "correlation_factory"
    assert second.causation_event_id == first.event_id


def test_event_factory_does_not_replace_an_explicit_invalid_correlation_id() -> None:
    factory = EventFactory(
        clock=lambda: FIXED_TIME,
        event_id_factory=lambda: "event_factory_invalid",
    )

    with pytest.raises(ValidationError):
        factory.create(
            sequence=1,
            run_id="run_factory",
            workflow_id="workflow_factory",
            workflow_revision="rev_001",
            event_type=EventType.RUN_STARTED,
            payload=EventPayload(),
            correlation_id="",
        )
