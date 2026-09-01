import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from backend.control.admission import AdmissionController, QuotaPolicy
from backend.control.api import load_api_control
from backend.control.deployments import DeploymentLifecycle, DeploymentState
from backend.control.governance import (
    ArtifactManifest,
    DataClassification,
    DataGovernancePolicy,
    verify_artifact,
)
from backend.control.observability import ControlEvent
from backend.control.records import ExecutionRecord, SQLiteExecutionRecordStore
from backend.control.security import (
    Principal,
    Role,
    SecretRef,
    authenticate_api_key,
    authorize,
    issue_api_key,
    resolve_secret_ref,
)


def test_api_keys_are_hashed_and_tenant_authorization_denies_by_default() -> None:
    principal = Principal("user-1", "tenant-a", frozenset({Role.INFERENCE}))
    key, record = issue_api_key(principal)
    assert key not in record.digest
    assert authenticate_api_key(key, {record.key_id: record}) == principal
    assert authenticate_api_key(key + "x", {record.key_id: record}) is None
    assert authorize(principal, tenant_id="tenant-a", role=Role.INFERENCE)
    assert not authorize(principal, tenant_id="tenant-b", role=Role.INFERENCE)
    assert not authorize(principal, tenant_id="tenant-a", role=Role.OPERATOR)


def test_expired_and_revoked_api_keys_are_rejected() -> None:
    principal = Principal("user-1", "tenant-a", frozenset({Role.INFERENCE}))
    now = datetime.now(UTC)
    key, expired = issue_api_key(principal, expires_at=now - timedelta(seconds=1))
    assert authenticate_api_key(
        key, {expired.key_id: expired}, now=now
    ) is None

    key, active = issue_api_key(principal, expires_at=now + timedelta(hours=1))
    revoked = replace(active, revoked_at=now)
    assert authenticate_api_key(
        key, {revoked.key_id: revoked}, now=now
    ) is None


