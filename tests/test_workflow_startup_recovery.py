from datetime import UTC, datetime, timedelta

import pytest

import backend.main as main
from backend.config import AppEnvironment, Settings
from backend.workflows.recovery import (
    StartupRecoveryReport,
    recover_workflows_at_startup,
)
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_workflow_store import packet


def stage(store, key, *, tenant="a", outcome=None, succeeded=True, lease_seconds=1):
    now = datetime(2026, 9, 25, tzinfo=UTC)
    workflow = store.create(tenant, key, packet(key))
    fence = store.claim(
        tenant, workflow, "worker", now=now, lease_seconds=lease_seconds
    )
    store.begin_dispatch(
        tenant, workflow, "worker", fence, {"max_attempts": 1}, now=now
    )
    if outcome is not None:
        store.record_outcome(
            tenant,
            workflow,
            "worker",
            fence,
            outcome,
            succeeded=succeeded,
            now=now,
        )
    return workflow, now


def saved(store, workflow_id, tenant="a"):
    row = store.get(tenant, workflow_id)
    assert row is not None
    return row


def test_startup_recovery_reconciles_only_durable_outcomes_and_is_idempotent(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "startup.db")
    try:
        unknown, now = stage(store, "unknown")
        succeeded, _ = stage(store, "success", outcome={"answer": "saved"})
        failed, _ = stage(
            store,
            "failure",
            outcome={"failure_code": "generation_failure"},
            succeeded=False,
        )
        active, _ = stage(store, "active", lease_seconds=3600)
        report = recover_workflows_at_startup(
            store, limit=10, now=now + timedelta(seconds=2)
        )
        assert report.scanned == 3
        assert {item.workflow_id for item in report.expired} == {
            unknown,
            succeeded,
            failed,
        }
        assert {(item.workflow_id, item.state) for item in report.reconciled} == {
            (succeeded, "awaiting_validation"),
            (failed, "failed"),
        }
        assert [(item.workflow_id, item.reason) for item in report.unresolved] == [
            (unknown, "outcome_unknown")
        ]
        assert saved(store, unknown)["state"] == "uncertain"
        assert saved(store, succeeded)["state"] == "awaiting_validation"
        assert saved(store, failed)["state"] == "failed"
        assert saved(store, active)["state"] == "running"

        replay = recover_workflows_at_startup(
            store, limit=10, now=now + timedelta(seconds=2)
        )
        assert replay.scanned == 1
        assert replay.expired == ()
        assert replay.reconciled == ()
        assert replay.unresolved == report.unresolved
    finally:
        store.close()


def test_startup_recovery_reports_corrupt_evidence_without_accepting_it(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "corrupt.db")
    try:
        workflow, now = stage(store, "corrupt", outcome={"answer": "saved"})
        store._db.execute(
            "UPDATE workflow_dispatches SET outcome_sha256=? WHERE workflow_id=?",
            ("0" * 64, workflow),
        )
        report = recover_workflows_at_startup(
            store, limit=10, now=now + timedelta(seconds=2)
        )
        assert report.reconciled == ()
        assert [(item.workflow_id, item.reason) for item in report.unresolved] == [
            (workflow, "invalid_outcome_evidence")
        ]
        row = saved(store, workflow)
        assert row["state"] == "uncertain"
        assert row["result_artifact_id"] is None
    finally:
        store.close()


def test_startup_recovery_limit_rolls_back_before_state_changes(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "bounded.db")
    try:
        first, now = stage(store, "first")
        second, _ = stage(store, "second")
        before = {item: store.events("a", item) for item in (first, second)}
        with pytest.raises(WorkflowConflict, match="scan limit"):
            recover_workflows_at_startup(store, limit=1, now=now + timedelta(seconds=2))
        assert [saved(store, item)["state"] for item in (first, second)] == [
            "running",
            "running",
        ]
        assert {item: store.events("a", item) for item in (first, second)} == before
    finally:
        store.close()


@pytest.mark.asyncio
async def test_application_lifespan_runs_recovery_before_runtime_start(
    tmp_path, monkeypatch
):
    store = SQLiteWorkflowStore(tmp_path / "lifespan.db")
    workflow, now = stage(store, "startup")
    events = []

    class Runtime:
        async def start(self):
            assert main.workflow_recovery_report is not None
            events.append("runtime_started")

        async def stop(self):
            events.append("runtime_stopped")

    class Registry:
        async def aclose(self):
            events.append("registry_closed")

    class Control:
        def close(self):
            events.append("control_closed")

    monkeypatch.setattr(
        main,
        "settings",
        Settings(
            app_env=AppEnvironment.TEST,
            workflow_recovery_scan_limit=10,
        ),
    )
    monkeypatch.setattr(main, "workflow_store", store)
    monkeypatch.setattr(main, "workflow_recovery_report", None)
    monkeypatch.setattr(main, "runtime_collector", Runtime())
    monkeypatch.setattr(main, "deployment_registry", Registry())
    monkeypatch.setattr(main, "api_control", Control())
    async with main.lifespan(main.app):
        report = main.workflow_recovery_report
        assert report is not None
        assert [(item.workflow_id, item.reason) for item in report.unresolved] == [
            (workflow, "outcome_unknown")
        ]
        assert saved(store, workflow)["state"] == "uncertain"
    assert events == [
        "runtime_started",
        "runtime_stopped",
        "registry_closed",
        "control_closed",
    ]


@pytest.mark.asyncio
async def test_failed_startup_clears_stale_report_and_closes_resources(
    tmp_path, monkeypatch
):
    store = SQLiteWorkflowStore(tmp_path / "failed-startup.db")
    stage(store, "first")
    stage(store, "second")
    events = []

    class Runtime:
        async def start(self):
            events.append("unexpected_runtime_start")

        async def stop(self):
            events.append("unexpected_runtime_stop")

    class Registry:
        async def aclose(self):
            events.append("registry_closed")

    class Control:
        def close(self):
            events.append("control_closed")

    monkeypatch.setattr(
        main,
        "settings",
        Settings(
            app_env=AppEnvironment.TEST,
            workflow_recovery_scan_limit=1,
        ),
    )
    monkeypatch.setattr(main, "workflow_store", store)
    monkeypatch.setattr(
        main,
        "workflow_recovery_report",
        StartupRecoveryReport(0, (), (), ()),
    )
    monkeypatch.setattr(main, "runtime_collector", Runtime())
    monkeypatch.setattr(main, "deployment_registry", Registry())
    monkeypatch.setattr(main, "api_control", Control())
    with pytest.raises(WorkflowConflict, match="scan limit"):
        async with main.lifespan(main.app):
            raise AssertionError("startup unexpectedly succeeded")
    assert main.workflow_recovery_report is None
    assert events == ["registry_closed", "control_closed"]
