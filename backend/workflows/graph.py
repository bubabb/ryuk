"""Deterministic, persistence-independent workflow dependency-graph contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from backend.workflows.contracts import TaskPacket, canonical_json

MAX_GRAPH_NODES = 100


class NodeState(StrEnum):
    BLOCKED = "blocked"
    READY = "ready"
    RUNNING = "running"
    AWAITING_VALIDATION = "awaiting_validation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"
    SKIPPED = "skipped"


TERMINAL_NODE_STATES = frozenset(
    {
        NodeState.SUCCEEDED,
        NodeState.FAILED,
        NodeState.REJECTED,
        NodeState.CANCELLED,
        NodeState.SKIPPED,
    }
)
UNSUCCESSFUL_NODE_STATES = TERMINAL_NODE_STATES - {NodeState.SUCCEEDED}


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    packet: TaskPacket
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.node_id, str)
            or not self.node_id
            or self.node_id != self.node_id.strip()
        ):
            raise ValueError("Graph node IDs must be nonempty without outer whitespace")
        if not isinstance(self.packet, TaskPacket):
            raise ValueError("Graph nodes require TaskPacket values")
        if not isinstance(self.depends_on, tuple) or any(
            not isinstance(value, str) or not value or value != value.strip()
            for value in self.depends_on
        ):
            raise ValueError("Graph dependencies must contain canonical node IDs")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("Graph dependencies must be unique")
        if tuple(sorted(self.depends_on)) != self.depends_on:
            raise ValueError("Graph dependencies must use canonical sorted order")

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "depends_on": list(self.depends_on),
            "packet": self.packet.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class WorkflowGraph:
    nodes: tuple[GraphNode, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported workflow graph version")
        if (
            not isinstance(self.nodes, tuple)
            or not 1 <= len(self.nodes) <= MAX_GRAPH_NODES
        ):
            raise ValueError(f"Workflow graphs require 1 to {MAX_GRAPH_NODES} nodes")
        if any(not isinstance(node, GraphNode) for node in self.nodes):
            raise ValueError("Workflow graphs require GraphNode values")
        identifiers = tuple(node.node_id for node in self.nodes)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Workflow graph node IDs must be unique")
        if tuple(sorted(identifiers)) != identifiers:
            raise ValueError("Workflow graph nodes must use canonical sorted order")
        known = set(identifiers)
        for node in self.nodes:
            if node.node_id in node.depends_on:
                raise ValueError("Workflow graph nodes cannot depend on themselves")
            if not set(node.depends_on) <= known:
                raise ValueError("Workflow graph dependency does not exist")
        self._require_acyclic()

    def _require_acyclic(self) -> None:
        dependencies = {node.node_id: set(node.depends_on) for node in self.nodes}
        remaining = set(dependencies)
        while remaining:
            ready = {
                node_id
                for node_id in remaining
                if not dependencies[node_id] & remaining
            }
            if not ready:
                raise ValueError("Workflow graph must be acyclic")
            remaining -= ready

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "nodes": [node.to_dict() for node in self.nodes],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WorkflowGraph:
        try:
            if set(value) != {"schema_version", "nodes"}:
                raise ValueError("Invalid workflow graph fields")
            graph = cls(
                tuple(
                    GraphNode(
                        node_id=node["node_id"],
                        depends_on=tuple(node["depends_on"]),
                        packet=TaskPacket.from_dict(node["packet"]),
                    )
                    for node in value["nodes"]
                ),
                schema_version=value["schema_version"],
            )
            if canonical_json(graph.to_dict()) != canonical_json(value):
                raise ValueError("Noncanonical workflow graph")
            return graph
        except (TypeError, KeyError, AttributeError, ValueError) as exc:
            raise ValueError("Invalid workflow graph") from exc

    def initial_state(self) -> GraphState:
        return GraphState(
            self,
            tuple(
                (
                    node.node_id,
                    NodeState.BLOCKED if node.depends_on else NodeState.READY,
                )
                for node in self.nodes
            ),
        )


_ALLOWED_TRANSITIONS = {
    NodeState.READY: frozenset({NodeState.RUNNING, NodeState.CANCELLED}),
    NodeState.RUNNING: frozenset(
        {
            NodeState.AWAITING_VALIDATION,
            NodeState.FAILED,
            NodeState.CANCELLED,
            NodeState.UNCERTAIN,
        }
    ),
    NodeState.AWAITING_VALIDATION: frozenset(
        {NodeState.SUCCEEDED, NodeState.REJECTED, NodeState.CANCELLED}
    ),
    NodeState.UNCERTAIN: frozenset(
        {NodeState.AWAITING_VALIDATION, NodeState.FAILED, NodeState.CANCELLED}
    ),
}


@dataclass(frozen=True, slots=True)
class GraphState:
    graph: WorkflowGraph
    node_states: tuple[tuple[str, NodeState], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.graph, WorkflowGraph) or not isinstance(
            self.node_states, tuple
        ):
            raise ValueError("Graph state requires a graph and canonical node tuple")
        expected = tuple(node.node_id for node in self.graph.nodes)
        actual = tuple(node_id for node_id, _ in self.node_states)
        if actual != expected or any(
            not isinstance(state, NodeState) for _, state in self.node_states
        ):
            raise ValueError("Graph state must cover every node in canonical order")
        states = dict(self.node_states)
        for node in self.graph.nodes:
            state = states[node.node_id]
            dependencies = tuple(states[value] for value in node.depends_on)
            if state is NodeState.BLOCKED and (
                not dependencies
                or all(value is NodeState.SUCCEEDED for value in dependencies)
                or any(value in UNSUCCESSFUL_NODE_STATES for value in dependencies)
            ):
                raise ValueError("Blocked graph node conflicts with dependencies")
            if state in {
                NodeState.READY,
                NodeState.RUNNING,
                NodeState.AWAITING_VALIDATION,
                NodeState.SUCCEEDED,
                NodeState.FAILED,
                NodeState.REJECTED,
                NodeState.CANCELLED,
                NodeState.UNCERTAIN,
            } and any(value is not NodeState.SUCCEEDED for value in dependencies):
                raise ValueError("Scheduled graph node has incomplete dependencies")
            if state is NodeState.SKIPPED and not any(
                value in UNSUCCESSFUL_NODE_STATES for value in dependencies
            ):
                raise ValueError("Skipped graph node requires a failed dependency")

    def state_of(self, node_id: str) -> NodeState:
        try:
            return dict(self.node_states)[node_id]
        except KeyError as exc:
            raise ValueError("Unknown workflow graph node") from exc

    def ready_nodes(self) -> tuple[str, ...]:
        return tuple(
            node_id for node_id, state in self.node_states if state is NodeState.READY
        )

    @property
    def terminal(self) -> bool:
        return all(state in TERMINAL_NODE_STATES for _, state in self.node_states)

    def transition(self, node_id: str, target: NodeState) -> GraphState:
        if not isinstance(target, NodeState):
            raise ValueError("Target must be a NodeState")
        current = self.state_of(node_id)
        if target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise ValueError(f"Illegal graph node transition: {current} -> {target}")
        states = dict(self.node_states)
        states[node_id] = target
        if target in TERMINAL_NODE_STATES:
            self._refresh_waiting_nodes(states)
        return GraphState(
            self.graph,
            tuple((node.node_id, states[node.node_id]) for node in self.graph.nodes),
        )

    def _refresh_waiting_nodes(self, states: dict[str, NodeState]) -> None:
        changed = True
        while changed:
            changed = False
            for node in self.graph.nodes:
                if states[node.node_id] is not NodeState.BLOCKED:
                    continue
                dependency_states = tuple(states[value] for value in node.depends_on)
                if any(
                    state in UNSUCCESSFUL_NODE_STATES for state in dependency_states
                ):
                    states[node.node_id] = NodeState.SKIPPED
                    changed = True
                elif all(state is NodeState.SUCCEEDED for state in dependency_states):
                    states[node.node_id] = NodeState.READY
                    changed = True
