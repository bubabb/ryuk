import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest

from backend.workflows.graph import GraphNode, NodeState, WorkflowGraph
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_workflow_store import packet


def sample_graph() -> WorkflowGraph:
    return WorkflowGraph(
        (
            GraphNode("a", packet("a")),
            GraphNode("b", packet("b")),
            GraphNode("c", packet("c"), ("a", "b")),
            GraphNode("d", packet("d"), ("c",)),
        )
    )


@pytest.fixture
def store(tmp_path):
    value = SQLiteWorkflowStore(tmp_path / "graphs.db")
    yield value
    value.close()


def test_graph_creation_is_idempotent_tenant_scoped_and_survives_restart(tmp_path):
    path = tmp_path / "graphs.db"
    first = SQLiteWorkflowStore(path)
    graph = sample_graph()
    graph_id = first.create_graph("tenant-a", "request", graph)
    assert first.create_graph("tenant-a", "request", graph) == graph_id
    other = first.create_graph("tenant-b", "request", graph)
    assert other != graph_id
    assert first.get_graph_state("tenant-b", graph_id) is None
    assert first.graph_events("tenant-b", graph_id) == []
    first.close()

    reopened = SQLiteWorkflowStore(path)
    try:
        state = reopened.get_graph_state("tenant-a", graph_id)
        assert state is not None
        assert state.graph == graph
        assert state.ready_nodes() == ("a", "b")
        assert len(reopened.graph_events("tenant-a", graph_id)) == 4
    finally:
        reopened.close()


def test_graph_idempotency_conflict_and_invalid_input_do_not_write(store):
    graph_id = store.create_graph("tenant", "request", sample_graph())
    changed = WorkflowGraph((GraphNode("a", packet("different")),))
    with pytest.raises(WorkflowConflict, match="idempotency"):
        store.create_graph("tenant", "request", changed)
    with pytest.raises(ValueError, match="WorkflowGraph"):
        store.create_graph("tenant", "bad", object())
    assert store.get_graph_state("tenant", graph_id) is not None
    assert store._db.execute("SELECT count(*) FROM workflow_graphs").fetchone()[0] == 1


def test_accepted_dependencies_release_node_in_same_transaction(store):
    graph_id = store.create_graph("tenant", "request", sample_graph())
    for node_id in ("a", "b"):
        store.transition_graph_node("tenant", graph_id, node_id, NodeState.RUNNING)
        store.transition_graph_node(
            "tenant", graph_id, node_id, NodeState.AWAITING_VALIDATION
        )
        state = store.transition_graph_node(
            "tenant", graph_id, node_id, NodeState.SUCCEEDED
        )
    assert state.ready_nodes() == ("c",)
    assert store.list_ready_graph_nodes(10) == [("tenant", graph_id, "c")]
    events = store.graph_events("tenant", graph_id)
    assert [(event["node_id"], event["state"]) for event in events[-2:]] == [
        ("b", "succeeded"),
        ("c", "ready"),
    ]


def test_failure_atomically_skips_all_descendants_and_preserves_other_root(store):
    graph_id = store.create_graph("tenant", "request", sample_graph())
    store.transition_graph_node("tenant", graph_id, "a", NodeState.RUNNING)
    state = store.transition_graph_node("tenant", graph_id, "a", NodeState.FAILED)
    assert state.state_of("c") is NodeState.SKIPPED
    assert state.state_of("d") is NodeState.SKIPPED
    assert state.ready_nodes() == ("b",)
    assert store.list_ready_graph_nodes(10) == [("tenant", graph_id, "b")]


def test_derived_events_follow_causal_order_not_identifier_order(store):
    value = WorkflowGraph(
        (
            GraphNode("a-child", packet("child"), ("z-root",)),
            GraphNode("b-grandchild", packet("grandchild"), ("a-child",)),
            GraphNode("z-root", packet("root")),
        )
    )
    graph_id = store.create_graph("tenant", "inverted", value)
    store.transition_graph_node("tenant", graph_id, "z-root", NodeState.RUNNING)
    store.transition_graph_node("tenant", graph_id, "z-root", NodeState.FAILED)
    assert [
        (event["node_id"], event["state"])
        for event in store.graph_events("tenant", graph_id)[-3:]
    ] == [
        ("z-root", "failed"),
        ("a-child", "skipped"),
        ("b-grandchild", "skipped"),
    ]


