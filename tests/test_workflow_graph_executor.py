import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from backend.audit.deterministic import ValidationPolicy
from backend.inference.contracts import (
    AdapterInferenceResult,
    InferenceTask,
    TextInput,
    TokenUsage,
)
from backend.inference.router import InferenceRouter
from backend.workflows.contracts import canonical_json
from backend.workflows.graph import GraphNode, NodeState, WorkflowGraph
from backend.workflows.graph_budget import DurableGraphBudget
from backend.workflows.graph_executor import GraphNodeExecutor
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_execution import ControlledEngine, registry
from tests.test_workflow_store import packet


class CapturingEngine(ControlledEngine):
    def __init__(self, name: str, *, output_tokens: int | None = None) -> None:
        super().__init__(name)
        self.seen: list[InferenceTask] = []
        self.reported_output_tokens = output_tokens

    async def generate_task(self, task):
        self.seen.append(task)
        result = await super().generate_task(task)
        return AdapterInferenceResult(
            output=result.output,
            finish_reason=result.finish_reason,
            usage=TokenUsage(output_tokens=self.reported_output_tokens),
            timing=result.timing,
            adapter_metadata=result.adapter_metadata,
        )


def chain_graph() -> WorkflowGraph:
    return WorkflowGraph(
        (
            GraphNode("a", packet("first")),
            GraphNode("b", packet("second"), ("a",)),
            GraphNode("c", packet("third"), ("b",)),
        )
    )


@pytest.fixture
def graph_env(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "executor.db")
    graph_id = store.create_graph("tenant", "request", chain_graph())
    store.bind_graph_budget(
        "tenant",
        graph_id,
        deadline_seconds=60,
        max_attempts=10,
        max_output_tokens=100,
    )
    yield store, graph_id
    store.close()


@pytest.mark.asyncio
async def test_executor_hands_only_accepted_artifact_to_dependent_node(graph_env):
    store, graph_id = graph_env
    engine = CapturingEngine("only", output_tokens=2)
    executor = GraphNodeExecutor(store, InferenceRouter(registry(engine)))
    policy = ValidationPolicy(minimum_chars=1)

    first = await executor.execute("tenant", graph_id, "a", "worker", policy)
    assert first.state == "succeeded"
    artifact = store.get_graph_artifact("tenant", graph_id, "a")
    assert artifact is not None
    second = await executor.execute("tenant", graph_id, "b", "worker", policy)
    assert second.state == "succeeded"

    assert isinstance(engine.seen[1].input, TextInput)
    text = engine.seen[1].input.text
    envelope = json.loads(text.split("RYUK_ACCEPTED_DEPENDENCIES_JSON:\n", 1)[1])
    assert envelope == {
        "schema_version": 1,
        "accepted_dependencies": [
            {
                "node_id": "a",
                "artifact_id": artifact.ref.artifact_id,
                "sha256": artifact.ref.sha256,
                "output": {"text": "only: ok"},
            }
        ],
    }
    budget = store.get_graph_budget("tenant", graph_id)
    assert budget is not None
    assert budget["attempts"] == 2
    assert budget["output_tokens"] == 4


@pytest.mark.asyncio
async def test_rejected_output_skips_descendants_and_is_never_handed_off(graph_env):
    store, graph_id = graph_env
    engine = CapturingEngine("only")
    outcome = await GraphNodeExecutor(store, InferenceRouter(registry(engine))).execute(
        "tenant", graph_id, "a", "worker", ValidationPolicy(minimum_chars=100)
    )
    assert outcome.state == "rejected"
    state = store.get_graph_state("tenant", graph_id)
    assert state is not None
    assert state.state_of("b") is NodeState.SKIPPED
    assert state.state_of("c") is NodeState.SKIPPED
    with pytest.raises(WorkflowConflict, match="not accepted"):
        store.accepted_dependency_artifacts("tenant", graph_id, "b")


@pytest.mark.asyncio
async def test_one_durable_attempt_budget_is_shared_across_nodes(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "budget.db")
    try:
        graph_id = store.create_graph("tenant", "request", chain_graph())
        store.bind_graph_budget(
            "tenant",
            graph_id,
            deadline_seconds=60,
            max_attempts=1,
            max_output_tokens=100,
        )
        executor = GraphNodeExecutor(
            store, InferenceRouter(registry(CapturingEngine("only")))
        )
        policy = ValidationPolicy(minimum_chars=1)
        assert (
            await executor.execute("tenant", graph_id, "a", "worker", policy)
        ).state == "succeeded"
        assert (
            await executor.execute("tenant", graph_id, "b", "worker", policy)
        ).state == "failed"
        budget = store.get_graph_budget("tenant", graph_id)
        assert budget is not None
        assert budget["attempts"] == 1
        state = store.get_graph_state("tenant", graph_id)
        assert state is not None
        assert state.state_of("c") is NodeState.SKIPPED
    finally:
        store.close()


