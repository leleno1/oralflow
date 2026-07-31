from __future__ import annotations

import asyncio

from oralflow.adapters import AgentBackend, MockAgentBackend
from oralflow.domain import RoleRunRequest, StartContextRequest


def _accepts_backend_contract(backend: AgentBackend) -> AgentBackend:
    return backend


def test_mock_backend_is_deterministic_and_provider_neutral() -> None:
    backend = _accepts_backend_contract(
        MockAgentBackend(
            {
                "approved_review": {
                    "verdict": "approved",
                    "summary": "Contract accepted.",
                }
            }
        )
    )

    async def scenario() -> None:
        context = await backend.start_context(
            StartContextRequest(
                request_id="request_001",
                role_id="mock_reviewer",
                context_policy={"history_mode": "declared_artifacts"},
            )
        )
        request = RoleRunRequest(
            run_id="run_001",
            context_id=context.context_id,
            role_id="mock_reviewer",
            fixture_key="approved_review",
            input_data={"request": "Validate the contract."},
            output_schema={
                "type": "object",
                "required": ["verdict", "summary"],
            },
        )

        first = await backend.run_role(request)
        second = await backend.run_role(request)

        assert first == second
        assert first.status == "completed"
        assert first.output == {
            "verdict": "approved",
            "summary": "Contract accepted.",
        }

    asyncio.run(scenario())


def test_mock_backend_returns_structured_failure_for_unknown_fixture() -> None:
    backend = MockAgentBackend({})

    async def scenario() -> None:
        context = await backend.start_context(
            StartContextRequest(
                request_id="request_002",
                role_id="mock_reviewer",
                context_policy={},
            )
        )
        result = await backend.run_role(
            RoleRunRequest(
                run_id="run_002",
                context_id=context.context_id,
                role_id="mock_reviewer",
                fixture_key="missing",
                input_data={},
                output_schema={"type": "object"},
            )
        )

        assert result.status == "failed"
        assert result.error is not None
        assert result.error.code == "MOCK_FIXTURE_NOT_FOUND"
        assert not result.error.retryable

    asyncio.run(scenario())
