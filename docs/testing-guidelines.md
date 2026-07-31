# OralFlow Testing Guidelines

## 1. Principles

- Test contracts before Runtime behavior.
- Keep tests deterministic, local, and reproducible.
- Cover rejection behavior as carefully as successful behavior.
- Never call a real model or external API in M0 tests.
- Do not weaken a public contract to make a fixture pass.
- An implementer cannot provide final acceptance for its own change.

## 2. Test layers

### Schema definition tests

Verify every Schema against JSON Schema Draft 2020-12 and preload all `$id` values into an offline registry. No remote `$ref` resolution is allowed.

### Contract fixture tests

Maintain fixtures in:

```text
tests/contract/fixtures/valid/
tests/contract/fixtures/invalid/
```

Each invalid fixture names one expected stable error code. Avoid fixtures containing multiple unrelated violations because they make failures ambiguous.

### Workflow graph tests

Verify:

- unique workflow, role, node, and edge identifiers;
- existing edge endpoints;
- existing role references;
- entry and terminal nodes;
- reachability;
- bounded cycles and retries;
- retry exhaustion paths;
- subworkflow depth, ancestor, budget, and exit rules.

### Adapter contract tests

Run one shared test suite against `MockAgentBackend`. Future provider adapters must pass the same suite. Mock tests verify deterministic results, cancellation, timeout normalization, invalid-output handling, and zero external traffic.

### Application smoke tests

The backend smoke test checks import and health response only. The frontend smoke test checks TypeScript compilation, test execution, and production build. M0 smoke tests do not test workflow execution or a production GUI.

## 3. Required negative cases

At minimum:

- missing or unknown `schema_version`;
- undeclared property on a stable object;
- duplicate node or edge ID;
- unknown role or node reference;
- no entry or terminal node;
- unreachable node;
- cycle with no finite bound;
- retry with no exhaustion route;
- subworkflow with no depth bound or an ancestor cycle;
- Agent role with no output Schema;
- invalid Agent output entering a downstream node;
- Observer with write or routing permission;
- Supervisor with code-write permission;
- Event missing Run identity or timestamp;
- Run referencing an unpinned Workflow revision.

## 4. Test isolation

- Tests use temporary directories supplied by the test framework.
- Tests do not read developer secrets, recordings, or local databases.
- Tests do not depend on order or shared mutable state.
- Clock, IDs, and Mock responses are controlled.
- Network access is denied or mocked.
- Generated files remain outside tracked source directories.

## 5. Commands

Python commands must use the `oralflow` Conda environment:

```powershell
conda run -n oralflow python scripts\validate_examples.py
conda run -n oralflow python -m ruff check .
conda run -n oralflow python -m mypy backend
conda run -n oralflow python -m pytest -q
```

Frontend commands:

```powershell
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Repository check:

```powershell
git diff --check
git status --short
```

## 6. Evidence

Each task report records:

- task ID and goal;
- changed files;
- commands executed;
- pass/fail result;
- relevant test counts;
- review conclusion;
- acceptance conclusion;
- unresolved risks.

A missing command result is not equivalent to a pass.

## 7. Failure ownership

Failures return to the layer that owns the defect:

| Failure | Owning layer |
|---|---|
| Contradictory semantics | Contract documentation |
| Invalid or weak machine rule | JSON Schema |
| Incorrect reference or graph result | Validator |
| Incorrect fixture expectation | Test |
| Framework import or start failure | Application skeleton |
| Local/CI mismatch | CI and environment configuration |

Do not repair a failure in an unrelated downstream layer.

## 8. Acceptance

M0 acceptance runs after implementation tasks are complete and does not modify production files. If a check fails, acceptance returns the task to its owning loop. Two repair attempts are allowed for the same normalized failure; a third identical failure triggers human escalation.
