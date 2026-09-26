import pytest

from backend.workflows.graph import GraphNode, NodeState, WorkflowGraph
from tests.test_workflow_store import packet


def graph(*nodes: GraphNode) -> WorkflowGraph:
    return WorkflowGraph(tuple(nodes))


def test_graph_round_trip_and_deterministic_initial_readiness():
    value = graph(
        GraphNode("a", packet("a")),
        GraphNode("b", packet("b")),
        GraphNode("c", packet("c"), ("a", "b")),
    )
    assert WorkflowGraph.from_dict(value.to_dict()) == value
    state = value.initial_state()
    assert state.ready_nodes() == ("a", "b")
    assert state.state_of("c") is NodeState.BLOCKED
    assert not state.terminal


@pytest.mark.parametrize(
    "nodes,match",
    [
        ((GraphNode("a", packet()), GraphNode("a", packet())), "unique"),
        ((GraphNode("a", packet(), ("missing",)),), "does not exist"),
        ((GraphNode("a", packet(), ("a",)),), "cannot depend"),
        (
            (
                GraphNode("a", packet(), ("b",)),
                GraphNode("b", packet(), ("a",)),
            ),
            "acyclic",
        ),
    ],
)
def test_graph_rejects_invalid_topology(nodes, match):
    with pytest.raises(ValueError, match=match):
        graph(*nodes)


def test_graph_rejects_noncanonical_or_future_contracts():
    with pytest.raises(ValueError, match="sorted order"):
        graph(GraphNode("b", packet()), GraphNode("a", packet()))
    with pytest.raises(ValueError, match="canonical sorted order"):
        GraphNode("c", packet(), ("b", "a"))
    with pytest.raises(ValueError, match="Unsupported"):
        WorkflowGraph((GraphNode("a", packet()),), schema_version=2)
    value = graph(GraphNode("a", packet())).to_dict()
    value["extra"] = True
    with pytest.raises(ValueError, match="Invalid workflow graph"):
        WorkflowGraph.from_dict(value)
    with pytest.raises(ValueError, match="GraphNode values"):
        WorkflowGraph((object(),))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="canonical node IDs"):
        GraphNode("b", packet(), (" a",))


def test_success_unlocks_only_after_every_dependency_is_accepted():
    state = graph(
        GraphNode("a", packet("a")),
        GraphNode("b", packet("b")),
        GraphNode("c", packet("c"), ("a", "b")),
    ).initial_state()
    state = state.transition("a", NodeState.RUNNING)
    state = state.transition("a", NodeState.AWAITING_VALIDATION)
    state = state.transition("a", NodeState.SUCCEEDED)
    assert state.ready_nodes() == ("b",)
    assert state.state_of("c") is NodeState.BLOCKED
    state = state.transition("b", NodeState.RUNNING)
    state = state.transition("b", NodeState.AWAITING_VALIDATION)
    state = state.transition("b", NodeState.SUCCEEDED)
    assert state.ready_nodes() == ("c",)


@pytest.mark.parametrize(
    "failure",
    [NodeState.FAILED, NodeState.CANCELLED],
)
def test_execution_failure_skips_all_descendants_but_not_independent_work(failure):
    state = graph(
        GraphNode("a", packet("a")),
        GraphNode("b", packet("b"), ("a",)),
        GraphNode("c", packet("c"), ("b",)),
        GraphNode("d", packet("d")),
    ).initial_state()
    state = state.transition("a", NodeState.RUNNING).transition("a", failure)
    assert state.state_of("b") is NodeState.SKIPPED
    assert state.state_of("c") is NodeState.SKIPPED
    assert state.state_of("d") is NodeState.READY


def test_uncertain_dependency_blocks_until_durable_reconciliation():
    initial = graph(
        GraphNode("a", packet("a")),
        GraphNode("b", packet("b"), ("a",)),
    ).initial_state()
    uncertain = initial.transition("a", NodeState.RUNNING).transition(
        "a", NodeState.UNCERTAIN
    )
    assert uncertain.state_of("b") is NodeState.BLOCKED
    assert not uncertain.terminal

    succeeded = uncertain.transition("a", NodeState.AWAITING_VALIDATION).transition(
        "a", NodeState.SUCCEEDED
    )
    assert succeeded.state_of("b") is NodeState.READY

    failed = uncertain.transition("a", NodeState.FAILED)
    assert failed.state_of("b") is NodeState.SKIPPED


def test_graph_state_rejects_scheduler_invariants_bypassed_by_constructor():
    value = graph(
        GraphNode("a", packet("a")),
        GraphNode("b", packet("b"), ("a",)),
    )
    state_type = type(value.initial_state())
    with pytest.raises(ValueError, match="incomplete dependencies"):
        state_type(value, (("a", NodeState.READY), ("b", NodeState.READY)))
    with pytest.raises(ValueError, match="requires a failed dependency"):
        state_type(value, (("a", NodeState.READY), ("b", NodeState.SKIPPED)))


def test_rejection_skips_descendants_and_complete_graph_becomes_terminal():
    state = graph(
        GraphNode("a", packet("a")),
        GraphNode("b", packet("b"), ("a",)),
    ).initial_state()
    state = state.transition("a", NodeState.RUNNING)
    state = state.transition("a", NodeState.AWAITING_VALIDATION)
    state = state.transition("a", NodeState.REJECTED)
    assert state.state_of("b") is NodeState.SKIPPED
    assert state.terminal


def test_illegal_transition_and_unknown_node_do_not_mutate_state():
    state = graph(GraphNode("a", packet())).initial_state()
    with pytest.raises(ValueError, match="Illegal"):
        state.transition("a", NodeState.SUCCEEDED)
    with pytest.raises(ValueError, match="Unknown"):
        state.transition("missing", NodeState.RUNNING)
    assert state.ready_nodes() == ("a",)
