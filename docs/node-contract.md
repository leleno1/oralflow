# OralFlow Node Contract

## 1. Purpose

Every node uses one envelope so that validation, observability, error routing, and future adapters do not require node-specific special cases.

M0 defines and validates this envelope. Node execution begins in M1.

## 2. Node envelope

```text
identity
inputs
config
outputs
error_contract
execution_policy
permissions
metadata
```

### Identity

Required fields:

- `schema_version`
- `id`
- `kind`
- `name`

Conditionally required fields include `role_id` for agent tasks, `workflow_ref` for subworkflows, and `outcome` for terminal nodes.

### Inputs

Inputs separate bindings from their accepted structure:

```json
{
  "bindings": {
    "plan": {"ref": "artifact://plan.json"}
  },
  "schema": {
    "type": "object",
    "required": ["plan"]
  }
}
```

A binding may refer to a workflow input, prior node output, artifact, or approved file. References are data, not executable strings.

### Config

`config.values` contains node configuration. `config.schema` constrains it. Configuration is validated before a node is queued.

Configuration must not contain unrestricted shell fragments, model secrets, or undeclared filesystem permissions.

### Outputs

Outputs declare names, destination or artifact policy, and a JSON Schema:

```json
{
  "schema": {
    "type": "object",
    "required": ["verdict"],
    "properties": {
      "verdict": {"enum": ["approved", "rejected"]}
    },
    "additionalProperties": false
  }
}
```

Produced output is untrusted until it passes this Schema. An Agent output cannot advance the Workflow merely because the provider call succeeded.

### Error contract

Every node declares allowed error categories or codes and whether each is retryable. The common error envelope is:

```text
code
message
category
retryable
details
cause_event_id
```

Errors must not embed secrets, arbitrary exceptions, or unlimited logs. Full diagnostic material belongs in a redacted Artifact.

### Execution policy

Required bounds depend on node kind:

- `timeout_seconds`
- `max_attempts`
- `exit_conditions`
- `escalation_condition`

Subworkflow nodes additionally require depth, child-count, and inherited-budget limits.

### Permissions

Node permissions may narrow Role permissions but cannot widen them. Effective permissions are the intersection of:

```text
repository policy
workflow policy
role policy
node policy
human approvals
```

## 3. Kind-specific requirements

| Kind | Additional contract |
|---|---|
| `input` | input source and sanitization policy |
| `agent_task` | `role_id` and resolvable role output Schema |
| `code_task` | allowed write paths and command classes |
| `command` | command identifier from an allowlisted registry |
| `transform` | deterministic transform identifier |
| `gate` | restricted condition expression and branch cases |
| `human_approval` | prompt, timeout, and timeout outcome |
| `subworkflow` | workflow reference, mappings, isolation, budgets |
| `artifact` | media type, digest policy, retention policy |
| `terminal` | `success`, `failure`, or `cancelled` outcome |

## 4. Reference rules

- Node IDs are unique inside a Workflow revision.
- `role_id` resolves in the effective Workflow role set.
- Input references point only to declared workflow inputs, prior reachable nodes, artifacts, or approved files.
- Output names are unique per node.
- A file reference does not grant file access; permissions are checked separately.
- A subworkflow reference cannot point to the current Workflow or any ancestor.

## 5. Validation and transition

Before execution:

1. validate the Node envelope;
2. resolve inputs;
3. validate input values;
4. validate configuration;
5. compute effective permissions and budgets.

After execution:

1. normalize provider or tool output;
2. validate output or error;
3. persist or reference declared Artifacts;
4. append a structured Event;
5. select only an eligible edge.

If output validation fails, downstream transitions are blocked.

## 6. Retry and failure rules

- `max_attempts` is always finite and at least 1.
- A retryable error may use a retry edge only while its traversal budget remains.
- Two consecutive failures with the same normalized error default to `REPLAN`.
- Three consecutive failures with the same normalized error default to `ESCALATE`.
- Timeout exhaustion follows the declared error or escalation path.
- Missing exit behavior is a static contract error.

## 7. Observability

Each node attempt must eventually be representable by Events for:

```text
queued
started
input_validated or input_rejected
output_validated or output_rejected
succeeded, failed, skipped, cancelled, or waiting_approval
```

M0 validates the event shapes but does not execute or store these transitions.
