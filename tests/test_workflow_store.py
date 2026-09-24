from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from backend.inference.contracts import (
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.workflows.contracts import TaskPacket
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict


def packet(text="synthetic"):
    return TaskPacket(
        InferenceTask(
            TextInput(text),
            GenerationConfig(),
            TaskRequirements(),
            TraceContext("test"),
        )
    )


@pytest.fixture
def store(tmp_path):
    value = SQLiteWorkflowStore(tmp_path / "workflows.db")
    yield value
    value.close()


def test_idempotency_and_tenant_isolation(store):
    workflow = store.create("a", "key", packet())
    assert store.create("a", "key", packet()) == workflow
    with pytest.raises(WorkflowConflict):
        store.create("a", "key", packet("different"))
    assert store.create("b", "key", packet()) != workflow
    assert store.get("b", workflow) is None
    assert store.events("b", workflow) == []
    assert not store.cancel("b", workflow)
    with pytest.raises(WorkflowConflict):
        store.claim("b", workflow, "worker")
    assert len(store.events("a", workflow)) == 1


def test_two_connections_cannot_claim_same_task(tmp_path):
    path = tmp_path / "concurrent.db"
    first, second = SQLiteWorkflowStore(path), SQLiteWorkflowStore(path)
    try:
        workflow = first.create("a", "key", packet())

        def claim(store):
            try:
                return store.claim("a", workflow, "worker")
            except WorkflowConflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(claim, (first, second)))
        assert sorted(value for value in outcomes if value is not None) == [1]
        assert [event["state"] for event in first.events("a", workflow)] == [
            "ready",
            "running",
        ]
    finally:
        first.close()
        second.close()


def test_restart_expired_execution_is_uncertain_and_late_result_rejected(tmp_path):
    path = tmp_path / "recovery.db"
    now = datetime(2026, 9, 15, tzinfo=UTC)
    first = SQLiteWorkflowStore(path)
    workflow = first.create("a", "key", packet())
    fence = first.claim("a", workflow, "worker", lease_seconds=1, now=now)
    first.close()
    recovered = SQLiteWorkflowStore(path)
    try:
        assert recovered.recover_expired("b", now=now + timedelta(seconds=2)) == 0
        assert recovered.recover_expired("a", now=now + timedelta(seconds=2)) == 1
        assert recovered.recover_expired("a", now=now + timedelta(seconds=2)) == 0
        row = recovered.get("a", workflow)
        assert row is not None
        assert row["state"] == "uncertain"
        with pytest.raises(WorkflowConflict):
            recovered.complete(
                "a",
                workflow,
                "worker",
                fence,
                {},
                succeeded=True,
                now=now + timedelta(seconds=2),
            )
        with pytest.raises(WorkflowConflict):
            recovered.claim("a", workflow, "another")
    finally:
        recovered.close()


@pytest.mark.parametrize("wrong", ("tenant", "owner", "fence", "expired"))
def test_invalid_completions_do_not_change_state(store, wrong):
    now = datetime(2026, 9, 15, tzinfo=UTC)
    workflow = store.create("a", "key", packet())
    fence = store.claim("a", workflow, "worker", now=now)
    with pytest.raises(WorkflowConflict):
        store.complete(
            "b" if wrong == "tenant" else "a",
            workflow,
            "wrong" if wrong == "owner" else "worker",
            fence + 1 if wrong == "fence" else fence,
            {},
            succeeded=True,
            now=now + timedelta(seconds=31) if wrong == "expired" else now,
        )
    assert store.get("a", workflow)["state"] == "running"
    assert len(store.events("a", workflow)) == 2


def test_terminal_completion_and_cancellation_are_fenced(store):
    workflow = store.create("a", "key", packet())
    fence = store.claim("a", workflow, "worker")
    store.complete(
        "a", workflow, "worker", fence, {"answer": "synthetic"}, succeeded=True
    )
    with pytest.raises(WorkflowConflict):
        store.complete("a", workflow, "worker", fence, {}, succeeded=True)
    assert store.cancel("a", workflow)
    cancelled = store.create("a", "other", packet())
    fence = store.claim("a", cancelled, "worker")
    assert store.cancel("a", cancelled)
    assert store.cancel("a", cancelled)
    with pytest.raises(WorkflowConflict):
        store.complete("a", cancelled, "worker", fence, {}, succeeded=True)
    assert len(store.events("a", cancelled)) == 3


def test_event_failure_rolls_back_state(store, monkeypatch):
    workflow = store.create("a", "key", packet())

    def fail(*args):
        raise RuntimeError("injected event failure")

    monkeypatch.setattr(store, "_event", fail)
    with pytest.raises(RuntimeError):
        store.claim("a", workflow, "worker")
    assert store.get("a", workflow)["state"] == "ready"
    assert store.get("a", workflow)["fence"] == 0


def test_rejects_future_schema_without_modifying_it(tmp_path):
    import sqlite3

    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE workflow_schema(version INTEGER NOT NULL)")
        connection.execute("INSERT INTO workflow_schema VALUES(999)")
    with pytest.raises(ValueError, match="Unsupported"):
        SQLiteWorkflowStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version FROM workflow_schema").fetchone() == (
            999,
        )
