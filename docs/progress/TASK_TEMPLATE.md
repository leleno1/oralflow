# <TASK-ID> <Task title>

## 1. Task status

- Status: `planned`
- Current role: `planner`
- Milestone:
- Created at:
- Updated at:
- Git branch:
- Final commit: `pending`

Allowed status values: `planned`, `awaiting_approval`, `in_progress`, `blocked`, `review_pending`, `acceptance_pending`, `completed`, `failed`, `cancelled`.

## 2. Original request

Record the user's original request without silently broadening or reinterpreting it. Redact credentials, tokens, personal recordings, and unredacted private material.

## 3. Task objective

State one bounded and independently verifiable outcome.

## 4. Scope

### Allowed changes

- List exact files or directories.

### Forbidden changes

- List protected files, directories, capabilities, and external systems.

## 5. Prerequisites

- Required documents, contracts, tasks, environment, and approvals.

## 6. Implementation plan

1. List the smallest executable steps.
2. Include validation after the owning change.
3. Define maximum retry counts, exit conditions, and human-escalation conditions for every loop.

## 7. Acceptance criteria

- Use executable and objectively decidable conditions.
- A task cannot become `completed` without plan, Diff, test, review, and acceptance evidence.

## 8. Actual implementation record

| Time | Actor | Action | Command or evidence | Result |
|---|---|---|---|---|

## 9. File changes

| File | Operation | Description |
|---|---|---|

## 10. Test record

| Command/check | Result | Evidence or failure |
|---|---|---|

## 11. Observer record

Record facts only: deviations, retries, failures, context switches, elapsed-time anomalies, unplanned scope, and unresolved risks. Observer does not route execution or grant acceptance.

## 12. Reviewer conclusion

- Verdict: `pending` / `passed` / `failed` / `conditional`
- Reviewer:
- Findings:
- Required rework:
- Evidence reviewed:

Reviewer must be independent of the implementation decision and must not edit production code while acting as reviewer.

## 13. Supervisor conclusion

- Decision: `CONTINUE` / `RETRY` / `REPLAN` / `ROLLBACK` / `ESCALATE` / `STOP` / `ACCEPT`
- Record completeness: `pending` / `complete` / `incomplete`
- Reason:
- Retry count and limit:
- Human escalation condition:

Supervisor must prevent `completed` when the plan, Diff, tests, review, or acceptance evidence is missing.

## 14. Acceptance result

- Result: `pending` / `passed` / `failed` / `conditional`
- Acceptor:
- Evidence:
- Open issues:
- Follow-up task:

## 15. Git information

- Branch:
- Base commit:
- Final commit: `pending`
- Commit subject:
- Changed files:
- Remote status: `not_pushed` / `pushed` / `not_applicable`

For a read-only or no-op task, explain why no content commit exists. Otherwise a completed task must record its commit hash.

## 16. Follow-up tasks

- List the next bounded tasks without starting them implicitly.

## 17. Final summary

Summarize what was actually delivered, what was verified, and what remains unresolved.

## Development event types

The append-only `logs/development-events.jsonl` ledger supports:

- `task_created`
- `plan_created`
- `plan_approved`
- `implementation_started`
- `file_created`
- `file_modified`
- `command_executed`
- `test_passed`
- `test_failed`
- `review_requested`
- `review_passed`
- `review_failed`
- `acceptance_passed`
- `acceptance_failed`
- `task_blocked`
- `task_completed`

Each line must be one UTF-8 JSON object with at least `schema_version`, `time`, `task_id`, `event`, and `actor`. Corrections append a new event; they do not rewrite history.

