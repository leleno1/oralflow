# OralFlow Workflow DSL

## 1. Status and scope

This document defines the M0 serialized workflow language. It describes graph structure and static validation only. Execution semantics beyond the declared state and transition contracts belong to M1.

The initial Schema version is `0.1.0` and uses JSON Schema Draft 2020-12.

## 2. Top-level Workflow

A Workflow contains:

| Field | Purpose |
|---|---|
| `schema_version` | Version of the Workflow serialization contract |
| `workflow_id` | Stable logical identifier |
| `workflow_version` | Semantic version of workflow content |
| `revision` | Immutable revision identifier for a saved definition |
| `name` | Human-readable name |
| `goal` | Explicit expected outcome |
| `status` | Definition lifecycle, initially `draft` or `active` |
| `inputs` | Workflow input contract |
| `roles` | Effective Role definitions |
| `nodes` | Node definitions |
| `edges` | Directed graph edges |
| `policies` | Global limits, permissions, and escalation defaults |
| `success_criteria` | Programmatic or human-verifiable criteria |
| `metadata` | Namespaced extension metadata |

Workflow, Run, and Event versions are distinct. A Run pins one exact Workflow revision.

## 3. Node kinds

M0 recognizes these node kinds:

```text
input
agent_task
code_task
command
transform
gate
human_approval
subworkflow
artifact
terminal
```

Recognition does not mean M0 executes them. Each kind has conditional Schema requirements. For example, `agent_task` requires `role_id`; `subworkflow` requires a workflow reference and bounded context policy; `terminal` requires a terminal outcome.

## 4. Edge structure

Every edge contains:

```json
{
  "id": "edge_unique_id",
  "kind": "sequence",
  "from": {"node_id": "source", "port": "result"},
  "to": {"node_id": "target", "port": "input"}
}
```

Endpoint node IDs must exist. Port names must be declared by their nodes once port compatibility validation is implemented.

## 5. Edge kinds

### `sequence`

Unconditional forward transition. No condition or retry limit is permitted.

### `conditional`

Selects a branch using a restricted expression and a named case.

Required data:

```text
condition.expression
condition.case
```

Expressions may read declared values and use an allowlisted operator set. They must never be evaluated with Python `eval`, JavaScript `eval`, shell expansion, or arbitrary code execution.

### `retry`

Returns control to a prior node or checkpoint after a retryable failure.

Required data:

```text
retry.max_traversals
retry.backoff
retry.on_exhausted
```

`max_traversals` must be at least 1. `on_exhausted` must resolve to a failure, replan, stop, or human-escalation path.

### `error`

Routes a structured node error.

Required data:

```text
match.codes or match.categories
to
```

Catch-all error edges are allowed only when they lead to a terminal or bounded recovery path.

### `subworkflow`

Routes the validated result of a subworkflow node.

Required data:

```text
on_status
result_mapping
to
```

The referenced child Workflow and its budgets are configured on the source subworkflow node. An edge may route `completed`, `failed`, `cancelled`, or `escalated` results.

Supervisor decisions are Events and are not represented by a sixth `supervisory` edge kind.

## 6. Bounded graph rules

A Workflow policy must define:

```text
max_total_transitions
max_duration_seconds
max_failures
max_replans
max_children
max_subworkflow_depth
human_escalation_condition
```

Initial `max_subworkflow_depth` is 3.

Static validation must reject:

- duplicate node, edge, or role IDs;
- missing entry or terminal nodes;
- unreachable nodes;
- edges with unknown endpoints;
- role references that do not resolve;
- cycles with no bounded retry or loop controller;
- retry edges with no maximum;
- retry exhaustion with no exit;
- subworkflows with no maximum depth;
- a child Workflow already present in the ancestor chain;
- a child budget greater than the available parent budget;
- terminal paths that do not declare an outcome.

Every loop must name:

1. its maximum iteration or traversal count;
2. its success exit condition;
3. its failure or exhaustion exit;
4. its human-escalation condition.

## 7. Subworkflow contract

A subworkflow node declares:

```text
workflow_ref
input_mapping
output_mapping
context_policy.isolation
context_policy.return_mode
limits.max_depth
limits.max_children
limits.max_duration_seconds
limits.max_attempts
exit_conditions
escalation_condition
```

The parent receives only a validated summary, artifact references, verdict, open risks, and metrics. It does not inherit the child conversation history.

## 8. Role output gate

An `agent_task` node must identify a Role whose `output_schema` is resolvable. The transition sequence is:

```text
receive provider result
→ normalize to OralFlow result
→ validate output Schema
→ validate permissions and artifact references
→ append accepted or rejected Event
→ allow or deny downstream transition
```

Invalid output never enters downstream node inputs.

## 9. Extension policy

Stable objects reject undeclared fields. Optional product-specific metadata must be placed below `metadata.extensions` using a namespaced key. Extension data must not alter core routing, permissions, budgets, or acceptance semantics.

## 10. Validation order

Workflow validation follows:

```text
JSON
→ Schema
→ identifiers and references
→ graph structure
→ node contracts
→ permissions
→ budgets and recursion
→ artifact references
→ accepted definition
```

Any failure returns a stable error code, instance path, Schema path where applicable, and a human-readable message.
