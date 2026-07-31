# Backend Instructions

- Root `AGENTS.md` remains authoritative.
- Keep domain models independent of FastAPI, persistence, and concrete agent providers.
- Framework code belongs under `oralflow/api/`; provider implementations belong under `oralflow/adapters/`.
- M1 may implement only the deterministic Runtime subset declared in `docs/m1-runtime-semantics.md`.
- Keep Run/Event contracts under the domain layer, EventStore implementations under `oralflow/events/`, and execution/projection logic under `oralflow/runtime/`.
- M1 handlers are pure and allowlisted. Do not use `eval`, dynamic imports, shell execution, network access, framework objects, database handles, or AgentBackend inside a node handler.
- Treat Events as append-only facts and Run as a pure projection. Never update or delete historical Events to repair state.
- Use injected clocks, ID factories, delay strategies, and EventStore protocols so tests remain deterministic and do not sleep.
- The M1 executable node subset is `input`, `transform`, `gate`, and `terminal`; the executable edge subset is `sequence`, `conditional`, `retry`, and `error`.
- Reject unsupported `agent_task`, `code_task`, `command`, `human_approval`, `subworkflow`, `artifact`, and subworkflow edges before execution.
- SQLite work must use the Python standard library, transactional expected-sequence append, unique Event constraints, and pytest temporary directories.
- Do not implement external model calls, Agent orchestration, GUI behavior, production databases, or M2+ capabilities in M1.
- Use Pydantic models with forbidden extra fields at external boundaries.
- All adapter methods use OralFlow domain request and response objects.
- Run the narrowest Runtime tests after each change, then Ruff, strict mypy, contract tests, and backend smoke tests before task acceptance.
