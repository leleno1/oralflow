"""Validate all M0 Schemas and example Workflows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from oralflow.validators import (  # noqa: E402
    SchemaLoadError,
    load_schema_bundle,
    validate_workflow,
)
from oralflow.validators.schema import load_json_object  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", type=Path, default=ROOT / "schemas")
    parser.add_argument("--examples", type=Path, default=ROOT / "examples")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        bundle = load_schema_bundle(args.schemas)
        example_paths = sorted(args.examples.glob("*.json"))
        if not example_paths:
            raise SchemaLoadError(f"No JSON examples found in {args.examples}")

        catalog: dict[str, dict[str, Any]] = {}
        source_paths: dict[str, Path] = {}
        for path in example_paths:
            workflow = load_json_object(path)
            workflow_id = workflow.get("workflow_id")
            if not isinstance(workflow_id, str) or not workflow_id:
                raise SchemaLoadError(f"Example {path} has no workflow_id")
            if workflow_id in catalog:
                raise SchemaLoadError(
                    f"Duplicate example workflow_id {workflow_id!r} "
                    f"in {path} and {source_paths[workflow_id]}"
                )
            catalog[workflow_id] = workflow
            source_paths[workflow_id] = path

        results: list[dict[str, Any]] = []
        valid = True
        for workflow_id, workflow in sorted(catalog.items()):
            report = validate_workflow(workflow, bundle, catalog)
            valid = valid and report.valid
            results.append(
                {
                    "workflow_id": workflow_id,
                    "path": str(source_paths[workflow_id].relative_to(ROOT)),
                    **report.as_dict(),
                }
            )

        output = {
            "valid": valid,
            "schema_count": len(bundle.schemas),
            "example_count": len(catalog),
            "results": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if valid else 1
    except SchemaLoadError as error:
        print(
            json.dumps(
                {
                    "valid": False,
                    "issues": [
                        {
                            "code": "SCHEMA_LOAD_FAILED",
                            "message": str(error),
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
