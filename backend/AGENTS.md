# Backend Instructions

- Root `AGENTS.md` remains authoritative.
- Keep domain models independent of FastAPI, persistence, and concrete agent providers.
- Framework code belongs under `oralflow/api/`; provider implementations belong under `oralflow/adapters/`.
- M0 may expose only a health endpoint and deterministic Mock adapter behavior.
- Do not implement workflow scheduling, state transitions, persistence, event replay, or external model calls in M0.
- Use Pydantic models with forbidden extra fields at external boundaries.
- All adapter methods use OralFlow domain request and response objects.
- Run Ruff, strict mypy, contract tests, and backend smoke tests for backend changes.
