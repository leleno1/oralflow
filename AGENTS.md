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

## Development Harness Ledger

Development-process records are distinct from product runtime records. Development work is tracked in `docs/progress/` and `logs/development-events.jsonl`; future Workflow, Run, Role, and Agent behavior belongs in the product event store defined by the runtime contracts. Do not mix the two event streams.

1. Every development task must have a unique task ID and a task card under `docs/progress/tasks/`.
2. Before modifying code, configuration, contracts, or documentation, create or update the corresponding task card.
3. Every task card must record the original request, objective, implementation plan, allowed and forbidden scope, prerequisites, and executable acceptance criteria.
4. After implementation, record the actual files changed, commands executed, Diff summary, test commands, results, failures, and retry count.
5. Reviewer and Acceptor conclusions must be structured, identify the evidence reviewed, and remain independent of the implementation decision.
6. A task must not be marked `completed` when plan, Diff, test, review, or acceptance evidence is missing. Failed tests cannot be presented as formal completion evidence.
7. Observer records execution deviations, retries, failures, anomalies, context switches, and unresolved risks as facts; Observer does not route execution or grant acceptance.
8. Supervisor checks record completeness and must block completion or escalate to the user when required evidence is absent.
9. Never store credentials, tokens, private recording content, unredacted personal material, or secrets in task cards, reports, fixtures, or event logs.
10. Every completed task must record its Git branch, final commit hash, changed files, test result, acceptance result, and remote status. Use `pending` until a commit exists; explain `not_applicable` for an approved read-only or no-op task.

Additional ledger rules:

- `docs/progress/PROJECT_STATUS.md` is the project dashboard and must be updated when a task changes milestone status, becomes blocked, is accepted, or changes the next approved task.
- `docs/progress/TASK_TEMPLATE.md` defines the minimum task-card structure and supported development event names.
- `logs/development-events.jsonl` is UTF-8, append-only, and machine-readable: one complete JSON object per non-empty line. Correct prior information with a new event rather than deleting or rewriting history.
- `CHANGELOG.md` contains only user-visible capabilities and significant engineering changes; detailed command history belongs in the task card and event ledger.
- Store detailed test, review, and acceptance evidence under `reports/tests/`, `reports/reviews/`, and `reports/acceptance/` when a task requires standalone reports.
- Do not commit generated runtime logs merely because the development ledger has a tracked exception under `logs/`.

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
