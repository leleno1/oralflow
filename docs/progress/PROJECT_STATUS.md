# OralFlow Project Status

- Last updated: 2026-07-31 19:05 +08:00
- Current milestone: M1 — no-GUI Workflow core
- Milestone verdict: M0 accepted; M1 architecture semantics accepted
- Current task: `M1-PROJECTION-001` (approved, task card pending creation)
- Current task status: `approved`
- Branch: `main`
- Latest recorded implementation commit: `8e3c30f8336b2e5157c7eda22c09160539e9935c`
- Remote tracking: local `main` is ahead of `origin/main`; M1 EventStore commits are pending push

## In progress

| Task | Description | Status | Owner role |
|---|---|---|---|
| `M1-PROJECTION-001` | Implement pure Run projection and deterministic Event replay | `approved` | Developer |

## Completed

| Task | Description | Evidence |
|---|---|---|
| `M0-PLAN-001` | Inspect the repository and define the executable M0 plan | Retrospective task record and M0 commit history |
| M0 implementation | Freeze contracts, validators, tests, shells, and CI | `0cae3ea`, `M0 Quality Gate #1` |
| M0 hosted acceptance | Record the successful hosted quality gate | Local commit `2809b50` |
| `M0-RECORD-001` | Establish and validate the Development Harness Ledger | `ec2fe30`, user acceptance on 2026-07-31 |
| M0 ledger hosted acceptance | Run the closed ledger state on hosted Windows CI | `M0 Quality Gate #2`, head `71d8da2` |
| `M1-PLAN-001` | Plan the no-GUI Workflow core as 12 bounded loops | `8a23019`, user approval on 2026-07-31 |
| `M1-ARCH-001` | Freeze deterministic M1 Runtime semantics and activate M1 repository boundaries | `993acf4`, user acceptance on 2026-07-31 |
| `M1-DOMAIN-001` | Implement strict Run/Event domain models and deterministic Workflow digest | `18e1228`, user acceptance on 2026-07-31 |
| `M1-EVENT-001` | Implement append-only EventStore protocol and deterministic in-memory store | `8e3c30f`, user acceptance on 2026-07-31 |

## Blockers

- No unresolved implementation blocker is known for `M1-PROJECTION-001`.

## Risks

- `M0-PLAN-001` predates the ledger, so its task card is explicitly retrospective and must not imply that the file existed during the original planning turn.
- The development event ledger is manually maintained in M0. Missing or inconsistent events remain possible until automated ledger validation is separately approved.
- Runtime events and development events must remain separate; this ledger is not the future product event store.

## Next task

1. Record and push the accepted `M1-EVENT-001` commits.
2. Create the `M1-PROJECTION-001` task card before projection source changes.
3. Implement and independently validate pure Run projection and replay.
