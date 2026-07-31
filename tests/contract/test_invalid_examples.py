from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from oralflow.validators.schema import JsonObject, SchemaBundle, validate_instance
from oralflow.validators.workflow import validate_workflow


def _resolve_parent(document: Any, path: list[str | int]) -> tuple[Any, str | int]:
    current = document
    for part in path[:-1]:
        current = current[part]
    return current, path[-1]


def _apply_operations(document: JsonObject, operations: list[dict[str, Any]]) -> None:
    for operation in operations:
        path: list[str | int] = operation["path"]
        parent, key = _resolve_parent(document, path)
        if operation["op"] == "set":
            parent[key] = operation["value"]
        elif operation["op"] == "remove":
            del parent[key]
        else:
            raise AssertionError(f"Unsupported fixture operation: {operation['op']}")


def test_invalid_workflow_mutations_return_expected_codes(
    invalid_workflow_cases: list[dict[str, Any]],
    workflow_catalog: dict[str, JsonObject],
    schema_bundle: SchemaBundle,
) -> None:
    base = workflow_catalog["wf_minimal_contract"]
    for case in invalid_workflow_cases:
        workflow = copy.deepcopy(base)
        _apply_operations(workflow, case["operations"])
        catalog = {**workflow_catalog, workflow["workflow_id"]: workflow}
        report = validate_workflow(workflow, schema_bundle, catalog)
        codes = {issue.code for issue in report.issues}
        assert not report.valid, case["name"]
        assert case["expected_code"] in codes, {
            "name": case["name"],
            "expected": case["expected_code"],
            "actual": report.as_dict(),
        }


def test_event_without_run_id_is_rejected(
    valid_fixture_dir: Path,
    schema_bundle: SchemaBundle,
) -> None:
    event: JsonObject = json.loads(
        (valid_fixture_dir / "event.json").read_text(encoding="utf-8")
    )
    del event["run_id"]
    report = validate_instance(
        event,
        "urn:oralflow:schema:event:0.1.0",
        schema_bundle,
    )
    assert not report.valid
    assert {issue.code for issue in report.issues} == {"SCHEMA_VALIDATION_FAILED"}


def test_run_without_pinned_digest_is_rejected(
    valid_fixture_dir: Path,
    schema_bundle: SchemaBundle,
) -> None:
    run: JsonObject = json.loads(
        (valid_fixture_dir / "run.json").read_text(encoding="utf-8")
    )
    del run["workflow_ref"]["digest"]
    report = validate_instance(
        run,
        "urn:oralflow:schema:run:0.1.0",
        schema_bundle,
    )
    assert not report.valid


@pytest.mark.parametrize("role_type", ["observer", "supervisor"])
def test_control_roles_cannot_write_code(
    role_type: str,
    workflow_catalog: dict[str, JsonObject],
    schema_bundle: SchemaBundle,
) -> None:
    role = copy.deepcopy(workflow_catalog["wf_minimal_contract"]["roles"][0])
    role["role_type"] = role_type
    role["permission_policy"]["code_write"] = True
    if role_type == "supervisor":
        role["permission_policy"]["routing_control"] = True
        role["permission_policy"]["business_artifact_write"] = False
    report = validate_instance(
        role,
        "urn:oralflow:schema:role:0.1.0",
        schema_bundle,
    )
    assert not report.valid
