"""Offline crash-boundary and reconciliation contracts; no provider calls."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from backend.audit.deterministic import ValidationPolicy
from backend.inference.router import InferenceRouter
from backend.workflows.budget import WorkflowBudget
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_execution import ControlledEngine, registry
from tests.test_workflow_store import packet


class SimulatedCrash(BaseException):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary,calls,reconciled",
    [
        ("begin_dispatch", 0, "uncertain"),
        ("router", 0, "uncertain"),
        ("record_outcome", 1, "uncertain"),
        ("complete", 1, "awaiting_validation"),
        (None, 1, "awaiting_validation"),
    ],
)
async def test_restart_at_dispatch_boundaries(
    tmp_path, monkeypatch, boundary, calls, reconciled
):
    path = tmp_path / "crash.db"
    store = SQLiteWorkflowStore(path)
    workflow = store.create("a", "task", packet())
    engine = ControlledEngine("only")
    router = InferenceRouter(registry(engine))

    def crash(*args, **kwargs):
        raise SimulatedCrash()

    with monkeypatch.context() as patch:
        if boundary == "router":
            patch.setattr(router, "generate_task", crash)
        elif boundary:
            patch.setattr(store, boundary, crash)
        executor = WorkflowExecutor(store, router)
        if boundary:
            with pytest.raises(SimulatedCrash):
                await executor.execute("a", workflow, "worker", WorkflowBudget(10, 1))
        else:
            await executor.execute("a", workflow, "worker", WorkflowBudget(10, 1))
    assert engine.calls == calls
    before = store.get("a", workflow)
    assert before is not None
    store.close()
    store = SQLiteWorkflowStore(path)
    try:
        future = datetime.now(UTC) + timedelta(hours=1)
        assert store.recover_expired("b", now=future) == 0
        assert store.recover_expired("a", now=future) == int(boundary is not None)
        assert store.recover_expired("a", now=future) == 0
        assert store.reconcile_uncertain("a", workflow) == reconciled
        events = store.events("a", workflow)
        assert store.reconcile_uncertain("a", workflow) == reconciled
        assert store.events("a", workflow) == events
        with pytest.raises(WorkflowConflict):
            await WorkflowExecutor(store, router).execute(
                "a", workflow, "new", WorkflowBudget(10, 1)
            )
        with pytest.raises(WorkflowConflict):
            store.reconcile_uncertain("b", workflow)
        if reconciled == "awaiting_validation":
            saved = store.get("a", workflow)
            assert saved is not None
            assert saved["result"]["budget"]["attempts"] == 1
            assert saved["result"]["provenance"]["deployment_id"] == "only-deployment"
            if boundary is None:
                assert saved["result_artifact_id"] == before["result_artifact_id"]
            report = store.validate("a", workflow, ValidationPolicy())
            assert report["decision"] == "accepted"
            assert store.reconcile_uncertain("a", workflow) == "succeeded"
            assert store.validate("a", workflow, ValidationPolicy()) == report
        assert engine.calls == calls
    finally:
        store.close()


def staged(store, *, succeeded=True):
    now = datetime(2026, 9, 24, tzinfo=UTC)
    workflow = store.create("a", "task", packet())
    fence = store.claim("a", workflow, "worker", now=now, lease_seconds=1)
    store.begin_dispatch("a", workflow, "worker", fence, {"max_attempts": 1}, now=now)
    result: dict[str, Any] = (
        {"output": {"text": "synthetic"}}
        if succeeded
        else {"failure_code": "generation_failure"}
    )
    store.record_outcome(
        "a", workflow, "worker", fence, result, succeeded=succeeded, now=now
    )
    return workflow, fence, now, result


@pytest.mark.parametrize("succeeded", [True, False])
def test_concurrent_recovery_commits_one_artifact(tmp_path, succeeded):
    path = tmp_path / "race.db"
    first, second = SQLiteWorkflowStore(path), SQLiteWorkflowStore(path)
    try:
        workflow, fence, now, result = staged(first, succeeded=succeeded)

        def recover(store):
            store.recover_expired("a", now=now + timedelta(seconds=1))
            return store.reconcile_uncertain("a", workflow)

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(recover, (first, second)))
        state = "awaiting_validation" if succeeded else "failed"
        assert outcomes == [state, state]
        assert [e["state"] for e in first.events("a", workflow)] == [
            "ready",
            "running",
            "dispatch_started",
            "outcome_recorded",
            "uncertain",
            state,
        ]
        saved = first.get("a", workflow)
        assert saved is not None
        assert saved["result"] == result
        with sqlite3.connect(path) as db:
            assert (
                db.execute("SELECT count(*) FROM workflow_artifacts").fetchone()[0] == 1
            )
        for store in (first, second):
            with pytest.raises(WorkflowConflict):
                store.complete(
                    "a", workflow, "worker", fence, result, succeeded=succeeded, now=now
                )
    finally:
        first.close()
        second.close()


def test_journal_replay_fencing_and_cancellation(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "fence.db")
    try:
        workflow, fence, now, result = staged(store)
        events = store.events("a", workflow)
        store.record_outcome(
            "a", workflow, "worker", fence, result, succeeded=True, now=now
        )
        assert store.events("a", workflow) == events
        with pytest.raises(WorkflowConflict):
            store.begin_dispatch("a", workflow, "worker", fence, {}, now=now)
        for tenant, owner, token, at, payload in [
            ("b", "worker", fence, now, result),
            ("a", "other", fence, now, result),
            ("a", "worker", fence + 1, now, result),
            ("a", "worker", fence, now + timedelta(seconds=1), result),
            ("a", "worker", fence, now, {"different": True}),
        ]:
            with pytest.raises(WorkflowConflict):
                store.record_outcome(
                    tenant, workflow, owner, token, payload, succeeded=True, now=at
                )
        with pytest.raises(WorkflowConflict):
            store.complete("a", workflow, "worker", fence, {}, succeeded=True, now=now)
        assert store.cancel("a", workflow)
        assert store.recover_expired("a", now=now + timedelta(seconds=2)) == 0
        assert store.reconcile_uncertain("a", workflow) == "cancelled"
        saved = store.get("a", workflow)
        assert saved is not None
        assert saved["result_artifact_id"] is None
    finally:
        store.close()


@pytest.mark.parametrize("phase", ["record", "recover", "reconcile"])
def test_recovery_transaction_failure_is_retryable(tmp_path, monkeypatch, phase):
    store = SQLiteWorkflowStore(tmp_path / "rollback.db")
    try:
        workflow, fence, now, result = staged(store)
        future = now + timedelta(seconds=2)
        if phase == "record":
            # Remove the fixture outcome to exercise the first durable write.
            store._db.execute(
                "UPDATE workflow_dispatches SET outcome_json=NULL, "
                "outcome_sha256=NULL, succeeded=NULL"
            )

            def action() -> object:
                store.record_outcome(
                    "a", workflow, "worker", fence, result, succeeded=True, now=now
                )
                return None
        elif phase == "recover":

            def action() -> object:
                return store.recover_expired("a", now=future)
        else:
            store.recover_expired("a", now=future)

            def action() -> object:
                return store.reconcile_uncertain("a", workflow)

        before = store.get("a", workflow)
        events = store.events("a", workflow)

        def fail(*args):
            raise RuntimeError("injected")

        with monkeypatch.context() as patch:
            patch.setattr(store, "_event", fail)
            with pytest.raises(RuntimeError):
                action()
        assert store.get("a", workflow) == before
        assert store.events("a", workflow) == events
        assert (
            store._db.execute("SELECT count(*) FROM workflow_artifacts").fetchone()[0]
            == 0
        )
        if phase == "record":
            assert (
                store._db.execute(
                    "SELECT outcome_json FROM workflow_dispatches"
                ).fetchone()[0]
                is None
            )
        action()
    finally:
        store.close()


def test_corrupt_outcome_cannot_be_reconciled(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "corrupt.db")
    try:
        workflow, _, now, _ = staged(store)
        store.recover_expired("a", now=now + timedelta(seconds=2))
        store._db.execute("UPDATE workflow_dispatches SET outcome_json='{}'")
        with pytest.raises(WorkflowConflict, match="evidence"):
            store.reconcile_uncertain("a", workflow)
        saved = store.get("a", workflow)
        assert saved is not None
        assert saved["state"] == "uncertain"
        saved = store.get("a", workflow)
        assert saved is not None
        assert saved["result_artifact_id"] is None
    finally:
        store.close()


def test_abrupt_process_exit_preserves_recorded_outcome(tmp_path):
    import subprocess
    import sys

    path = tmp_path / "process.db"
    program = """
