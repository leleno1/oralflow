from __future__ import annotations

from fastapi.testclient import TestClient
from oralflow.api.app import app


def test_health_endpoint_reports_m0_without_external_models() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "milestone": "M0",
        "external_models_enabled": False,
    }
