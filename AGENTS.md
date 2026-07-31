# OralFlow Repository Instructions

## Source of truth

- Before making changes, read this file and the relevant documents under `docs/`.
- `docs/development-spec.md` defines the product boundary and milestone intent.
- If an implementation request conflicts with the development specification, stop and ask for a decision instead of silently choosing one.
- More specific `AGENTS.md` files may tighten these rules for their directory, but must not relax root-level safety or validation requirements.

## Current milestone

- The current milestone is M0: engineering Harness and contract freeze.
- M0 may establish documentation, schemas, examples, validators, tests, empty frontend/backend scaffolding, and CI.
- Do not implement the workflow Runtime, production GUI, English-training features, real model calls, or external service integrations during M0.
- Do not add Codex SDK, OpenAI API, Redis, PostgreSQL, Docker, or cloud infrastructure unless a later approved task explicitly requires them.

## Harness Engineering rules

1. Schema first: define and review contracts before business behavior.
2. Work in one bounded, independently verifiable task loop at a time.
3. Every task must name its allowed paths, forbidden paths, expected artifacts, validation commands, and acceptance criteria.
4. Do not expand task scope to fix unrelated issues.
5. Agent-generated output must pass its declared Schema or programmatic validator before downstream use.
6. Every retry, loop, replan path, and subworkflow must have a maximum count or depth, an exit condition, and a human-escalation condition.
7. Record runtime and role behavior as structured, append-only events when those capabilities are implemented.
8. Keep the workflow core independent of any concrete agent SDK. Integrations belong behind an adapter interface.
9. Preserve independent review: an implementer cannot grant final acceptance to its own change.
10. Never mark a task accepted without reproducible validation evidence.

## Change discipline

- Inspect the current Git status and relevant files before editing.
- Preserve user changes and avoid unrelated formatting or refactors.
- Do not modify `docs/development-spec.md` unless the task explicitly authorizes changing the governing specification.
- Use UTF-8 for text files.
- Prefer small, reviewable changes. If a required fix crosses the approved path boundary, stop and request approval.
- Do not create commits, tags, branches, remotes, pull requests, or releases unless explicitly requested.
- Do not delete, overwrite, migrate, publish, or access production data without explicit confirmation.
- Do not install or upgrade dependencies without explicit approval.

## Environment

- Target operating system: Windows.
- Node.js package manager: npm.
- Python target: Python 3.12 in the Miniconda environment named `oralflow`.
- Do not rely on the unqualified `python` command until the `oralflow` environment is confirmed active.
- Prefer `conda run -n oralflow python ...` for reproducible Python commands.
- MVP persistence is SQLite plus local files.

## Contracts and validation

- Use JSON Schema Draft 2020-12 unless an approved architecture decision changes it.
- Keep Schema validation deterministic and offline; do not resolve remote references during tests.
- Stable contract objects should reject undeclared properties unless a documented extension point permits them.
- Validate both successful and failing examples.
- Static workflow validation must cover identifier uniqueness, references, graph reachability, bounded cycles, terminal paths, role permissions, budgets, and subworkflow limits.
- Agent output validation failure must produce a structured failure and follow a bounded retry, replan, or escalation path.

## Architecture boundaries

- Domain contracts must not import FastAPI, React, database drivers, or concrete agent SDK types.
- `AgentBackend` is the boundary for agent providers.
- `MockAgentBackend` must be deterministic and use fixed fixtures.
- A future Codex adapter must translate provider requests, responses, and failures into OralFlow domain types.
- Observer records facts and deviations but does not route execution.
- Supervisor consumes events and issues control decisions but does not produce business artifacts or modify application code.

## Testing and acceptance

- Run the narrowest relevant tests after each atomic change.
- Before M0 acceptance, run Schema checks, contract tests, Python lint and type checks, frontend type checks and tests, and the production frontend build.
- Tests must cover negative cases such as invalid references, unbounded retries, excessive nesting, missing output schemas, and permission violations.
- If validation fails, fix the owning layer; do not weaken a public contract merely to make a test pass.
- Report changed files, commands run, results, and unresolved risks at task completion.

## Data and secrets

- Never commit `.env` files, credentials, tokens, private recordings, local databases, generated artifacts, or user work materials.
- Logs and fixtures must not contain secrets or personally identifying source material.
- Tests must not call real models or external APIs unless a later task explicitly authorizes an integration test.
