import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from backend.inference.contracts import ChatInput, ChatMessage, ChatRole
from backend.workflows.contracts import TaskPacket
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_workflow_store import packet


@pytest.mark.parametrize("chat", (False, True))
def test_packet_roundtrip_reuses_inference_contract_and_normalizes_deadline(chat):
    original = packet()
    task = replace(
        original.task,
        input=ChatInput((ChatMessage(ChatRole.USER, "synthetic"),))
        if chat
        else original.task.input,
        deadline_at=datetime(2026, 9, 15, 8, tzinfo=timezone(timedelta(hours=-4))),
        requirements=replace(
            original.task.requirements, required_model="model", production_only=True
        ),
    )
    original = TaskPacket(task)
    encoded = original.to_dict()
    assert encoded["task"]["deadline_at"] == "2026-09-15T12:00:00+00:00"
    restored = TaskPacket.from_dict(json.loads(json.dumps(encoded)))
    assert restored == original
    encoded["task"]["requirements"]["production_only"] = False
    assert restored.task.requirements.production_only is True


@pytest.mark.parametrize(
    "mutation", ("version", "extra", "flag", "token_bool", "role", "kind", "deadline")
)
def test_invalid_packets_fail_closed(mutation):
    value = packet().to_dict()
    if mutation == "version":
        value["schema_version"] = 999
    elif mutation == "extra":
        value["task"]["unrecognized"] = "value"
    elif mutation == "flag":
        value["task"]["requirements"]["production_only"] = "false"
    elif mutation == "token_bool":
        value["task"]["generation"]["max_output_tokens"] = True
    elif mutation == "role":
        value["task"]["input"] = {
            "kind": "chat",
            "messages": [{"role": "unknown", "content": "synthetic"}],
        }
    elif mutation == "kind":
        value["task"]["input"]["kind"] = "unknown"
    else:
        value["task"]["deadline_at"] = "2026-09-15T00:00:00"
    with pytest.raises(ValueError, match="Invalid workflow task packet"):
        TaskPacket.from_dict(value)


def test_artifact_survives_restart_and_is_scoped_and_immutable(tmp_path):
    path = tmp_path / "artifact.db"
    store = SQLiteWorkflowStore(path)
    task_packet = packet()
    workflow = store.create("a", "key", task_packet)
    fence = store.claim("a", workflow, "worker")
    artifact = store.complete(
        "a",
        workflow,
        "worker",
        fence,
        {"answer": "synthetic ✓", "attempts": []},
        succeeded=True,
    )
    store.close()
    store = SQLiteWorkflowStore(path)
    try:
        assert store.get_packet("a", workflow) == task_packet
        assert store.get_packet("b", workflow) is None
        saved = store.get_artifact("a", workflow, artifact.artifact_id)
        assert saved is not None
        assert saved.ref == artifact
        assert saved.payload()["answer"] == "synthetic ✓"
        saved.payload()["answer"] = "mutation"
        assert saved.payload()["answer"] == "synthetic ✓"
        assert store.get_artifact("b", workflow, artifact.artifact_id) is None
        other = store.create("a", "other", packet())
        assert store.get_artifact("a", other, artifact.artifact_id) is None
        record = store.get("a", workflow)
        assert record is not None
        assert record["result_artifact_id"] == artifact.artifact_id
        with pytest.raises(WorkflowConflict):
            store.complete("a", workflow, "worker", fence, {}, succeeded=True)
        with sqlite3.connect(path) as db:
            assert (
                db.execute("SELECT COUNT(*) FROM workflow_artifacts").fetchone()[0] == 1
            )
            db.execute("UPDATE workflow_artifacts SET content_json='{}'")
        with pytest.raises(ValueError, match="integrity"):
            store.get_artifact("a", workflow, artifact.artifact_id)
    finally:
        store.close()


def test_completion_event_failure_rolls_back_artifact_and_result(tmp_path, monkeypatch):
    path = tmp_path / "rollback.db"
    store = SQLiteWorkflowStore(path)
    try:
        workflow = store.create("a", "key", packet())
        fence = store.claim("a", workflow, "worker")

        def fail(*args):
            raise RuntimeError("injected")

        monkeypatch.setattr(store, "_event", fail)
        with pytest.raises(RuntimeError):
            store.complete("a", workflow, "worker", fence, {}, succeeded=True)
        row = store.get("a", workflow)
        assert row is not None
        assert row["state"] == "running"
        assert row["result"] is None
        assert row["result_artifact_id"] is None
        with sqlite3.connect(path) as db:
            assert (
                db.execute("SELECT COUNT(*) FROM workflow_artifacts").fetchone()[0] == 0
            )
    finally:
        store.close()