import os
import sys
from pathlib import Path
from backend.workflows.store import SQLiteWorkflowStore
from tests.test_workflow_recovery import staged
store = SQLiteWorkflowStore(Path(sys.argv[1]))
staged(store)
os._exit(17)
"""
    result = subprocess.run([sys.executable, "-c", program, str(path)], timeout=15)
    assert result.returncode == 17
    store = SQLiteWorkflowStore(path)
    try:
        workflow = store.create("a", "task", packet())
        assert store.recover_expired("a", now=datetime(2026, 9, 25, tzinfo=UTC)) == 1
        assert store.reconcile_uncertain("a", workflow) == "awaiting_validation"
        assert (
            store.validate("a", workflow, ValidationPolicy())["decision"] == "accepted"
        )
    finally:
        store.close()


def test_v3_migration_and_rollback_preserve_existing_work(tmp_path, monkeypatch):
    from contextlib import contextmanager

    path = tmp_path / "migration.db"
    store = SQLiteWorkflowStore(path)
    workflow = store.create("a", "legacy", packet())
    now = datetime(2026, 9, 24, tzinfo=UTC)
    store.claim("a", workflow, "legacy-worker", now=now)
    before = store.get("a", workflow)
    events = store.events("a", workflow)
    store.close()
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE workflow_dispatches")
        db.execute("UPDATE workflow_schema SET version=3")
    transaction = SQLiteWorkflowStore._transaction

    @contextmanager
    def fail_migration(self):
        with transaction(self):
            yield
            raise RuntimeError("injected migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteWorkflowStore, "_transaction", fail_migration)
        with pytest.raises(RuntimeError):
            SQLiteWorkflowStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 3
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='workflow_dispatches'"
        ).fetchall()
    store = SQLiteWorkflowStore(path)
    try:
        assert store.get("a", workflow) == before
        assert store.events("a", workflow) == events
        assert store.recover_expired("a", now=now + timedelta(minutes=1)) == 1
        assert store.reconcile_uncertain("a", workflow) == "uncertain"
        with pytest.raises(WorkflowConflict):
            store.claim("a", workflow, "new-worker")
    finally:
        store.close()
