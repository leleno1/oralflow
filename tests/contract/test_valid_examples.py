from __future__ import annotations

import json
from pathlib import Path

import pytest
from oralflow.validators.schema import JsonObject, SchemaBundle, validate_instance
from oralflow.validators.workflow import validate_workflow


@pytest.mark.parametrize(
    ("filename", "schema_id"),
    [
        ("artifact.json", "urn:oralflow:schema:artifact:0.1.0"),
        ("event.json", "urn:oralflow:schema:event:0.1.0"),
        ("run.json", "urn:oralflow:schema:run:0.1.0"),
    ],
)
def test_valid_standalone_instances(
    filename: str,
    schema_id: str,
    valid_fixture_dir: Path,
    schema_bundle: SchemaBundle,
) -> None:
    instance: JsonObject = json.loads(
        (valid_fixture_dir / filename).read_text(encoding="utf-8")
    )
    report = validate_instance(instance, schema_id, schema_bundle)
    assert report.valid, report.as_dict()


def test_all_example_workflows_pass(
    workflow_catalog: dict[str, JsonObject],
    schema_bundle: SchemaBundle,
) -> None:
    for workflow in workflow_catalog.values():
        report = validate_workflow(workflow, schema_bundle, workflow_catalog)
        assert report.valid, report.as_dict()


def test_minimal_workflow_covers_all_edge_kinds(
    workflow_catalog: dict[str, JsonObject],
) -> None:
    edge_kinds = {
        edge["kind"]
        for edge in workflow_catalog["wf_minimal_contract"]["edges"]
    }
    assert edge_kinds == {
        "sequence",
        "conditional",
        "retry",
        "error",
        "subworkflow",
    }
