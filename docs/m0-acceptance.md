# OralFlow M0 Acceptance Record

- Task: M0 — Engineering Harness and contract freeze
- Date: 2026-07-31
- Local verdict: Accepted
- Final verdict: Accepted
- Branch: `main`
- CI definition commit: `3556627`
- Acceptance source commit: `0cae3ea09f6a50dc8056773f788f673559c5dddb`
- Remote: `https://github.com/leleno1/oralflow.git`

## 1. Scope result

M0 delivered repository governance, environment configuration, architecture and contract documentation, versioned JSON Schemas, deterministic examples, offline validators, automated tests, frontend/backend application shells, a provider-neutral Agent adapter, and a Windows CI definition.

M0 did not implement:

- workflow Runtime execution;
- graph editing or production GUI behavior;
- English-speaking training;
- Codex SDK, OpenAI API, or real model calls;
- Docker, Redis, PostgreSQL, or cloud deployment.

Static source inspection found zero real model SDK imports and zero Runtime implementation files.

## 2. Required artifacts

The acceptance inventory checked 27 required paths and found none missing.

Key groups:

- repository: `AGENTS.md`, `README.md`, `.gitignore`;
- environment: `environment.yml`, `pyproject.toml`;
- contracts: architecture, Workflow DSL, Node, Role, testing, and versioning ADR;
- Schemas: Workflow, Node, Role, Run, Event, and Artifact;
- examples: one root Workflow and one child Workflow;
- validation: offline Schema registry and graph validator;
- tests: valid, invalid, permission, adapter, and API smoke tests;
- shells: React/Vite status page and FastAPI health endpoint;
- CI: `.github/workflows/ci.yml`.

At acceptance time Git tracked 59 files before this report was added.

## 3. Contract evidence

The offline validator reported:

```text
schema_count=6
example_count=2
valid=true
```

The example set verifies:

- explicit Schema and Workflow versions;
- Node and Role references;
- `sequence`, `conditional`, `retry`, `error`, and `subworkflow` edges;
- finite retry exhaustion;
- structured error routing;
- child Workflow version resolution;
- maximum subworkflow depth;
- role output Schema;
- success and failure terminals.

The validator additionally checks IDs, references, edge fields, ports, reachability, terminal paths, bounded strongly connected components, embedded Schemas, artifacts, child budgets, versions, and ancestor cycles.

## 4. Test evidence

Python:

```text
Python 3.12.13
Ruff: passed
mypy --strict: passed, 18 source files
pytest: 16 passed
pip check: no broken requirements
```

Frontend:

```text
ESLint: passed
TypeScript: passed
Vitest: 1 passed
Vite production build: passed
npm audit: 0 vulnerabilities
```

The production dependency audit separately reported zero vulnerabilities.

## 5. Adapter evidence

`AgentBackend` is defined only in terms of OralFlow domain request and response models.

`MockAgentBackend`:

- uses fixed local fixtures;
- returns deterministic results;
- supports context creation, resume, fork, compact, role run, and cancellation;
- produces structured failures for unknown fixtures;
- performs no network or model call.

No Codex adapter implementation exists in M0.

## 6. Git evidence

M0 was implemented as bounded local commits:

```text
6a17c79 chore(repo): initialize governance and project specification
b44db64 build: define M0 project environment
44894f5 docs: freeze M0 architecture and contracts
9940112 fix(build): bootstrap dependencies before package skeleton
5a714be feat(contracts): add versioned M0 schemas
564a3cb test(fixtures): add minimal contract workflows
c1b13a6 build: add jsonschema typing support
d3783d3 feat(validation): add offline workflow contract validator
adeea4f test(contracts): cover valid and rejected M0 definitions
76661a5 feat(scaffold): add M0 frontend and backend shells
3556627 ci: add Windows M0 quality gate
```

No remote, tag, release, or push was created during the bounded local implementation loops. After local acceptance, `main` was pushed to the approved `origin` remote and configured to track `origin/main`.

## 7. Remote CI evidence and residual risks

### Remote CI passed

The first hosted run passed from the pushed `main` branch:

```text
Workflow run: M0 Quality Gate #1
Head commit: 0cae3ea
Branch: main
Conclusion: success
Duration: 4m 24s
Evidence reviewed: 2026-07-31
```

The run is listed at `https://github.com/leleno1/oralflow/actions`. The immutable workflow run number and head commit were verified from the user-supplied GitHub Actions result.

### Clean environment proof complete

The local Conda environment was repaired after an interrupted initial installation and passes dependency checks. `M0 Quality Gate #1` independently reproduced the environment and passed all checks on hosted `windows-latest`.

### Transitive deprecation notice

npm reports a deprecation notice for `whatwg-encoding`, a transitive development dependency. The complete npm audit reports zero vulnerabilities, so this is recorded as a non-blocking upstream maintenance observation.

## 8. Final acceptance condition

M0 acceptance conditions:

1. [x] the repository is pushed to the approved remote;
2. [x] the `M0 Quality Gate` GitHub Actions workflow runs on `windows-latest`;
3. [x] all workflow steps pass from a clean checkout;
4. [x] the immutable run identifier and head commit are recorded here;
5. [x] the user supplied the successful hosted-run evidence and authorized continuation.

M0 is accepted. M1 remains outside this task and must begin only under a separately approved scope.
