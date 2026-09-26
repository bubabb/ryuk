import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import backend.main as main
from backend.inference.router import InferenceRouter
from backend.workflows.graph import NodeState
from backend.workflows.graph_executor import GraphNodeExecutor
from backend.workflows.store import WorkflowConflict
from tests.test_execution import ControlledEngine, registry

pytest_plugins = ("tests.test_workflow_api",)

GRAPH_BODY: dict[str, Any] = {
    "idempotency_key": "graph-1",
    "nodes": [
        {
            "node_id": "first",
            "prompt": "synthetic first",
            "model": "test",
            "max_tokens": 16,
            "depends_on": [],
        },
        {
            "node_id": "second",
            "prompt": "synthetic second",
            "model": "test",
            "max_tokens": 16,
            "depends_on": ["first"],
        },
    ],
}


def create_graph(env, who="a"):
    response = env[1][who].post("/v1/workflow-graphs", json=GRAPH_BODY)
    assert response.status_code == 202, response.text
    return response.json()["graph_id"]


def test_graph_creation_is_governed_idempotent_and_never_dispatches(env, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("creation must not dispatch")

    monkeypatch.setattr(main.inference_router, "generate_task", forbidden)
    graph_id = create_graph(env)
    assert create_graph(env) == graph_id
    response = env[1]["a"].get(f"/v1/workflow-graphs/{graph_id}")
    assert response.status_code == 200
    assert response.json() == {
        "graph_id": graph_id,
        "state": "active",
        "terminal": False,
        "nodes": [
            {"node_id": "first", "state": "ready"},
            {"node_id": "second", "state": "blocked"},
        ],
    }
    budget = env[0].get_graph_budget("a", graph_id)
    assert budget is not None
    assert budget["max_attempts"] == 2
    assert env[0].get_graph_binding("a", graph_id) == env[3]["a"].binding()


def test_graph_creation_rolls_back_graph_nodes_and_budget_together(env, monkeypatch):
    def fail(*args):
        raise sqlite3.OperationalError("injected graph creation failure")

    monkeypatch.setattr(env[0], "_graph_event", fail)
    response = env[1]["a"].post("/v1/workflow-graphs", json=GRAPH_BODY)
    assert response.status_code == 503
    assert env[0]._db.execute("SELECT count(*) FROM workflow_graphs").fetchone()[0] == 0
    assert (
        env[0]._db.execute("SELECT count(*) FROM workflow_graph_nodes").fetchone()[0]
        == 0
    )
    assert (
        env[0]._db.execute("SELECT count(*) FROM workflow_graph_budgets").fetchone()[0]
        == 0
    )


def test_graph_routes_enforce_authentication_tenant_and_policy(env):
    graph_id = create_graph(env)
    assert env[1]["b"].get(f"/v1/workflow-graphs/{graph_id}").status_code == 404
    assert (
        env[1]["a"]
        .get(f"/v1/workflow-graphs/{graph_id}", headers={"x-tenant-id": "b"})
        .status_code
        == 403
    )
    assert env[1]["operator"].get(f"/v1/workflow-graphs/{graph_id}").status_code == 403
    assert (
        env[1]["unconfigured"].post("/v1/workflow-graphs", json=GRAPH_BODY).status_code
        == 403
    )


@pytest.mark.parametrize(
    "nodes",
    [
        [
            {**GRAPH_BODY["nodes"][0], "depends_on": ["missing"]},
        ],
        [
            {**GRAPH_BODY["nodes"][0], "depends_on": ["second"]},
            {**GRAPH_BODY["nodes"][1], "depends_on": ["first"]},
        ],
        [GRAPH_BODY["nodes"][0], GRAPH_BODY["nodes"][0]],
    ],
)
def test_invalid_graph_topology_is_422_without_writes(env, nodes):
    response = env[1]["a"].post(
        "/v1/workflow-graphs", json={"idempotency_key": "bad", "nodes": nodes}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_workflow_graph"
    assert env[0]._db.execute("SELECT count(*) FROM workflow_graphs").fetchone()[0] == 0


def test_graph_result_requires_every_sink_to_be_accepted(env):
    graph_id = create_graph(env)
    executor = GraphNodeExecutor(
        env[0], InferenceRouter(registry(ControlledEngine("only")))
    )
    policy = env[3]["a"].acceptance.policy()
    assert env[1]["a"].get(f"/v1/workflow-graphs/{graph_id}/result").status_code == 409
    asyncio.run(executor.execute("a", graph_id, "first", "worker-1", policy))
    asyncio.run(executor.execute("a", graph_id, "second", "worker-2", policy))
    response = env[1]["a"].get(f"/v1/workflow-graphs/{graph_id}/result")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "succeeded"
    assert [item["node_id"] for item in body["results"]] == ["second"]
    assert body["results"][0]["validation"]["decision"] == "accepted"
    assert "synthetic first" not in response.text


def test_graph_cancel_fences_running_node_and_skips_descendant(env):
    graph_id = create_graph(env)
    fence = env[0].claim_graph_node("a", graph_id, "first", "worker")
    response = env[1]["a"].post(f"/v1/workflow-graphs/{graph_id}/cancel")
    assert response.status_code == 200
    assert response.json()["state"] == "completed_with_failures"
    assert response.json()["nodes"] == [
        {"node_id": "first", "state": "cancelled"},
        {"node_id": "second", "state": "skipped"},
    ]
    with pytest.raises(WorkflowConflict, match="Stale"):
        env[0].complete_graph_node(
            "a", graph_id, "first", "worker", fence, {}, succeeded=True
        )


def test_startup_recovery_fences_expired_graph_node_and_is_tenant_filtered(
    env, monkeypatch
):
    now = datetime(2026, 9, 26, tzinfo=UTC)
    graph_id = create_graph(env)
    env[0]._db.execute(
        "UPDATE workflow_graph_budgets SET deadline_at=? WHERE graph_id=?",
        ((now + timedelta(minutes=1)).isoformat(), graph_id),
    )
    env[0].claim_graph_node("a", graph_id, "first", "worker", lease_seconds=1, now=now)
    report = tuple(
        env[0].recover_graph_nodes_startup(limit=10, now=now + timedelta(seconds=2))
    )
    monkeypatch.setattr(main, "graph_recovery_report", report)
    state = env[0].get_graph_state("a", graph_id)
    assert state is not None
    assert state.state_of("first") is NodeState.UNCERTAIN
    assert state.state_of("second") is NodeState.BLOCKED
    response = env[1]["operator"].get("/v1/workflow-graphs/recovery")
    assert response.status_code == 200
    assert response.json() == {
        "scanned": 1,
        "unresolved": [
            {
                "graph_id": graph_id,
                "node_id": "first",
                "reason": "outcome_unknown",
            }
        ],
    }
    assert env[1]["a"].get("/v1/workflow-graphs/recovery").status_code == 403
