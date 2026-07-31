"""Injected factory for deterministic M1 Event identity and timestamps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from oralflow.domain.runtime import Event, EventPayload, EventType


class Clock(Protocol):
    def __call__(self) -> datetime:
        """Return the current aware wall-clock timestamp."""


class EventIdFactory(Protocol):
    def __call__(self) -> str:
        """Return one globally unique Event identifier."""


@dataclass(frozen=True, slots=True)
class EventFactory:
    """Build Event contracts without hidden time or randomness dependencies."""

    clock: Clock
    event_id_factory: EventIdFactory

    def create(
        self,
        *,
        sequence: int,
        run_id: str,
        workflow_id: str,
        workflow_revision: str,
        event_type: EventType,
        payload: EventPayload,
        node_id: str | None = None,
        role_id: str | None = None,
        causation_event_id: str | None = None,
        correlation_id: str | None = None,
    ) -> Event:
        return Event(
            event_id=self.event_id_factory(),
            sequence=sequence,
            run_id=run_id,
            workflow_id=workflow_id,
            workflow_revision=workflow_revision,
            node_id=node_id,
            role_id=role_id,
            type=event_type,
            timestamp=self.clock(),
            causation_event_id=causation_event_id,
            correlation_id=run_id if correlation_id is None else correlation_id,
            payload=payload,
        )
