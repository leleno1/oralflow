# OralFlow Role Contracts

## 1. Purpose

Roles define responsibility, context, permission, output, and budget boundaries independently of a concrete model provider. A Workflow binds nodes to roles; an adapter later resolves the configured backend.

## 2. Common Role configuration

Every Role declares:

| Field | Meaning |
|---|---|
| `schema_version` | Role contract version |
| `role_id` | Stable identifier within Workflow scope |
| `role_type` | One of the registered 7+1 role types |
| `skill_ref` | Versioned role instruction reference |
| `model_profile` | Capability profile, never a hard-coded provider model |
| `personality_profile` | Behavioral profile identifier |
| `backend_profile` | Provider-neutral backend selection profile |
| `context_policy` | Allowed files, artifacts, summaries, and history |
| `permission_policy` | Tool, command, path, network, and mutation limits |
| `input_artifact_types` | Declared accepted artifact classes |
| `output_schema` | JSON Schema required for the role result |
| `timeout_seconds` | Per-attempt time limit |
| `max_attempts` | Finite attempt count |
| `escalation_policy` | Conditions and target for human escalation |

A Role with no resolvable output Schema is invalid.

## 3. The 7+1 roles

### R1 — Intent Agent

- Converts user intent into explicit goals, constraints, and acceptance criteria.
- Reads only declared project material.
- Produces `task_intent`.
- Cannot modify the repository.

### R2 — Planner

- Splits accepted intent into bounded, independently verifiable tasks.
- Declares dependencies, allowed paths, checks, budgets, exits, and escalation.
- Produces `plan`.
- Cannot modify the repository.

### R3 — Plan Critic

- Checks missing dependencies, unverifiable outcomes, unsafe permissions, unbounded loops, and scope drift.
- Receives the plan and necessary architecture context, not the Planner conversation.
- Produces `plan_review`.
- Cannot modify the repository or approve implementation evidence.

### R4 — Implementer

- Changes only approved paths and runs approved commands.
- Produces the change plus `patch_manifest`.
- Cannot grant final acceptance.
- Must stop when a fix requires an unapproved path.

### R5 — Observer

- Subscribes to validated Events.
- Records timing, budgets, deviation, repeated failures, and unresolved risks.
- Produces append-only observations.
- Cannot change execution state, route the Workflow, modify code, or declare acceptance.

### R6 — Reviewer

- Reviews diffs, contracts, tests, maintainability, safety, and regressions.
- Uses a read-only evidence view independent of the Implementer context.
- Produces `review_report`.
- Cannot fix issues it identifies within the same role run.

### R7 — Acceptance Agent

- Executes approved acceptance checks and maps evidence to user criteria.
- Produces `acceptance_report`.
- May run tests but cannot modify production code.
- Rejects missing or non-reproducible evidence.

### R8 — Supervisor

- Consumes Events, observations, budgets, and checkpoint evidence.
- Produces one control decision: `CONTINUE`, `RETRY`, `REPLAN`, `ROLLBACK`, `ESCALATE`, `STOP`, or `ACCEPT`.
- Cannot produce business artifacts or modify code.
- Must include rationale, evidence references, and remaining budget.

## 4. Context isolation

Each invocation receives a Context Capsule containing:

```text
goal
constraints
relevant_files
prior_artifact_refs
acceptance_criteria
budget
ancestor_workflow_ids
```

Default behavior:

- do not copy full conversation history;
- grant only files and artifacts required for the current task;
- return summaries and accepted artifact references to a parent;
- compact history without deleting decision or evidence indexes;
- merge only accepted artifacts.

Planner, Critic, Reviewer, Acceptance, Observer, and Supervisor are read-only unless their specific task requires a narrower approved capability. Implementer write paths are explicit.

## 5. Permission model

Permission evaluation is deny-by-default.

Command classes:

```text
safe
review_required
dangerous
```

- `safe`: read operations, lint, type checks, approved tests.
- `review_required`: dependency installation, migrations, or broad formatting.
- `dangerous`: deletion, overwrite, release, production access, or secret operations.

Dangerous actions always require human confirmation. A Role or Node cannot grant itself more permission than the repository policy.

## 6. Output validation

Role output handling is:

```text
provider response
→ adapter normalization
→ output Schema validation
→ permission and artifact checks
→ accepted/rejected Event
→ downstream eligibility
```

Failure to validate is not a successful role result. Retry and replan behavior is finite, and repeated identical failures lead to human escalation.

## 7. Observer/Supervisor boundary

Observer reports facts without authority. Supervisor makes control decisions without changing business artifacts.

The Supervisor must not reinterpret an invalid Agent output as valid. It may request retry, replan, stop, or escalation, but only a successful Schema/program validation permits the data to enter the next stage.

## 8. AgentBackend boundary

The provider-neutral interface accepts domain requests and returns domain results. It conceptually supports:

```text
start_context(request) -> context_ref
run_role(request) -> role_run_result
resume_context(context_id) -> context_ref
fork_context(context_id, checkpoint) -> context_ref
compact_context(context_id) -> completion
cancel(run_id) -> completion
```

`MockAgentBackend`:

- uses local fixed fixtures;
- is deterministic;
- emits no network traffic;
- returns the same domain result shape as every future provider;
- can deliberately return invalid fixtures for negative tests.

Future Codex integration:

- lives only in an adapter module;
- imports no SDK types into domain contracts;
- maps provider errors to OralFlow errors;
- respects context, path, tool, timeout, cancellation, and budget policies;
- is not implemented during M0.