def make_v1_database(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE workflow_schema(version INTEGER NOT NULL)")
        db.execute("INSERT INTO workflow_schema VALUES (1)")
        db.execute("""CREATE TABLE workflows (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL, packet TEXT NOT NULL, state TEXT NOT NULL,
            fence INTEGER NOT NULL DEFAULT 0, owner TEXT, lease_until TEXT,
            result TEXT, UNIQUE(tenant, idempotency_key))""")
        db.execute(
            "INSERT INTO workflows VALUES "
            "('old', 'a', 'key', 'hash', '{}', 'ready', 0, NULL, NULL, NULL)"
        )


def test_v1_migration_preserves_legacy_packet_but_does_not_invent_a_task(tmp_path):
    path = tmp_path / "v1.db"
    make_v1_database(path)
    store = SQLiteWorkflowStore(path)
    try:
        row = store.get("a", "old")
        assert row is not None
        assert row["packet"] == {}
        assert row["result_artifact_id"] is None
        with pytest.raises(ValueError):
            store.get_packet("a", "old")
        with pytest.raises(ValueError):
            store.claim("a", "old", "worker")
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 8
        assert store.create("a", "new", packet())
    finally:
        store.close()


def test_cancelled_or_expired_task_cannot_publish_an_artifact(tmp_path):
    path = tmp_path / "stale.db"
    store = SQLiteWorkflowStore(path)
    now = datetime.now(UTC)
    try:
        workflow = store.create("a", "key", packet())
        fence = store.claim("a", workflow, "worker", lease_seconds=1, now=now)
        with pytest.raises(WorkflowConflict):
            store.complete(
                "a",
                workflow,
                "worker",
                fence,
                {},
                succeeded=True,
                now=now + timedelta(seconds=2),
            )
        store.cancel("a", workflow)
        with pytest.raises(WorkflowConflict):
            store.complete("a", workflow, "worker", fence, {}, succeeded=True, now=now)
        with sqlite3.connect(path) as db:
            assert (
                db.execute("SELECT COUNT(*) FROM workflow_artifacts").fetchone()[0] == 0
            )
    finally:
        store.close()


def test_migration_failure_rolls_back_column_and_version(tmp_path, monkeypatch):
    path = tmp_path / "migration-failure.db"
    make_v1_database(path)
    connect = sqlite3.connect

    def deny_artifact_table(action, name, *args):
        if action == sqlite3.SQLITE_CREATE_TABLE and name == "workflow_artifacts":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def guarded_connect(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connection.set_authorizer(deny_artifact_table)
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", guarded_connect)
        with pytest.raises(sqlite3.DatabaseError):
            SQLiteWorkflowStore(path)
    with connect(path) as db:
        assert db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 1
        assert "result_artifact_id" not in {
            row[1] for row in db.execute("PRAGMA table_info(workflows)")
        }
        assert (
            db.execute("SELECT packet FROM workflows WHERE id='old'").fetchone()[0]
            == "{}"
        )
    # After the underlying fault is removed, migration can be retried safely.
    store = SQLiteWorkflowStore(path)
    store.close()


def test_workflow_create_rejects_untyped_and_invalid_packets_without_writes(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "invalid.db")
    try:
        with pytest.raises(ValueError, match="TaskPacket"):
            store.create("a", "key", {})  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            TaskPacket(
                replace(
                    packet().task,
                    generation=replace(
                        packet().task.generation, max_output_tokens=True
                    ),
                )
            )
        with sqlite3.connect(tmp_path / "invalid.db") as db:
            assert db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0] == 0
    finally:
        store.close()


def test_completion_uses_time_after_acquiring_transaction(tmp_path, monkeypatch):
    from contextlib import contextmanager

    store = SQLiteWorkflowStore(tmp_path / "lease-wait.db")
    now = datetime(2026, 9, 15, tzinfo=UTC)
    workflow = store.create("a", "key", packet())
    fence = store.claim("a", workflow, "worker", lease_seconds=1, now=now)
    transaction = store._transaction
    clock = [now]

    @contextmanager
    def delayed_transaction():
        with transaction():
            # Simulate lock contention that lasts past the worker's lease.
            clock[0] = now + timedelta(seconds=2)
            yield

    monkeypatch.setattr(store, "_transaction", delayed_transaction)
    monkeypatch.setattr(store, "_now", lambda _: clock[0])
    try:
        with pytest.raises(WorkflowConflict):
            store.complete("a", workflow, "worker", fence, {}, succeeded=True)
        row = store.get("a", workflow)
        assert row is not None
        assert row["state"] == "running"
        assert row["result_artifact_id"] is None
    finally:
        store.close()
