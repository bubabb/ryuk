"""Governed workflow routes using synthetic inputs and in-process ASGI only."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

import backend.main as main
from backend.audit.deterministic import ValidationPolicy
from backend.config import Settings
from backend.control.admission import AdmissionController, QuotaPolicy
from backend.control.api import APIControlPlane
from backend.control.records import SQLiteExecutionRecordStore
from backend.control.security import Principal, Role, issue_api_key
from backend.inference.router import InferenceRouter
from backend.workflows.budget import WorkflowBudget
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.governance import WorkflowPolicy, load_workflow_policies
from backend.workflows.recovery import (
    ExpiredWorkflow,
    ReconciledWorkflow,
    StartupRecoveryReport,
    UnresolvedWorkflow,
)
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_api import ASGITestClient
from tests.test_execution import ControlledEngine, registry
from tests.test_workflow_store import packet

BODY = {
    "idempotency_key": "synthetic-1",
    "prompt": "synthetic prompt",
    "model": "test",
    "max_tokens": 32,
}
POLICY = {
    "version": "synthetic-v1",
    "acceptance": {"minimum_chars": 1, "forbidden_phrases": ["forbidden"]},
    "budget": {"deadline_seconds": 10.0, "max_attempts": 2, "max_output_tokens": 64},
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    store = SQLiteWorkflowStore(tmp_path / "workflows.db")
    records = SQLiteExecutionRecordStore(tmp_path / "records.db")
    keys, clients = {}, {}
    for label, tenant, role in [
        ("a", "a", Role.INFERENCE),
        ("b", "b", Role.INFERENCE),
        ("operator", "a", Role.OPERATOR),
        ("admin", "a", Role.ADMIN),
        ("unconfigured", "c", Role.INFERENCE),
    ]:
        key, record = issue_api_key(Principal(label, tenant, frozenset({role})))
        keys[record.key_id] = record
        client = ASGITestClient()
        client.headers["Authorization"] = f"Bearer {key}"
        clients[label] = client
    control = APIControlPlane(
        keys,
        AdmissionController(
            {tenant: QuotaPolicy(1000, 10, 1000000) for tenant in ("a", "b", "c")}
        ),
        records,
    )
    policies = {tenant: WorkflowPolicy.model_validate(POLICY) for tenant in ("a", "b")}
    monkeypatch.setattr(main, "workflow_store", store)
    monkeypatch.setattr(main, "workflow_policies", policies)
    monkeypatch.setattr(main, "api_control", control)
    yield store, clients, control, policies
    store.close()
    records.close()


def created(env, who="a"):
    response = env[1][who].post("/v1/workflows", json=BODY)
    assert response.status_code == 202, response.text
    return response.json()["workflow_id"]


def requests_for(workflow):
    return [
        ("POST", "/v1/workflows", {"json": BODY}),
        ("GET", f"/v1/workflows/{workflow}", {}),
        ("POST", f"/v1/workflows/{workflow}/cancel", {}),
        ("GET", f"/v1/workflows/{workflow}/result", {}),
    ]


@pytest.mark.parametrize(
    "credentials,expected", [(None, 401), ("broken", 401), ("operator", 403)]
)
def test_every_route_requires_authentication_and_role(env, credentials, expected):
    workflow = created(env)
    client = env[1][credentials] if credentials == "operator" else ASGITestClient()
    if credentials == "broken":
        client.headers["Authorization"] = "Bearer invalid"
    for method, path, kwargs in requests_for(workflow):
        assert client.request(method, path, **kwargs).status_code == expected
    assert env[0].get("a", workflow)["state"] == "ready"


def test_operator_can_inspect_only_own_startup_recovery_report(env, monkeypatch):
    monkeypatch.setattr(
        main,
        "workflow_recovery_report",
        StartupRecoveryReport(
            scanned=4,
            expired=(ExpiredWorkflow("a", "expired-a"),),
            reconciled=(
                ReconciledWorkflow("a", "saved-a", "awaiting_validation"),
                ReconciledWorkflow("b", "saved-b", "failed"),
            ),
            unresolved=(UnresolvedWorkflow("a", "unknown-a", "outcome_unknown"),),
        ),
    )
    assert env[1]["a"].get("/v1/workflows/recovery").status_code == 403
    response = env[1]["operator"].get("/v1/workflows/recovery")
    assert response.status_code == 200
    assert response.json() == {
        "scanned": 3,
        "expired": 1,
        "reconciled": [{"workflow_id": "saved-a", "state": "awaiting_validation"}],
        "unresolved": [{"workflow_id": "unknown-a", "reason": "outcome_unknown"}],
    }
    assert "saved-b" not in response.text


def test_recovery_status_fails_closed_without_startup_report(env, monkeypatch):
    monkeypatch.setattr(main, "workflow_recovery_report", None)
    response = env[1]["operator"].get("/v1/workflows/recovery")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "workflow_recovery_unavailable"


def test_revoked_and_expired_keys_fail_closed(env):
    workflow = created(env)
    control = env[2]
    for field in ("revoked_at", "expires_at"):
        for key, record in list(control.api_keys.items()):
            control.api_keys[key] = replace(
                record, **{field: datetime.now(UTC) - timedelta(days=1)}
            )
        for method, path, kwargs in requests_for(workflow):
            assert env[1]["a"].request(method, path, **kwargs).status_code == 401


def test_tenant_isolation_and_no_client_authority(env):
    workflow = created(env)
    other = created(env, "b")
    assert workflow != other
    for method, path, kwargs in requests_for(workflow)[1:]:
        response = env[1]["b"].request(method, path, **kwargs)
        assert response.status_code == 404
        assert workflow not in response.text
    for method, path, kwargs in requests_for(workflow):
        response = env[1]["a"].request(
            method, path, headers={"x-tenant-id": "b"}, **kwargs
        )
        assert response.status_code == 403
    for field in ("tenant_id", "policy", "budget", "state", "trace", "owner"):
        assert (
            env[1]["a"]
            .post("/v1/workflows", json={**BODY, field: "override"})
            .status_code
            == 422
        )
    assert env[1]["admin"].get(f"/v1/workflows/{workflow}").status_code == 200


def test_creation_binds_detached_policy_and_stable_replay(env, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("creation must not dispatch")

    monkeypatch.setattr(main.inference_router, "generate_task", forbidden)
    workflow = created(env)
    assert created(env) == workflow
    row = env[0].get("a", workflow)
    assert row is not None
    assert row["state"] == "ready"
    assert len(env[0].events("a", workflow)) == 1
    bound = env[0].get_binding("a", workflow)
    assert bound == env[3]["a"].binding()
    assert (
        env[1]["a"]
        .post("/v1/workflows", json={**BODY, "prompt": "changed"})
        .status_code
        == 409
    )
    env[3]["a"].acceptance.forbidden_phrases.append("changed")
    assert env[0].get_binding("a", workflow) == bound
    assert env[1]["a"].post("/v1/workflows", json=BODY).status_code == 409
    response = env[1]["a"].get(f"/v1/workflows/{workflow}")
    assert set(response.json()) == {
        "workflow_id",
        "state",
        "policy_version",
        "result_available",
    }
    assert "synthetic prompt" not in response.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_tokens", 65),
        ("max_tokens", True),
        ("prompt", " "),
        ("idempotency_key", " key "),
        ("temperature", 3),
    ],
)
def test_invalid_input_cannot_create_work(env, field, value):
    assert (
        env[1]["a"].post("/v1/workflows", json={**BODY, field: value}).status_code
        == 422
    )
    assert env[0]._db.execute("SELECT count(*) FROM workflows").fetchone()[0] == 0


def test_disabled_and_unconfigured_tenants(env, monkeypatch):
    assert env[1]["unconfigured"].post("/v1/workflows", json=BODY).status_code == 403
    monkeypatch.setattr(main, "workflow_store", None)
    for method, path, kwargs in requests_for("unknown"):
        assert env[1]["a"].request(method, path, **kwargs).status_code == 503


def test_cancel_and_result_states(env):
    workflow = created(env)
    url = f"/v1/workflows/{workflow}"
    assert env[1]["a"].get(url + "/result").status_code == 409
    assert env[1]["a"].post(url + "/cancel").json()["state"] == "cancelled"
    assert env[1]["a"].post(url + "/cancel").status_code == 200
    assert env[1]["a"].get(url + "/result").status_code == 409
    with pytest.raises(WorkflowConflict):
        env[0].claim("a", workflow, "worker")
    legacy = env[0].create("a", "legacy", packet())
    assert env[1]["a"].get(f"/v1/workflows/{legacy}").status_code == 404


@pytest.mark.parametrize("state", ["failed", "rejected", "uncertain"])
def test_nonaccepted_results_are_not_exposed(env, state):
    workflow = created(env)
    store = env[0]
    fence = store.claim("a", workflow, "worker")
    if state == "uncertain":
        store.recover_expired("a", now=datetime.now(UTC) + timedelta(hours=1))
    else:
        store.complete(
            "a",
            workflow,
            "worker",
            fence,
            {"output": {"text": "forbidden"}},
            succeeded=state != "failed",
        )
        if state == "rejected":
            store.validate("a", workflow)
    assert env[1]["a"].get(f"/v1/workflows/{workflow}/result").status_code == 409
    assert env[1]["a"].post(f"/v1/workflows/{workflow}/cancel").status_code == 409


def test_bound_executor_and_validation_survive_restart(env, tmp_path):
    import asyncio

    store, clients, _, policies = env
    workflow = created(env)
    engine = ControlledEngine("only")
    executor = WorkflowExecutor(store, InferenceRouter(registry(engine)))
    with pytest.raises(WorkflowConflict, match="overridden"):
        asyncio.run(executor.execute("a", workflow, "worker", WorkflowBudget(99, 9)))
    asyncio.run(executor.execute("a", workflow, "worker"))
    assert clients["a"].get(f"/v1/workflows/{workflow}/result").status_code == 409
    with pytest.raises(WorkflowConflict, match="bound policy"):
        store.validate("a", workflow, ValidationPolicy())
    reopened = SQLiteWorkflowStore(tmp_path / "workflows.db")
    try:
        report = reopened.validate("a", workflow)
        assert report["decision"] == "accepted"
        policies.clear()
        response = clients["a"].get(f"/v1/workflows/{workflow}/result")
        assert response.status_code == 200
        assert response.json()["validation"] == report
        assert clients["a"].post(f"/v1/workflows/{workflow}/cancel").status_code == 409
        with pytest.raises(WorkflowConflict):
            asyncio.run(executor.execute("a", workflow, "worker"))
        assert engine.calls == 1
    finally:
        reopened.close()


def test_quota_rejection_precedes_store_and_permits_release(env, monkeypatch):
    workflow = created(env)
    control = env[2]
    control.admission = AdmissionController({"a": QuotaPolicy(100, 1, 100000)})
    held = control.admit(Principal("p", "a", frozenset({Role.INFERENCE})), 0)
    for method, path, kwargs in requests_for(workflow):
        assert env[1]["a"].request(method, path, **kwargs).status_code == 429
    held.release()
    assert env[0].get("a", workflow)["state"] == "ready"
    assert env[1]["a"].get(f"/v1/workflows/{workflow}/result").status_code == 409
    assert env[1]["a"].get(f"/v1/workflows/{workflow}").status_code == 200

    def fail(*args):
        raise RuntimeError("synthetic write failure")

    with monkeypatch.context() as patch:
        patch.setattr(env[0], "_event", fail)
        with pytest.raises(RuntimeError):
            env[1]["a"].post(f"/v1/workflows/{workflow}/cancel")
    assert env[1]["a"].get(f"/v1/workflows/{workflow}").status_code == 200


def test_config_requires_both_paths_and_rejects_production(tmp_path):
    for options in (
        {"workflow_store_path": tmp_path / "w.db"},
        {"workflow_policy_config_path": tmp_path / "p.json"},
        {
            "workflow_store_path": tmp_path / "w.db",
            "workflow_policy_config_path": tmp_path / "p.json",
            "app_env": "production",
            "mock_enabled": False,
        },
    ):
        with pytest.raises(ValueError):
            Settings(_env_file=None, **options)  # type: ignore[call-arg]
    import json

    path = tmp_path / "policies.json"
    path.write_text(json.dumps({"a": POLICY}))
    assert load_workflow_policies(path)["a"].version == "synthetic-v1"
    path.write_text(json.dumps({"a": {**POLICY, "unknown": True}}))
    with pytest.raises(ValueError):
        load_workflow_policies(path)


def test_binding_creation_and_event_rollback(env, monkeypatch):
    def fail(*args):
        import sqlite3

        raise sqlite3.OperationalError("synthetic sensitive detail")

    with monkeypatch.context() as patch:
        patch.setattr(env[0], "_event", fail)
        response = env[1]["a"].post("/v1/workflows", json=BODY)
    assert response.status_code == 503
    assert "sensitive" not in response.text
    for table in ("workflows", "workflow_bindings", "workflow_events"):
        assert env[0]._db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    created(env)


def test_lost_terminal_record_ack_can_be_replayed_without_duplicate(env, monkeypatch):
    records = env[2].records
    original = records.put

    def lost_ack(record):
        original(record)
        raise RuntimeError("lost acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(records, "put", lost_ack)
        assert env[1]["a"].post("/v1/workflows", json=BODY).status_code == 503
    workflow = created(env)
    assert env[0]._db.execute("SELECT count(*) FROM workflows").fetchone()[0] == 1
    assert len(env[0].events("a", workflow)) == 1


def test_concurrent_create_and_cancel_validation_race(env, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: created(env), range(2)))
    assert ids[0] == ids[1]
    workflow = ids[0]
    store = env[0]
    fence = store.claim("a", workflow, "worker")
    store.complete(
        "a",
        workflow,
        "worker",
        fence,
        {"output": {"text": "synthetic"}},
        succeeded=True,
    )
    other = SQLiteWorkflowStore(tmp_path / "workflows.db")
    try:

        def validate():
            try:
                return other.validate("a", workflow)["decision"]
            except WorkflowConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            acceptance = pool.submit(validate)
            cancelled = pool.submit(
                env[1]["a"].post, f"/v1/workflows/{workflow}/cancel"
            )
            decision, response = acceptance.result(), cancelled.result()
        row = store.get("a", workflow)
        assert row is not None
        if row["state"] == "succeeded":
            assert decision == "accepted"
            assert response.status_code == 409
        else:
            assert row["state"] == "cancelled"
            assert decision == "conflict"
            assert response.status_code == 200
            assert row["validation"] is None
    finally:
        other.close()


def test_result_corruption_and_policy_mismatch_fail_closed(env):
    store = env[0]
    workflow = created(env)
    fence = store.claim("a", workflow, "worker")
    ref = store.complete(
        "a",
        workflow,
        "worker",
        fence,
        {"output": {"text": "synthetic"}},
        succeeded=True,
    )
    store.validate("a", workflow)
    store._db.execute(
        "UPDATE workflow_artifacts SET content_json='{}' WHERE id=?", (ref.artifact_id,)
    )
    response = env[1]["a"].get(f"/v1/workflows/{workflow}/result")
    assert response.status_code == 503
    assert "synthetic" not in response.text


def test_terminal_records_exclude_packet_and_policy_content(env):
    import json

    workflow = created(env)
    env[1]["a"].get(f"/v1/workflows/{workflow}")
    env[1]["a"].get(f"/v1/workflows/{workflow}/result")
    env[1]["a"].post(f"/v1/workflows/{workflow}/cancel")
    # Inspect the existing record API rather than exposing workflow packets.
    rows = (
        env[2].records._connection.execute("SELECT * FROM execution_records").fetchall()
    )
    serialized = json.dumps(rows, default=str)
    assert "synthetic prompt" not in serialized
    assert "forbidden" not in serialized
    for operation in ("create", "status", "result", "cancel"):
        assert f"workflow.{operation}" in serialized


def test_v4_migration_preserves_legacy_and_rolls_back_binding_table(
    tmp_path, monkeypatch
):
    import sqlite3
    from contextlib import contextmanager

    path = tmp_path / "migration.db"
    store = SQLiteWorkflowStore(path)
    workflow = store.create("a", "legacy", packet())
    before = store.get("a", workflow)
    store.close()
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE workflow_bindings")
        db.execute("UPDATE workflow_schema SET version=4")
    original = SQLiteWorkflowStore._transaction

    @contextmanager
    def fail(self):
        with original(self):
            yield
            raise RuntimeError("migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteWorkflowStore, "_transaction", fail)
        with pytest.raises(RuntimeError):
            SQLiteWorkflowStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 4
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='workflow_bindings'"
        ).fetchall()
    store = SQLiteWorkflowStore(path)
    try:
        assert store.get("a", workflow) == before
        assert store.get_binding("a", workflow) is None
        assert (
            store._db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 5
        )
    finally:
        store.close()


@pytest.mark.parametrize("phase", ["running", "awaiting_validation"])
def test_api_cancel_fences_inflight_and_unaccepted_work(env, phase):
    store = env[0]
    workflow = created(env)
    fence = store.claim("a", workflow, "worker")
    if phase == "awaiting_validation":
        store.complete(
            "a",
            workflow,
            "worker",
            fence,
            {"output": {"text": "synthetic"}},
            succeeded=True,
        )
    response = env[1]["a"].post(f"/v1/workflows/{workflow}/cancel")
    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"
    with pytest.raises(WorkflowConflict):
        store.complete("a", workflow, "worker", fence, {}, succeeded=True)
    with pytest.raises(WorkflowConflict):
        store.validate("a", workflow)
    assert env[1]["a"].get(f"/v1/workflows/{workflow}/result").status_code == 409


def test_token_admission_and_server_input_limits(env, monkeypatch):
    env[2].admission = AdmissionController({"a": QuotaPolicy(100, 1, 63)})
    # 32 requested output tokens * 2 bound attempts exceeds admission capacity.
    assert env[1]["a"].post("/v1/workflows", json=BODY).status_code == 429
    assert env[0]._db.execute("SELECT count(*) FROM workflows").fetchone()[0] == 0
    env[2].admission = AdmissionController({"a": QuotaPolicy(100, 1, 10000)})
    monkeypatch.setattr(main.settings, "max_prompt_chars", 3)
    assert env[1]["a"].post("/v1/workflows", json=BODY).status_code == 422
    monkeypatch.setattr(main.settings, "max_prompt_chars", 100000)
    monkeypatch.setattr(main.settings, "max_generation_tokens", 16)
    assert env[1]["a"].post("/v1/workflows", json=BODY).status_code == 422


def test_saved_policy_cannot_be_weakened_by_configuration_change(env):
    store = env[0]
    workflow = created(env)
    env[3]["a"] = WorkflowPolicy.model_validate(
        {**POLICY, "acceptance": {"minimum_chars": 0}}
    )
    fence = store.claim("a", workflow, "worker")
    store.complete(
        "a",
        workflow,
        "worker",
        fence,
        {"output": {"text": "forbidden"}},
        succeeded=True,
    )
    assert store.validate("a", workflow)["decision"] == "rejected"
    assert env[1]["a"].get(f"/v1/workflows/{workflow}/result").status_code == 409
