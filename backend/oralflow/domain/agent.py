"""Provider-neutral Agent backend data contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FrozenContract(BaseModel):
    """Strict immutable base for adapter boundary objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class StartContextRequest(FrozenContract):
    request_id: str = Field(min_length=1, max_length=128)
    role_id: str = Field(min_length=1, max_length=128)
    context_policy: dict[str, Any]


class ContextRef(FrozenContract):
    context_id: str = Field(min_length=1, max_length=256)
    backend_profile: str = Field(min_length=1, max_length=128)
    status: Literal["active", "compacted", "cancelled"]


class RoleRunRequest(FrozenContract):
    run_id: str = Field(min_length=1, max_length=128)
    context_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(min_length=1, max_length=128)
    fixture_key: str = Field(min_length=1, max_length=128)
    input_data: dict[str, Any]
    output_schema: dict[str, Any]


class StandardError(FrozenContract):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1, max_length=4096)
    category: Literal[
        "validation",
        "permission",
        "timeout",
        "tool",
        "provider",
        "budget",
        "cancelled",
        "internal",
    ]
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class RoleRunResult(FrozenContract):
    status: Literal["completed", "failed", "cancelled"]
    output: dict[str, Any] | None = None
    error: StandardError | None = None