def test_budget_binding_is_immutable_and_survives_restart(tmp_path):
    path = tmp_path / "restart.db"
    store = SQLiteWorkflowStore(path)
    graph_id = store.create_graph("tenant", "request", chain_graph())
    first = store.bind_graph_budget(
        "tenant",
        graph_id,
        deadline_seconds=60,
        max_attempts=3,
        max_output_tokens=20,
    )
    assert (
        store.bind_graph_budget(
            "tenant",
            graph_id,
            deadline_seconds=60,
            max_attempts=3,
            max_output_tokens=20,
        )
        == first
    )
    with pytest.raises(WorkflowConflict, match="already bound"):
        store.bind_graph_budget(
            "tenant",
            graph_id,
            deadline_seconds=60,
            max_attempts=4,
            max_output_tokens=20,
        )
    assert DurableGraphBudget(store, "tenant", graph_id).reserve_attempt()
    store.close()
    reopened = SQLiteWorkflowStore(path)
    try:
        budget = DurableGraphBudget(reopened, "tenant", graph_id)
        assert budget.attempts == 1
        assert budget.max_attempts == 3
    finally:
        reopened.close()


def test_concurrent_attempt_reservation_cannot_exceed_graph_limit(tmp_path):
    path = tmp_path / "concurrent-budget.db"
    first, second = SQLiteWorkflowStore(path), SQLiteWorkflowStore(path)
    try:
        graph_id = first.create_graph("tenant", "request", chain_graph())
        first.bind_graph_budget(
            "tenant",
            graph_id,
            deadline_seconds=60,
            max_attempts=1,
            max_output_tokens=None,
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(
                pool.map(
                    lambda store: store.reserve_graph_attempt("tenant", graph_id),
                    (first, second),
                )
            )
        assert sorted(outcomes) == [False, True]
        budget = first.get_graph_budget("tenant", graph_id)
        assert budget is not None
        assert budget["attempts"] == 1
    finally:
        first.close()
        second.close()


def test_stale_graph_node_lease_cannot_publish_artifact(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "lease.db")
    now = datetime(2026, 9, 26, tzinfo=UTC)
    try:
        graph_id = store.create_graph("tenant", "request", chain_graph())
        store.bind_graph_budget(
            "tenant",
            graph_id,
            deadline_seconds=60,
            max_attempts=2,
            max_output_tokens=20,
            now=now,
        )
        fence = store.claim_graph_node(
            "tenant", graph_id, "a", "worker", lease_seconds=1, now=now
        )
        with pytest.raises(WorkflowConflict, match="Stale"):
            store.complete_graph_node(
                "tenant",
                graph_id,
                "a",
                "worker",
                fence,
                {"output": {"text": "late"}},
                succeeded=True,
                now=now + timedelta(seconds=2),
            )
        assert store.get_graph_artifact("tenant", graph_id, "a") is None
    finally:
        store.close()


def test_v6_graph_migration_adds_execution_state_and_rolls_back(tmp_path, monkeypatch):
    path = tmp_path / "v6.db"
    value = chain_graph()
    graph_id = "legacy-graph"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE workflow_schema(version INTEGER NOT NULL)")
        db.execute("INSERT INTO workflow_schema VALUES (6)")
        db.execute("""CREATE TABLE workflow_graphs (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
            idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
            graph_json TEXT NOT NULL, UNIQUE(tenant, idempotency_key))""")
        db.execute("""CREATE TABLE workflow_graph_nodes (
            graph_id TEXT NOT NULL, node_id TEXT NOT NULL,
            tenant TEXT NOT NULL, state TEXT NOT NULL,
            PRIMARY KEY(graph_id, node_id),
            FOREIGN KEY(graph_id) REFERENCES workflow_graphs(id))""")
        db.execute("""CREATE TABLE workflow_graph_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            graph_id TEXT NOT NULL, node_id TEXT NOT NULL,
            tenant TEXT NOT NULL, state TEXT NOT NULL,
            FOREIGN KEY(graph_id) REFERENCES workflow_graphs(id))""")
        db.execute(
            "INSERT INTO workflow_graphs VALUES (?, 'tenant', 'key', 'hash', ?)",
            (graph_id, canonical_json(value.to_dict())),
        )
        for node_id, state in value.initial_state().node_states:
            db.execute(
                "INSERT INTO workflow_graph_nodes VALUES (?, ?, 'tenant', ?)",
                (graph_id, node_id, state.value),
            )

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
        assert db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 6
        assert "fence" not in {
            row[1] for row in db.execute("PRAGMA table_info(workflow_graph_nodes)")
        }
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='workflow_graph_budgets'"
        ).fetchall()

    migrated = SQLiteWorkflowStore(path)
    try:
        graph_state = migrated.get_graph_state("tenant", graph_id)
        assert graph_state is not None
        assert graph_state.ready_nodes() == ("a",)
        assert migrated.schema_version == 7
        assert (
            migrated._db.execute("SELECT version FROM workflow_schema").fetchone()[0]
            == 7
        )
        migrated.bind_graph_budget(
            "tenant",
            graph_id,
            deadline_seconds=60,
            max_attempts=3,
            max_output_tokens=20,
        )
        assert migrated.claim_graph_node("tenant", graph_id, "a", "worker") == 1
    finally:
        migrated.close()
