# ADR-0001: M0 Contract and Versioning Conventions

- Status: Accepted
- Date: 2026-07-31
- Scope: M0 public serialized contracts

## Context

OralFlow needs stable machine-readable contracts before Runtime, GUI, or real Agent integration. The development specification and M0 task list used different edge vocabulary and differed on whether Artifact was a first-class M0 Schema.

Contracts must be versioned, validated offline, strict by default, and capable of future migration.

## Decision

### Schema dialect

Use JSON Schema Draft 2020-12.

Each Schema uses a versioned URN identifier:

```text
urn:oralflow:schema:<type>:<schema-version>
```

Validators preload known Schemas into a local registry. They never fetch remote Schema content.

### Initial versions

The initial contract version is `0.1.0`.

Every serialized Workflow, Node, Role, Run, Event, and Artifact includes `schema_version`.

Workflow content additionally includes:

- `workflow_version`: semantic version of the authored definition;
- `revision`: immutable saved revision identifier.

A Run pins Workflow ID, Workflow version, revision, and content digest.

### Version changes

Before 1.0:

- compatible clarification or correction increments patch;
- breaking field or semantic changes increment minor.

At and after 1.0, normal Semantic Versioning applies.

Unknown versions are rejected. Readers do not silently coerce or discard fields.

Migration is explicit:

```text
read original
→ validate source version
→ apply one versioned pure migration
→ validate target version
→ run semantic validators
→ persist as a new revision
```

M0 documents this process but does not implement a migration engine.

### Strictness and extensions

Stable objects use `additionalProperties: false`. Optional product extensions live under a namespaced `metadata.extensions` object and may not alter routing, permissions, budgets, or acceptance semantics.

### Core Schema set

M0 includes:

- Workflow
- Node
- Role
- Run
- Event
- Artifact

Artifact is included because Node output, Event evidence, and Run provenance require one shared reference contract.

### Edge vocabulary

The canonical M0 edge kinds are:

```text
sequence
conditional
retry
error
subworkflow
```

The former `normal` term is replaced by `sequence`.

Supervisor decisions are represented as structured Events rather than a `supervisory` edge. This keeps the declared data/control graph separate from control-plane governance.

### Examples

M0 examples live in the root `examples/` directory. A future executable workflow registry may be introduced under `workflows/` in M1 without moving or reinterpreting M0 contract fixtures.

## Consequences

- All public instances carry explicit version information.
- Schema validation remains deterministic and offline.
- Artifact references gain one common format.
- Graph tooling has five stable edge kinds.
- Supervisor actions remain observable without becoming graph data edges.
- Breaking changes require a documented migration instead of silent compatibility behavior.
