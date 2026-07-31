from __future__ import annotations

from oralflow.validators.schema import SchemaBundle


def test_all_m0_schema_ids_are_registered(schema_bundle: SchemaBundle) -> None:
    assert set(schema_bundle.schemas) == {
        "urn:oralflow:schema:artifact:0.1.0",
        "urn:oralflow:schema:event:0.1.0",
        "urn:oralflow:schema:node:0.1.0",
        "urn:oralflow:schema:role:0.1.0",
        "urn:oralflow:schema:run:0.1.0",
        "urn:oralflow:schema:workflow:0.1.0",
    }


def test_all_m0_schemas_use_draft_2020_12(schema_bundle: SchemaBundle) -> None:
    assert all(
        schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        for schema in schema_bundle.schemas.values()
    )


def test_all_m0_schemas_have_unique_paths(schema_bundle: SchemaBundle) -> None:
    assert len(schema_bundle.paths) == len(set(schema_bundle.paths.values()))
