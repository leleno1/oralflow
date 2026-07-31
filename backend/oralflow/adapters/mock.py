"""Deterministic, network-free Agent backend for Harness tests."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from oralflow.domain import (
    ContextRef,
    RoleRunRequest,
    RoleRunResult,
    StandardError,
    StartContextRequest,
)


class MockAgentBackend:
    """Return fixed local fixtures through the provider-neutral interface."""

    def __init__(self, fixtures: Mapping[str, Mapping[str, Any]]) -> None:
        self._fixtures = {
            key: copy.deepcopy(dict(value))
            for key, value in fixtures.items()
        }
        self._cancelled_runs: set[str] = set()
        self._contexts: dict[str, ContextRef] = {}

    async def start_context(self, request: StartContextRequest) -> ContextRef:
        context = ContextRef(
            context_id=f"mock_context_{request.request_id}",
            backend_profile="mock",
            status="active",
        )
        self._contexts[context.context_id] = context
        return context

    async def run_role(self, request: RoleRunRequest) -> RoleRunResult:
        if request.run_id in self._cancelled_runs:
            return RoleRunResult(
                status="cancelled",
                error=StandardError(
                    code="RUN_CANCELLED",
                    message="The deterministic mock run was cancelled.",
                    category="cancelled",
                    retryable=False,
                ),
            )

        fixture = self._fixtures.get(request.fixture_key)
        if fixture is None:
            return RoleRunResult(
                status="failed",
                error=StandardError(
                    code="MOCK_FIXTURE_NOT_FOUND",
                    message=f"No Mock fixture is registered for {request.fixture_key!r}.",
                    category="provider",
                    retryable=False,
                ),
            )
        return RoleRunResult(status="completed", output=copy.deepcopy(fixture))

    async def resume_context(self, context_id: str) -> ContextRef:
        context = self._contexts.get(context_id)
        if context is None:
            raise KeyError(f"Unknown Mock context: {context_id}")
        return context

    async def fork_context(
        self,
        context_id: str,
        checkpoint: str | None,
    ) -> ContextRef:
        if context_id not in self._contexts:
            raise KeyError(f"Unknown Mock context: {context_id}")
        suffix = checkpoint or "latest"
        forked = ContextRef(
            context_id=f"{context_id}_fork_{suffix}",
            backend_profile="mock",
            status="active",
        )
        self._contexts[forked.context_id] = forked
        return forked

    async def compact_context(self, context_id: str) -> None:
        context = await self.resume_context(context_id)
        self._contexts[context_id] = context.model_copy(update={"status": "compacted"})

    async def cancel(self, run_id: str) -> None:
        self._cancelled_runs.add(run_id)
