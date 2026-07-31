"""Minimal M0 FastAPI application."""

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Stable health response for smoke tests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    milestone: str
    external_models_enabled: bool


app = FastAPI(
    title="OralFlow",
    version="0.0.0",
    description="M0 engineering Harness and contract shell",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        milestone="M0",
        external_models_enabled=False,
    )