def test_event_failure_rolls_back_transition_and_derived_readiness(store, monkeypatch):
    graph_id = store.create_graph("tenant", "request", sample_graph())
    for node_id in ("a", "b"):
        store.transition_graph_node("tenant", graph_id, node_id, NodeState.RUNNING)
        store.transition_graph_node(
            "tenant", graph_id, node_id, NodeState.AWAITING_VALIDATION
        )
    store.transition_graph_node("tenant", graph_id, "a", NodeState.SUCCEEDED)
    before = store.graph_events("tenant", graph_id)

    def fail(*args):
        raise RuntimeError("injected graph event failure")

    monkeypatch.setattr(store, "_graph_event", fail)
    with pytest.raises(RuntimeError, match="injected"):
        store.transition_graph_node("tenant", graph_id, "b", NodeState.SUCCEEDED)
    state = store.get_graph_state("tenant", graph_id)
    assert state is not None
    assert state.state_of("b") is NodeState.AWAITING_VALIDATION
    assert state.state_of("c") is NodeState.BLOCKED
    assert store.graph_events("tenant", graph_id) == before


def test_two_connections_cannot_commit_the_same_graph_transition(tmp_path):
    path = tmp_path / "concurrent.db"
    first, second = SQLiteWorkflowStore(path), SQLiteWorkflowStore(path)
    try:
        graph_id = first.create_graph("tenant", "request", sample_graph())

        def start(store):
            try:
                store.transition_graph_node("tenant", graph_id, "a", NodeState.RUNNING)
                return True
            except WorkflowConflict:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(start, (first, second)))
        assert sorted(outcomes) == [False, True]
        state = first.get_graph_state("tenant", graph_id)
        assert state is not None
        assert state.state_of("a") is NodeState.RUNNING
        assert [
            event["state"]
            for event in first.graph_events("tenant", graph_id)
            if event["node_id"] == "a"
        ] == ["ready", "running"]
    finally:
        first.close()
        second.close()


def test_corrupt_or_incomplete_persisted_graph_state_fails_closed(store):
    graph_id = store.create_graph("tenant", "request", sample_graph())
    store._db.execute(
        "DELETE FROM workflow_graph_nodes WHERE graph_id=? AND node_id='d'",
        (graph_id,),
    )
    with pytest.raises(ValueError, match="Invalid persisted"):
        store.get_graph_state("tenant", graph_id)


def test_v5_migration_is_atomic_and_does_not_invent_graphs(tmp_path, monkeypatch):
    path = tmp_path / "migration.db"
    initial = SQLiteWorkflowStore(path)
    workflow_id = initial.create("tenant", "legacy", packet())
    initial.close()
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE workflow_graph_events")
        db.execute("DROP TABLE workflow_graph_nodes")
        db.execute("DROP TABLE workflow_graphs")
        db.execute("UPDATE workflow_schema SET version=5")

    original = SQLiteWorkflowStore._transaction

    @contextmanager
    def fail(self):
        with original(self):
            yield
            raise RuntimeError("migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteWorkflowStore, "_transaction", fail)
        with pytest.raises(RuntimeError, match="migration failure"):
            SQLiteWorkflowStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 5
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='workflow_graphs'"
        ).fetchall()

    migrated = SQLiteWorkflowStore(path)
    try:
        assert migrated.get("tenant", workflow_id) is not None
        assert migrated.get_graph_state("tenant", "missing") is None
        assert (
            migrated._db.execute("SELECT version FROM workflow_schema").fetchone()[0]
            == 6
        )
    finally:
        migrated.close()


@pytest.mark.parametrize("limit", [0, 1001, True])
def test_ready_graph_snapshot_is_bounded(store, limit):
    with pytest.raises(ValueError, match="between 1 and 1000"):
        store.list_ready_graph_nodes(limit)
