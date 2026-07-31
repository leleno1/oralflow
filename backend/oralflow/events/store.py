"""Append-only EventStore boundary and deterministic in-memory implementation."""

from __future__ import annotations

from threading import RLock
from typing import ClassVar, Protocol, runtime_checkable

from oralflow.domain.runtime import Event, to_schema_instance
from oralflow.validators.schema import SchemaBundle, validate_instance

EVENT_SCHEMA_ID = "urn:oralflow:schema:event:0.1.0"


class EventStoreError(RuntimeError):
    """Base error with a stable machine-readable EventStore code."""

    code: ClassVar[str] = "EVENT_STORE_ERROR"


class EventSchemaInvalid(EventStoreError):
    """Raised before append when an Event fails the frozen Schema."""

    code = "EVENT_SCHEMA_INVALID"


class EventSequenceConflict(EventStoreError):
    """Raised when expected or supplied sequence does not extend the stream."""

    code = "EVENT_SEQUENCE_CONFLICT"


class EventIdConflict(EventStoreError):
    """Raised when an Event ID already exists in any Run stream."""

    code = "EVENT_ID_CONFLICT"


class EventIdentityConflict(EventStoreError):
    """Raised when a Run stream changes its pinned Workflow identity."""

    code = "EVENT_IDENTITY_CONFLICT"


@runtime_checkable
class EventStore(Protocol):
    """Minimal append-only event persistence boundary shared by M1 stores."""

    def append(self, event: Event, expected_last_sequence: int) -> None:
        """Atomically append one Event if it extends the observed stream."""

    def load(self, run_id: str) -> tuple[Event, ...]:
        """Return one Run stream ordered by sequence."""

    def last_sequence(self, run_id: str) -> int:
        """Return zero for an empty stream or its latest sequence."""


class InMemoryEventStore:
    """Thread-safe append-only store for deterministic tests and local execution."""

    def __init__(self, schema_bundle: SchemaBundle) -> None:
        self._schema_bundle = schema_bundle
        self._events_by_run: dict[str, list[Event]] = {}
        self._event_ids: set[str] = set()
        self._lock = RLock()

    def append(self, event: Event, expected_last_sequence: int) -> None:
        if (
            isinstance(expected_last_sequence, bool)
            or not isinstance(expected_last_sequence, int)
            or expected_last_sequence < 0
        ):
            raise EventSequenceConflict(
                "expected_last_sequence must be a non-negative integer"
            )
        snapshot = event.model_copy(deep=True)
        self._validate_schema(snapshot)

        with self._lock:
            stream = self._events_by_run.get(snapshot.run_id, [])
            actual_last_sequence = stream[-1].sequence if stream else 0
            required_sequence = actual_last_sequence + 1

            if (
                expected_last_sequence != actual_last_sequence
                or snapshot.sequence != required_sequence
            ):
                raise EventSequenceConflict(
                    "Run "
                    f"{snapshot.run_id!r} expected last sequence {expected_last_sequence}, "
                    f"actual {actual_last_sequence}, Event sequence {snapshot.sequence}; "
                    f"required Event sequence is {required_sequence}"
                )
            if snapshot.event_id in self._event_ids:
                raise EventIdConflict(f"Event ID already exists: {snapshot.event_id!r}")
            if stream:
                first = stream[0]
                if (
                    snapshot.workflow_id != first.workflow_id
                    or snapshot.workflow_revision != first.workflow_revision
                ):
                    raise EventIdentityConflict(
                        f"Run {snapshot.run_id!r} cannot change Workflow identity"
                    )

            self._events_by_run.setdefault(snapshot.run_id, []).append(snapshot)
            self._event_ids.add(snapshot.event_id)

    def load(self, run_id: str) -> tuple[Event, ...]:
        with self._lock:
            return tuple(
                event.model_copy(deep=True)
                for event in self._events_by_run.get(run_id, ())
            )

    def last_sequence(self, run_id: str) -> int:
        with self._lock:
            stream = self._events_by_run.get(run_id)
            return stream[-1].sequence if stream else 0

    def _validate_schema(self, event: Event) -> None:
        report = validate_instance(
            to_schema_instance(event),
            EVENT_SCHEMA_ID,
            self._schema_bundle,
        )
        if report.valid:
            return
        summary = "; ".join(
            f"{issue.instance_path or '/'}: {issue.message}"
            for issue in report.issues
        )
        raise EventSchemaInvalid(f"Event does not satisfy {EVENT_SCHEMA_ID}: {summary}")
