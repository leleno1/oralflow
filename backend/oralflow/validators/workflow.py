"""Static semantic validation for OralFlow Workflow definitions."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from oralflow.validators.schema import (
    JsonObject,
    SchemaBundle,
    ValidationIssue,
    ValidationReport,
    validate_instance,
)

WORKFLOW_SCHEMA_ID = "urn:oralflow:schema:workflow:0.1.0"


def _issue(
    code: str,
    message: str,
    path: str = "",
) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, instance_path=path)


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _reachable(start: Iterable[str], adjacency: dict[str, set[str]]) -> set[str]:
    visited: set[str] = set()
    queue = deque(start)
    while queue:
        node_id = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        queue.extend(adjacency.get(node_id, set()) - visited)
    return visited


def _strongly_connected_components(
    node_ids: Iterable[str],
    adjacency: dict[str, set[str]],
) -> list[set[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(node_id: str) -> None:
        nonlocal index
        indices[node_id] = index
        lowlinks[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)

        for target in adjacency.get(node_id, set()):
            if target not in indices:
                visit(target)
                lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target])
            elif target in on_stack:
                lowlinks[node_id] = min(lowlinks[node_id], indices[target])

        if lowlinks[node_id] != indices[node_id]:
            return

        component: set[str] = set()
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == node_id:
                break
        components.append(component)

    for node_id in node_ids:
        if node_id not in indices:
            visit(node_id)
    return components


def _validate_embedded_schemas(workflow: JsonObject) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for role_index, role in enumerate(workflow["roles"]):
        try:
            Draft202012Validator.check_schema(role["output_schema"])
        except SchemaError as error:
            issues.append(
                _issue(
                    "EMBEDDED_SCHEMA_INVALID",
                    f"Role {role['role_id']} output_schema is invalid: {error.message}",
                    f"/roles/{role_index}/output_schema",
                )
            )

    for node_index, node in enumerate(workflow["nodes"]):
        contracts = (
            ("inputs", "schema"),
            ("config", "schema"),
            ("outputs", "schema"),
            ("error_contract", "schema"),
        )
        for contract_name, schema_name in contracts:
            try:
                Draft202012Validator.check_schema(node[contract_name][schema_name])
            except SchemaError as error:
                issues.append(
                    _issue(
                        "EMBEDDED_SCHEMA_INVALID",
                        f"Node {node['id']} {contract_name}.schema is invalid: {error.message}",
                        f"/nodes/{node_index}/{contract_name}/schema",
                    )
                )
    return issues


def _validate_edge_fields(edge: JsonObject, edge_index: int) -> list[ValidationIssue]:
    common = {"id", "kind", "from", "to"}
    specific = {
        "sequence": set(),
        "conditional": {"condition"},
        "retry": {"retry"},
        "error": {"match"},
        "subworkflow": {"on_status", "result_mapping"},
    }
    allowed = common | specific[edge["kind"]]
    unexpected = sorted(set(edge) - allowed)
    if not unexpected:
        return []
    return [
        _issue(
            "EDGE_KIND_FIELDS_INVALID",
            f"Edge {edge['id']} has fields not allowed for {edge['kind']}: {unexpected}",
            f"/edges/{edge_index}",
        )
    ]


def _validate_bindings(
    workflow: JsonObject,
    nodes_by_id: dict[str, JsonObject],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    workflow_inputs = set(workflow["inputs"].get("properties", {}))
    produced_artifacts: set[str] = set()
    for node in workflow["nodes"]:
        produced_artifacts.update(
            value
            for value in node["outputs"]["destinations"].values()
            if value.startswith("artifact://")
        )

    for node_index, node in enumerate(workflow["nodes"]):
        for binding_name, binding in node["inputs"]["bindings"].items():
            if not isinstance(binding, dict) or "ref" not in binding:
                continue
            reference = binding["ref"]
            path = f"/nodes/{node_index}/inputs/bindings/{binding_name}"
            if reference.startswith("workflow-input://"):
                input_name = reference.removeprefix("workflow-input://")
                if input_name not in workflow_inputs:
                    issues.append(
                        _issue(
                            "WORKFLOW_INPUT_REFERENCE_UNKNOWN",
                            f"Node {node['id']} references unknown workflow input {input_name}",
                            path,
                        )
                    )
            elif reference.startswith("node-output://"):
                target = reference.removeprefix("node-output://")
                parts = target.split("/", maxsplit=1)
                if len(parts) != 2 or parts[0] not in nodes_by_id:
                    issues.append(
                        _issue(
                            "NODE_OUTPUT_REFERENCE_UNKNOWN",
                            f"Node {node['id']} has unknown output reference {reference}",
                            path,
                        )
                    )
                    continue
                source_node = nodes_by_id[parts[0]]
                if parts[1] not in source_node["outputs"]["destinations"]:
                    issues.append(
                        _issue(
                            "NODE_OUTPUT_PORT_UNKNOWN",
                            f"Node {node['id']} references unknown output port {reference}",
                            path,
                        )
                    )
            elif reference.startswith("artifact://") and reference not in produced_artifacts:
                issues.append(
                        _issue(
                            "ARTIFACT_REFERENCE_UNKNOWN",
                            f"Node {node['id']} references artifact with no declared "
                            f"producer: {reference}",
                            path,
                        )
                    )
    return issues


def _validate_subworkflows(
    workflow: JsonObject,
    catalog: dict[str, JsonObject],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    root_limit = workflow["policies"]["max_subworkflow_depth"]

    def walk(current: JsonObject, ancestors: tuple[str, ...], depth: int) -> None:
        current_id = current["workflow_id"]
        if current_id in ancestors:
            cycle = " -> ".join((*ancestors, current_id))
            issues.append(
                _issue(
                    "SUBWORKFLOW_ANCESTOR_CYCLE",
                    f"Subworkflow ancestor cycle detected: {cycle}",
                )
            )
            return
        if depth > root_limit:
            issues.append(
                _issue(
                    "SUBWORKFLOW_DEPTH_EXCEEDED",
                    f"Workflow {current_id} reaches depth {depth}, above limit {root_limit}",
                )
            )
            return

        next_ancestors = (*ancestors, current_id)
        child_nodes = [node for node in current["nodes"] if node["kind"] == "subworkflow"]
        if len(child_nodes) > current["policies"]["max_children"]:
            issues.append(
                _issue(
                    "SUBWORKFLOW_CHILD_LIMIT_EXCEEDED",
                    f"Workflow {current_id} declares {len(child_nodes)} children, "
                    f"above limit {current['policies']['max_children']}",
                )
            )

        for node in child_nodes:
            reference = node["workflow_ref"]
            child_id = reference["workflow_id"]
            child = catalog.get(child_id)
            if child is None:
                issues.append(
                    _issue(
                        "SUBWORKFLOW_REFERENCE_UNKNOWN",
                        f"Node {node['id']} references unknown Workflow {child_id}",
                    )
                )
                continue
            if child["workflow_version"] != reference["version"]:
                issues.append(
                    _issue(
                        "SUBWORKFLOW_VERSION_MISMATCH",
                        f"Node {node['id']} requires {reference['version']} but "
                        f"{child_id} is {child['workflow_version']}",
                    )
                )
            budget = node["budget"]
            if budget["max_depth"] > current["policies"]["max_subworkflow_depth"]:
                issues.append(
                    _issue(
                        "SUBWORKFLOW_NODE_DEPTH_EXCEEDS_POLICY",
                        f"Node {node['id']} max_depth exceeds Workflow policy",
                    )
                )
            if budget["max_children"] > current["policies"]["max_children"]:
                issues.append(
                    _issue(
                        "SUBWORKFLOW_NODE_CHILDREN_EXCEED_POLICY",
                        f"Node {node['id']} max_children exceeds Workflow policy",
                    )
                )
            if budget["max_duration_seconds"] > current["policies"]["max_duration_seconds"]:
                issues.append(
                    _issue(
                        "SUBWORKFLOW_BUDGET_EXCEEDS_PARENT",
                        f"Node {node['id']} duration budget exceeds Workflow budget",
                    )
                )
            walk(child, next_ancestors, depth + 1)

    walk(workflow, (), 1)
    return issues


def validate_workflow(
    workflow: JsonObject,
    bundle: SchemaBundle,
    catalog: dict[str, JsonObject] | None = None,
) -> ValidationReport:
    """Validate one Workflow structurally and semantically."""

    schema_report = validate_instance(workflow, WORKFLOW_SCHEMA_ID, bundle)
    if not schema_report.valid:
        return schema_report

    issues: list[ValidationIssue] = []
    nodes: list[JsonObject] = workflow["nodes"]
    roles: list[JsonObject] = workflow["roles"]
    edges: list[JsonObject] = workflow["edges"]

    node_ids = [node["id"] for node in nodes]
    role_ids = [role["role_id"] for role in roles]
    edge_ids = [edge["id"] for edge in edges]
    nodes_by_id = {node["id"]: node for node in nodes}

    for duplicate in sorted(_duplicates(node_ids)):
        issues.append(_issue("NODE_ID_DUPLICATE", f"Duplicate node ID: {duplicate}"))
    for duplicate in sorted(_duplicates(role_ids)):
        issues.append(_issue("ROLE_ID_DUPLICATE", f"Duplicate role ID: {duplicate}"))
    for duplicate in sorted(_duplicates(edge_ids)):
        issues.append(_issue("EDGE_ID_DUPLICATE", f"Duplicate edge ID: {duplicate}"))

    role_id_set = set(role_ids)
    for index, node in enumerate(nodes):
        if node["kind"] == "agent_task" and node["role_id"] not in role_id_set:
            issues.append(
                _issue(
                    "ROLE_REFERENCE_UNKNOWN",
                    f"Node {node['id']} references unknown Role {node['role_id']}",
                    f"/nodes/{index}/role_id",
                )
            )

    adjacency: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    valid_edges: list[JsonObject] = []
    for index, edge in enumerate(edges):
        source = edge["from"]["node_id"]
        target = edge["to"]["node_id"]
        if source not in nodes_by_id or target not in nodes_by_id:
            issues.append(
                _issue(
                    "EDGE_ENDPOINT_UNKNOWN",
                    f"Edge {edge['id']} references an unknown endpoint",
                    f"/edges/{index}",
                )
            )
            continue
        valid_edges.append(edge)
        adjacency[source].add(target)
        reverse[target].add(source)
        issues.extend(_validate_edge_fields(edge, index))

        source_ports = nodes_by_id[source]["outputs"]["destinations"]
        target_ports = nodes_by_id[target]["inputs"]["bindings"]
        if edge["from"]["port"] not in source_ports and edge["kind"] != "error":
            issues.append(
                _issue(
                    "EDGE_SOURCE_PORT_UNKNOWN",
                    f"Edge {edge['id']} uses undeclared source port {edge['from']['port']}",
                    f"/edges/{index}/from/port",
                )
            )
        if edge["to"]["port"] not in target_ports and edge["kind"] != "error":
            issues.append(
                _issue(
                    "EDGE_TARGET_PORT_UNKNOWN",
                    f"Edge {edge['id']} uses undeclared target port {edge['to']['port']}",
                    f"/edges/{index}/to/port",
                )
            )

    entry_ids = [node["id"] for node in nodes if node["kind"] == "input"]
    terminal_ids = [node["id"] for node in nodes if node["kind"] == "terminal"]
    if not entry_ids:
        issues.append(_issue("WORKFLOW_ENTRY_MISSING", "Workflow has no input entry node"))
    if not terminal_ids:
        issues.append(_issue("WORKFLOW_TERMINAL_MISSING", "Workflow has no terminal node"))

    reachable = _reachable(entry_ids, adjacency)
    for node_id in sorted(set(node_ids) - reachable):
        issues.append(_issue("NODE_UNREACHABLE", f"Node is unreachable: {node_id}"))

    can_reach_terminal = _reachable(terminal_ids, reverse)
    for node_id in sorted(reachable - can_reach_terminal):
        issues.append(
            _issue(
                "TERMINAL_PATH_MISSING",
                f"Reachable node has no path to a terminal: {node_id}",
            )
        )

    for terminal_id in terminal_ids:
        if adjacency.get(terminal_id):
            issues.append(
                _issue(
                    "TERMINAL_HAS_OUTGOING_EDGE",
                    f"Terminal node has outgoing edges: {terminal_id}",
                )
            )

    for component in _strongly_connected_components(node_ids, adjacency):
        has_self_loop = any(
            edge["from"]["node_id"] == edge["to"]["node_id"]
            and edge["from"]["node_id"] in component
            for edge in valid_edges
        )
        if len(component) == 1 and not has_self_loop:
            continue
        internal_edges = [
            edge
            for edge in valid_edges
            if edge["from"]["node_id"] in component and edge["to"]["node_id"] in component
        ]
        if not any(edge["kind"] == "retry" for edge in internal_edges):
            issues.append(
                _issue(
                    "WORKFLOW_CYCLE_UNBOUNDED",
                    f"Cycle has no bounded retry edge: {sorted(component)}",
                )
            )

    issues.extend(_validate_bindings(workflow, nodes_by_id))
    issues.extend(_validate_embedded_schemas(workflow))
    issues.extend(_validate_subworkflows(workflow, catalog or {workflow["workflow_id"]: workflow}))

    unique_issues = {
        (issue.code, issue.message, issue.instance_path, issue.schema_path): issue
        for issue in issues
    }
    ordered = tuple(
        unique_issues[key]
        for key in sorted(unique_issues)
    )
    return ValidationReport(ordered)
