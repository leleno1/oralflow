# ADR-0002: Deterministic event-sourced M1 Runtime semantics

- Status: accepted for M1 implementation
- Date: 2026-07-31
- Deciders: OralFlow project owner and M1 planning process
- Related tasks: `M1-PLAN-001`, `M1-ARCH-001`
- Supersedes: none
- Superseded by: none

## Context

M0 froze serialized Workflow, Node, Run, and Event contracts but intentionally did not define an executable engine. M1 must prove sequence, condition, finite retry, pause, resume, and event replay without introducing GUI, Agent orchestration, arbitrary code execution, or provider integration.

Three gaps require a durable decision before implementation:

1. `oralflow-expression-0.1` names a language but does not define a safe executable grammar.
2. Event `0.1.0` has no dedicated edge-traversal or checkpoint type, although replay needs transition evidence.
3. Run state must be reproducible from Events, but no EventStore or projection implementation exists.

The current repository also has static M0 examples containing Agent and subworkflow nodes. Treating every Schema-valid Workflow as M1-executable would silently pull later milestones into M1.

## Decision

M1 uses a deterministic, synchronous-at-checkpoints, event-sourced Runtime with a deliberately narrow support matrix.

1. M1 executes only input, deterministic transform, gate, and terminal nodes.
2. M1 routes sequence, conditional, retry, and error edges. Subworkflow edges remain unsupported.
3. `oralflow-expression-0.1` is path-only in M1; it cannot execute operators, calls, indices, templates, or code.
4. A target `NODE_QUEUED` Event records the incoming edge and retry counters under `payload.details.runtime`, so no M0 Schema change is required.
5. Run is a pure projection of a pinned Workflow definition and ordered append-only Events.
6. Event append requires an expected sequence. In-memory and SQLite stores implement one protocol and shared tests.
7. Pause/resume occurs only at checkpoints. Re-entering a user input node without replacement data pauses the Run instead of reusing stale input.
8. M1 tests use synthetic bounded inline data. Sensitive, large, or real user material is forbidden until Artifact storage is implemented.

The detailed normative behavior is in `docs/m1-runtime-semantics.md`.

## Rationale

- A narrow executable subset proves the M1 milestone without coupling Runtime to Agent, GUI, shell, or model concerns.
- Path-only expressions are enough for the toy Workflow and avoid introducing a parser or arbitrary execution surface.
- Recording transition facts on an existing node Event preserves the frozen Event contract while keeping replay deterministic.
- Event sourcing makes pause, resume, audit, and replay one coherent design instead of separate mutable-state mechanisms.
- An EventStore protocol permits fast deterministic unit tests first and durable SQLite proof later without changing the engine contract.

## Alternatives considered

### Add `EDGE_TRAVERSED` and checkpoint Event types immediately

- Benefits: transition facts would have dedicated top-level types.
- Costs: changes a frozen public Schema before Runtime evidence proves the required shape.
- Rejection reason: M1 can express the necessary facts within the declared `payload.details` extension point. A future event-version migration can add dedicated types with evidence.

### Implement a general expression language

- Benefits: richer conditions in early Workflows.
- Costs: parser complexity, security risk, coercion ambiguity, and larger negative-test surface.
- Rejection reason: M1 only needs a validated case selector. General expressions are not required to prove the milestone.

### Persist mutable Run rows as the primary state

- Benefits: straightforward status queries.
- Costs: creates a second source of truth, complicates replay, and permits Event/Run divergence.
- Rejection reason: the M0 architecture explicitly defines Events as facts and Run as projection.

### Implement SQLite before an in-memory store

- Benefits: durable behavior from the first execution task.
- Costs: storage failures obscure domain, event, and projection defects and slow the smallest verification loops.
- Rejection reason: one protocol with an in-memory implementation isolates semantics first; SQLite later passes the same contract suite.

### Execute every Schema-valid node kind with placeholders

- Benefits: apparently broader feature coverage.
- Costs: silent no-op behavior, false success, M2+ scope leakage, and untestable semantics.
- Rejection reason: unsupported behavior must fail explicitly rather than imitate execution.

## Consequences

### Positive

- Every M1 transition is finite, deterministic, observable, and replayable.
- M0 Schemas remain unchanged.
- Tests can inject clock, IDs, delay, and storage without real waiting or external traffic.
- Agent providers, GUI, and persistence details remain outside the domain core.

### Negative

- Schema-valid M0 examples with Agent or subworkflow nodes cannot run in M1.
- Conditions cannot yet compare or calculate values; transforms must emit the branch case.
- Event consumers must understand the `payload.details.runtime` convention until a later Event version adds dedicated transition types.
- M1 inline data is intentionally limited to synthetic, small values.

### Risks and mitigations

- Risk: details fields drift between engine and projector. Mitigation: one typed Runtime details model and shared live/replay tests.
- Risk: retry counters reset after resume. Mitigation: counters derive only from recorded Events.
- Risk: EventStore concurrency produces duplicate sequence numbers. Mitigation: expected-sequence atomic append and unique constraints.
- Risk: expression scope expands informally. Mitigation: grammar and rejection tests are normative; expansion requires ADR review.

## Validation

- Static M0 Schema and contract tests must remain unchanged and pass.
- Each M1 implementation task adds negative tests for its state or error boundary.
- M1 acceptance compares live and replay projections and recreates the Engine over a temporary SQLite database.
- Hosted CI remains the final clean-environment gate.

## Migration and rollback

- Compatibility boundary: serialized contract version `0.1.0` and Runtime semantics version `0.1.0`.
- Migration trigger: a required fact cannot be represented without ambiguous `payload.details`, or a later milestone needs a richer expression/result contract.
- Migration steps: propose a new Schema version and ADR, add dual-read tests, migrate fixtures explicitly, then remove old write behavior only after acceptance.
- Rollback condition: M1 semantics cannot reproduce a Run from Events or requires weakening M0 validation.
- Rollback steps: stop source implementation, revert only unaccepted M1 code, retain M0 contracts and this ADR as decision evidence, and request user direction.

## Review trigger

Review this ADR when any of the following occurs:

- M2 begins Agent execution;
- M6 begins subworkflow execution;
- a dedicated edge/checkpoint Event version is proposed;
- expression operators or functions are requested;
- inline Runtime payloads need real user or sensitive material;
- live and replay projections diverge in any accepted test.

