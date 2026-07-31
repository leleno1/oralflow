# OralFlow

OralFlow is a visual multi-agent workflow system built around Harness Engineering. Its first vertical scenario will be English speaking practice, while the workflow contracts, validation, orchestration boundaries, and observability model remain domain-independent.

The project is currently in **M0: engineering Harness and contract freeze**.

## M0 scope

M0 establishes:

- repository and agent development rules;
- architecture and contract documentation;
- versioned JSON Schemas for workflows, nodes, roles, runs, events, and artifacts;
- deterministic example workflows and offline validators;
- automated contract tests;
- minimal React/Vite and FastAPI scaffolding;
- a provider-neutral `AgentBackend` boundary with a deterministic mock;
- local and CI quality checks.

M0 does not implement:

- the workflow Runtime;
- the workflow editor GUI;
- English-speaking training;
- Codex SDK, OpenAI API, or real model calls;
- Docker, Redis, PostgreSQL, or cloud deployment.

## Source of truth

- [`docs/development-spec.md`](docs/development-spec.md) defines product boundaries and milestone intent.
- [`AGENTS.md`](AGENTS.md) defines repository-wide implementation and validation rules.
- More specific rules may be added under `frontend/` and `backend/` as those skeletons are created.

## Target environment

| Component | Target |
|---|---|
| Operating system | Windows |
| Node.js | 22.x |
| Package manager | npm |
| Python | 3.12 |
| Conda environment | `oralflow` |
| Backend | FastAPI + Pydantic |
| Frontend | React + TypeScript + Vite |
| MVP storage | SQLite + local files |

The unqualified `python` command on a developer machine may point to another installation. Prefer commands scoped to the project environment:

```powershell
conda run -n oralflow python --version
```

## Environment setup

Dependency installation requires explicit approval under the repository rules.

Once approved, create the Python environment from the repository root:

```powershell
conda env create -f environment.yml
conda run -n oralflow python --version
conda run -n oralflow python -m pip check
```

When the frontend skeleton exists, install its locked dependencies with:

```powershell
npm --prefix frontend ci
```

## Planned validation entry points

The following commands become available as their M0 task loops are implemented:

```powershell
conda run -n oralflow python scripts\validate_examples.py
conda run -n oralflow python -m ruff check .
conda run -n oralflow python -m mypy backend
conda run -n oralflow python -m pytest -q

npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

No M0 test may call a real model or external API.

## Development workflow

Each change is handled as one bounded loop:

1. read repository instructions and relevant contracts;
2. inspect Git status and existing interfaces;
3. state allowed and forbidden paths;
4. implement one independently verifiable objective;
5. run the narrowest relevant checks;
6. report changed files, evidence, and unresolved risks;
7. obtain independent acceptance before declaring completion.

Every retry, graph cycle, replan path, and subworkflow must declare a maximum bound, an exit condition, and a human-escalation condition.

## Repository status

M0 is in progress. The repository currently contains the governing specification and root-level development rules. Contract documents, Schemas, examples, validators, tests, and application skeletons will be added in subsequent M0 loops.
