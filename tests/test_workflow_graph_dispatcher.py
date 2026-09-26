import asyncio

import pytest

from backend.audit.deterministic import ValidationPolicy
from backend.inference.router import InferenceRouter
from backend.workflows.dispatcher import LocalGraphDispatcher
from backend.workflows.graph import GraphNode, NodeState, WorkflowGraph
from backend.workflows.graph_executor import GraphNodeExecutor
from backend.workflows.store import SQLiteWorkflowStore
from backend.workflows.validation import policy_snapshot
from tests.test_execution import ControlledEngine, registry
from tests.test_workflow_store import packet


@pytest.mark.asyncio
async def test_graph_dispatcher_is_explicit_and_runs_dependency_order(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "dispatcher.db")
    engine = ControlledEngine("only")
    try:
        graph = WorkflowGraph(
            (
                GraphNode("a", packet("a")),
                GraphNode("b", packet("b"), ("a",)),
            )
        )
        policy = ValidationPolicy(minimum_chars=1)
        graph_id = store.create_graph(
            "tenant",
            "request",
            graph,
            budget=(60, 2, 20),
            binding={
                "version": "test",
                "policy": policy_snapshot(policy),
                "budget": {},
            },
        )
        dispatcher = LocalGraphDispatcher(
            GraphNodeExecutor(store, InferenceRouter(registry(engine))),
            owner_prefix="graph-worker",
            concurrency=2,
            poll_interval_seconds=0.001,
        )
        assert dispatcher.snapshot.state == "new"
        assert engine.calls == 0
        await dispatcher.start()
        await dispatcher.wait_idle()
        await dispatcher.stop()
        state = store.get_graph_state("tenant", graph_id)
        assert state is not None
        assert state.state_of("a") is NodeState.SUCCEEDED
        assert state.state_of("b") is NodeState.SUCCEEDED
        assert engine.calls == 2
        assert dispatcher.snapshot.completed == 2
        assert dispatcher.snapshot.state == "stopped"
    finally:
        store.close()


@pytest.mark.asyncio
async def test_graph_dispatcher_missing_policy_fails_closed_without_claim(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "policy.db")
    try:
        graph_id = store.create_graph(
            "tenant",
            "request",
            WorkflowGraph((GraphNode("a", packet()),)),
            budget=(60, 1, 20),
        )
        dispatcher = LocalGraphDispatcher(
            GraphNodeExecutor(
                store, InferenceRouter(registry(ControlledEngine("only")))
            ),
            owner_prefix="graph-worker",
            poll_interval_seconds=0.001,
        )
        await dispatcher.start()
        for _ in range(100):
            if dispatcher.snapshot.workflow_conflicts:
                break
            await asyncio.sleep(0.001)
        assert dispatcher.snapshot.workflow_conflicts > 0
        await dispatcher.stop()
        state = store.get_graph_state("tenant", graph_id)
        assert state is not None
        assert state.state_of("a") is NodeState.READY
        assert dispatcher.snapshot.recent_failures[-1].code == "workflow_conflict"
    finally:
        store.close()