def test_server_control_configuration_loads_hashes_quotas_and_store(tmp_path) -> None:
    principal = Principal("user-1", "tenant-a", frozenset({Role.INFERENCE}))
    key, record = issue_api_key(principal)
    config = tmp_path / "control.json"
    config.write_text(
        json.dumps(
            {
                "api_keys": [
                    {
                        "key_id": record.key_id,
                        "salt": record.salt,
                        "digest": record.digest,
                        "principal_id": principal.principal_id,
                        "tenant_id": principal.tenant_id,
                        "roles": ["inference"],
                    }
                ],
                "quotas": {
                    "tenant-a": {
                        "requests_per_minute": 10,
                        "concurrent_requests": 1,
                        "tokens_per_minute": 100,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    control = load_api_control(config, tmp_path / "records.db")

    assert control.authenticate(f"Bearer {key}") == principal
    permit = control.admit(principal, 10)
    permit.release()
    assert control.records is not None
    control.close()


def test_admission_enforces_request_token_and_concurrency_limits() -> None:
    controller = AdmissionController({"tenant-a": QuotaPolicy(2, 1, 10)})
    assert controller.admit("tenant-a", 6, now=0)
    assert not controller.admit("tenant-a", 1, now=1)
    controller.release("tenant-a")
    assert not controller.admit("tenant-a", 5, now=2)
    assert controller.admit("tenant-a", 5, now=61)
    assert not controller.admit("unknown", 1)


def test_records_are_tenant_scoped_durable_and_backupable(tmp_path) -> None:
    store = SQLiteExecutionRecordStore(tmp_path / "records.db")
    record = ExecutionRecord(
        "request-1",
        "tenant-a",
        "accepted",
        "policy-v1",
        {"deployment": "one"},
        datetime.now(UTC),
    )
    store.put(record)
    assert store.get("tenant-a", "request-1") == record
    assert store.get("tenant-b", "request-1") is None
    backup = tmp_path / "backup.db"
    store.backup(backup)
    assert backup.exists()
    assert store.health() == {"ready": True, "schema_version": 2, "durable": True}
    store.close()


def test_records_append_when_a_correlation_id_is_reused(tmp_path) -> None:
    store = SQLiteExecutionRecordStore(tmp_path / "records.db")
    first = ExecutionRecord(
        "request-1",
        "tenant-a",
        "failed",
        "policy-v1",
        {"attempt": 1},
        datetime.now(UTC),
    )
    second = replace(
        first,
        status="accepted",
        payload={"attempt": 2},
        created_at=datetime.now(UTC),
    )

    store.put(first)
    store.put(second)

    assert store.get("tenant-a", "request-1") == second
    store.close()


def test_record_store_migrates_v1_without_losing_records(tmp_path) -> None:
    database = tmp_path / "records.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE schema_meta (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_meta VALUES (1)")
    connection.execute(
        "CREATE TABLE execution_records ("
        "request_id TEXT NOT NULL, tenant_id TEXT NOT NULL, "
        "status TEXT NOT NULL, policy_version TEXT NOT NULL, "
        "payload_json TEXT NOT NULL, created_at TEXT NOT NULL, "
        "PRIMARY KEY (tenant_id, request_id))"
    )
    created_at = datetime.now(UTC)
    connection.execute(
        "INSERT INTO execution_records VALUES (?, ?, ?, ?, ?, ?)",
        (
            "request-1",
            "tenant-a",
            "accepted",
            "policy-v1",
            '{"safe": true}',
            created_at.isoformat(),
        ),
    )
    connection.commit()
    connection.close()

    store = SQLiteExecutionRecordStore(database)

    record = store.get("tenant-a", "request-1")
    assert record is not None
    assert record.payload == {"safe": True}
    assert store.health()["schema_version"] == 2
    store.close()


def test_artifact_integrity_and_governance_fail_closed(tmp_path) -> None:
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"pinned model bytes")
    digest = sha256(artifact.read_bytes()).hexdigest()
    manifest = ArtifactManifest(
        "model-a", digest, True, True, "https://provenance.example/model-a"
    )
    assert verify_artifact(artifact, manifest)
    assert not verify_artifact(
        artifact,
        ArtifactManifest(
            "model-a", "0" * 64, True, True, "https://provenance.example/model-a"
        ),
    )
    with pytest.raises(ValueError):
        DataGovernancePolicy(
            DataClassification.RESTRICTED,
            frozenset({"us-east"}),
            timedelta(days=7),
            log_payloads=True,
        )


def test_deployment_lifecycle_rejects_unsafe_transitions() -> None:
    deployment = DeploymentLifecycle("deployment-1", "tenant-a")
    for state in (
        DeploymentState.VALIDATING,
        DeploymentState.READY,
        DeploymentState.ACTIVE,
        DeploymentState.DRAINING,
        DeploymentState.RETIRED,
    ):
        deployment = deployment.transition(state)
    assert deployment.state is DeploymentState.RETIRED
    with pytest.raises(ValueError):
        DeploymentLifecycle("deployment-2", "tenant-a").transition(
            DeploymentState.ACTIVE
        )


def test_secret_references_and_observability_do_not_carry_secrets() -> None:
    assert SecretRef("vault", "kv/ryuk/nim").reference == "kv/ryuk/nim"
    event = ControlEvent(
        "inference.completed",
        "tenant-a",
        "request-1",
        datetime.now(UTC),
        {"deployment_id": "one", "prompt": "private", "authorization": "secret"},
    )
    assert event.safe_attributes() == {"deployment_id": "one"}


def test_environment_secret_reference_resolves_without_storing_value(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RYUK_TEST_PROVIDER_SECRET", "provider-secret-value")

    assert resolve_secret_ref("env:RYUK_TEST_PROVIDER_SECRET") == (
        "provider-secret-value"
    )
    with pytest.raises(ValueError, match="Unsupported"):
        resolve_secret_ref("file:/tmp/provider-secret")
