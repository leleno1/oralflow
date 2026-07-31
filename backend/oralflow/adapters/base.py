"""Provider-neutral Agent backend protocol."""

from __future__ import annotations

from typing import Protocol

from oralflow.domain import ContextRef, RoleRunRequest, RoleRunResult, StartContextRequest


class AgentBackend(Protocol):
    """Boundary implemented by deterministic mocks and future providers."""

    async def start_context(self, request: StartContextRequest) -> ContextRef: ...

    async def run_role(self, request: RoleRunRequest) -> RoleRunResult: ...

    async def resume_context(self, context_id: str) -> ContextRef: ...

    async def fork_context(
        self,
        context_id: str,
        checkpoint: str | None,
    ) -> ContextRef: ...

    async def compact_context(self, context_id: str) -> None: ...

    async def cancel(self, run_id: str) -> None: ...
