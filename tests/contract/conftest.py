from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from oralflow.validators.schema import JsonObject, SchemaBundle, load_schema_bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def schema_bundle() -> SchemaBundle:
    return load_schema_bundle(ROOT / "schemas")


@pytest.fixture(scope="session")
def workflow_catalog() -> dict[str, JsonObject]:
    catalog: dict[str, JsonObject] = {}
    for path in sorted((ROOT / "examples").glob("*.json")):
        workflow: JsonObject = json.loads(path.read_text(encoding="utf-8"))
        catalog[workflow["workflow_id"]] = workflow
    return catalog


@pytest.fixture(scope="session")
def valid_fixture_dir() -> Path:
    return ROOT / "tests" / "contract" / "fixtures" / "valid"


@pytest.fixture(scope="session")
def invalid_workflow_cases() -> list[dict[str, Any]]:
    path = ROOT / "tests" / "contract" / "fixtures" / "invalid" / "workflow-cases.json"
    value: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return value
