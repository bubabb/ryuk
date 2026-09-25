from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.audit.deterministic import ValidationPolicy
from backend.workflows.contracts import (
    ArtifactRef,
    StoredArtifact,
    TaskPacket,
    canonical_json,
)
from backend.workflows.validation import policy_snapshot, validate_artifact


class WorkflowConflict(ValueError):
    pass


class SQLiteWorkflowStore:
    """Offline single-task store. Expired execution is uncertain, never replayed."""

    schema_version = 5

    def __init__(self, path: Path) -> None:
        self._lock = RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        try:
            with self._transaction():
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS workflow_schema "
                    "(version INTEGER NOT NULL)"
                )
                versions = self._db.execute(
                    "SELECT version FROM workflow_schema"
                ).fetchall()
                if not versions:
                    self._db.execute("INSERT INTO workflow_schema VALUES (5)")
                elif len(versions) != 1 or versions[0][0] not in (1, 2, 3, 4, 5):
                    raise ValueError("Unsupported workflow schema version")
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL, packet TEXT NOT NULL,
                    state TEXT NOT NULL,
                    fence INTEGER NOT NULL DEFAULT 0, owner TEXT, lease_until TEXT,
                    result TEXT, result_artifact_id TEXT,
                    UNIQUE(tenant, idempotency_key))""")
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    tenant TEXT NOT NULL, state TEXT NOT NULL,
                    fence INTEGER NOT NULL)""")
                columns = {
                    row["name"]
                    for row in self._db.execute("PRAGMA table_info(workflows)")
                }
                if "result_artifact_id" not in columns:
                    self._db.execute(
                        "ALTER TABLE workflows ADD COLUMN result_artifact_id TEXT"
                    )
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_artifacts (
                    id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
                    tenant TEXT NOT NULL, schema_version INTEGER NOT NULL,
                    sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id))""")
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_validations (
                    workflow_id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id))""")
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_dispatches (
                    workflow_id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                    fence INTEGER NOT NULL, budget_json TEXT NOT NULL,
                    outcome_json TEXT, outcome_sha256 TEXT, succeeded INTEGER,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id))""")
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_bindings (
                    workflow_id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                    binding_json TEXT NOT NULL,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id))""")
                if versions and versions[0][0] < 3:
                    legacy = self._db.execute(
                        "SELECT id, tenant, fence FROM workflows "
                        "WHERE state='succeeded'"
                    ).fetchall()
                    for row in legacy:
                        self._db.execute(
                            "UPDATE workflows SET state='awaiting_validation' "
                            "WHERE id=?",
                            (row["id"],),
                        )
                        self._event(
                            row["tenant"],
                            row["id"],
                            "awaiting_validation",
                            row["fence"],
                        )
                self._db.execute("UPDATE workflow_schema SET version=5")
        except Exception:
            self._db.close()
            raise

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    @staticmethod
    def _identifier(value: str) -> None:
        if not value or value != value.strip():
            raise ValueError("Identifiers must be nonempty without outer whitespace")

    @staticmethod
    def _now(now: datetime | None) -> datetime:
        value = datetime.now(UTC) if now is None else now
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value.astimezone(UTC)

    def _event(self, tenant: str, workflow_id: str, state: str, fence: int) -> None:
        self._db.execute(
            "INSERT INTO workflow_events(workflow_id, tenant, state, fence) "
            "VALUES (?, ?, ?, ?)",
            (workflow_id, tenant, state, fence),
        )

    def create(
        self,
        tenant: str,
        key: str,
        packet: TaskPacket,
        *,
        binding: dict[str, Any] | None = None,
    ) -> str:
        self._identifier(tenant)
        self._identifier(key)
        if not isinstance(packet, TaskPacket):
            raise ValueError("Workflow creation requires a TaskPacket")
        validated = TaskPacket.from_dict(packet.to_dict())
        encoded = canonical_json(validated.to_dict())
        bound = canonical_json(binding) if binding is not None else None
        hashed = (
            encoded
            if bound is None
            else canonical_json(
                {"packet": validated.to_dict(), "binding": json.loads(bound)}
            )
        )
        digest = hashlib.sha256(hashed.encode()).hexdigest()
        with self._transaction():
            row = self._db.execute(
                "SELECT id, request_hash FROM workflows WHERE tenant=? AND "
                "idempotency_key=?",
                (tenant, key),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != digest:
                    raise WorkflowConflict(
                        "Idempotency key conflicts with existing input"
                    )
                return row["id"]
            workflow_id = str(uuid4())
            self._db.execute(
                "INSERT INTO workflows(id, tenant, idempotency_key, request_hash, "
                "packet, state) VALUES (?, ?, ?, ?, ?, 'ready')",
                (workflow_id, tenant, key, digest, encoded),
            )
            if bound is not None:
                self._db.execute(
                    "INSERT INTO workflow_bindings VALUES (?, ?, ?)",
                    (workflow_id, tenant, bound),
                )
            self._event(tenant, workflow_id, "ready", 0)
            return workflow_id

    def get_binding(self, tenant: str, workflow_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT binding_json FROM workflow_bindings "
                "WHERE tenant=? AND workflow_id=?",
                (tenant, workflow_id),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def get(self, tenant: str, workflow_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM workflows WHERE tenant=? AND id=?", (tenant, workflow_id)
            ).fetchone()
            if row is None:
                return None
            value = dict(row)
            value["packet"] = json.loads(value["packet"])
            value["result"] = (
                json.loads(value["result"]) if value["result"] is not None else None
            )
            if value["result_artifact_id"] is not None:
                artifact = self.get_artifact(
                    tenant, workflow_id, value["result_artifact_id"]
                )
                if artifact is None:
                    raise ValueError("Workflow result artifact is missing")
                value["result"] = artifact.payload()
            report = self._db.execute(
                "SELECT report_json FROM workflow_validations "
                "WHERE tenant=? AND workflow_id=?",
                (tenant, workflow_id),
            ).fetchone()
            value["validation"] = json.loads(report[0]) if report else None
            return value

    def get_packet(self, tenant: str, workflow_id: str) -> TaskPacket | None:
        workflow = self.get(tenant, workflow_id)
        if workflow is None:
            return None
        return TaskPacket.from_dict(workflow["packet"])

    def list_ready(self, limit: int) -> list[tuple[str, str]]:
        """Return a bounded local snapshot; claiming remains the authority."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Ready workflow limit must be between 1 and 1000")
        with self._lock:
            return [
                (row["tenant"], row["id"])
                for row in self._db.execute(
                    "SELECT tenant, id FROM workflows WHERE state='ready' "
                    "ORDER BY rowid LIMIT ?",
                    (limit,),
                )
            ]

    def get_artifact(
        self,
        tenant: str,
        workflow_id: str,
        artifact_id: str,
    ) -> StoredArtifact | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM workflow_artifacts "
                "WHERE tenant=? AND workflow_id=? AND id=?",
                (tenant, workflow_id, artifact_id),
            ).fetchone()
            if row is None:
                return None
            return StoredArtifact(
                ArtifactRef(
                    row["id"],
                    row["workflow_id"],
                    row["sha256"],
                    row["size_bytes"],
                    row["schema_version"],
                ),
                row["content_json"],
            )

    def claim(
        self,
        tenant: str,
        workflow_id: str,
        owner: str,
        *,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> int:
        self._identifier(owner)
        if not 1 <= lease_seconds <= 3600:
            raise ValueError("Lease must be between 1 and 3600 seconds")
        with self._transaction():
            expiry = (self._now(now) + timedelta(seconds=lease_seconds)).isoformat()
            row = self._db.execute(
                "SELECT state, fence, packet FROM workflows WHERE tenant=? AND id=?",
                (tenant, workflow_id),
            ).fetchone()
            if row is None or row["state"] != "ready":
                raise WorkflowConflict("Workflow is not claimable")
            TaskPacket.from_dict(json.loads(row["packet"]))
            fence = row["fence"] + 1
            self._db.execute(
                "UPDATE workflows SET state='running', fence=?, owner=?, "
                "lease_until=? WHERE tenant=? AND id=?",
                (fence, owner, expiry, tenant, workflow_id),
            )
            self._event(tenant, workflow_id, "running", fence)
            return fence

    def _require_lease(
        self,
        tenant: str,
        workflow_id: str,
        owner: str,
        fence: int,
        now: datetime | None,
    ) -> None:
        row = self._db.execute(
            "SELECT state, owner, fence, lease_until FROM workflows "
            "WHERE tenant=? AND id=?",
            (tenant, workflow_id),
        ).fetchone()
        if (
            row is None
            or row["state"] != "running"
            or row["owner"] != owner
            or row["fence"] != fence
            or datetime.fromisoformat(row["lease_until"]) <= self._now(now)
        ):
            raise WorkflowConflict("Stale or unauthorized workflow execution")

    def begin_dispatch(
        self,
        tenant: str,
        workflow_id: str,
        owner: str,
        fence: int,
        budget: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> None:
        """Persist intent before any router call; duplicate dispatch is forbidden."""
        encoded = canonical_json(budget)
        with self._transaction():
            self._require_lease(tenant, workflow_id, owner, fence, now)
            if self._db.execute(
                "SELECT 1 FROM workflow_dispatches WHERE workflow_id=?",
                (workflow_id,),
            ).fetchone():
                raise WorkflowConflict("Workflow dispatch already recorded")
            self._db.execute(
                "INSERT INTO workflow_dispatches "
                "(workflow_id, tenant, fence, budget_json) VALUES (?, ?, ?, ?)",
                (workflow_id, tenant, fence, encoded),
            )
            self._event(tenant, workflow_id, "dispatch_started", fence)

    def record_outcome(
        self,
        tenant: str,
        workflow_id: str,
        owner: str,
        fence: int,
        result: dict[str, Any],
        *,
        succeeded: bool,
        now: datetime | None = None,
    ) -> None:
        """Durably save a returned outcome without accepting or replaying it."""
        if not isinstance(result, dict) or type(succeeded) is not bool:
            raise ValueError("A result object and boolean success are required")
        encoded = canonical_json(result)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self._transaction():
            self._require_lease(tenant, workflow_id, owner, fence, now)
            row = self._db.execute(
                "SELECT * FROM workflow_dispatches WHERE tenant=? AND workflow_id=?",
                (tenant, workflow_id),
            ).fetchone()
            if row is None or row["fence"] != fence:
                raise WorkflowConflict("No matching dispatch")
            if row["outcome_json"] is not None:
                if (
                    row["outcome_json"] != encoded
                    or row["succeeded"] != int(succeeded)
                    or row["outcome_sha256"] != digest
                ):
                    raise WorkflowConflict("Outcome conflicts with recorded result")
                return
            self._db.execute(
                "UPDATE workflow_dispatches SET outcome_json=?, outcome_sha256=?, "
                "succeeded=? WHERE tenant=? AND workflow_id=?",
                (encoded, digest, int(succeeded), tenant, workflow_id),
            )
            self._event(tenant, workflow_id, "outcome_recorded", fence)

    def reconcile_uncertain(self, tenant: str, workflow_id: str) -> str:
        """Use only durable local evidence. Missing evidence never authorizes replay."""
        with self._transaction():
            row = self._db.execute(
                "SELECT state, fence FROM workflows WHERE tenant=? AND id=?",
                (tenant, workflow_id),
            ).fetchone()
            if row is None:
                raise WorkflowConflict("Workflow not found")
            if row["state"] != "uncertain":
                return row["state"]
            journal = self._db.execute(
                "SELECT * FROM workflow_dispatches WHERE tenant=? AND workflow_id=?",
                (tenant, workflow_id),
            ).fetchone()
            if journal is None or journal["outcome_json"] is None:
                return "uncertain"
            encoded = journal["outcome_json"]
            if (
                journal["fence"] + 1 != row["fence"]
                or hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                != journal["outcome_sha256"]
                or journal["succeeded"] not in (0, 1)
                or not isinstance(json.loads(encoded), dict)
            ):
                raise WorkflowConflict("Invalid durable outcome evidence")
            succeeded = bool(journal["succeeded"])
            self._commit_result(tenant, workflow_id, row["fence"], encoded, succeeded)
            return "awaiting_validation" if succeeded else "failed"

    def complete(
        self,
        tenant: str,
        workflow_id: str,
        owner: str,
        fence: int,
        result: dict[str, Any],
        *,
        succeeded: bool,
        now: datetime | None = None,
    ) -> ArtifactRef:
        if not isinstance(result, dict) or type(succeeded) is not bool:
            raise ValueError("A result object and boolean success are required")
        encoded = canonical_json(result)
        with self._transaction():
            self._require_lease(tenant, workflow_id, owner, fence, now)
            journal = self._db.execute(
                "SELECT * FROM workflow_dispatches WHERE tenant=? AND workflow_id=?",
                (tenant, workflow_id),
            ).fetchone()
            if journal is not None and (
                journal["outcome_json"] != encoded
                or journal["succeeded"] != int(succeeded)
                or journal["fence"] != fence
                or journal["outcome_sha256"]
                != hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            ):
                raise WorkflowConflict("Completion differs from recorded outcome")
            return self._commit_result(tenant, workflow_id, fence, encoded, succeeded)

    def _commit_result(
        self, tenant: str, workflow_id: str, fence: int, encoded: str, succeeded: bool
    ) -> ArtifactRef:
        """Caller must hold the write transaction and authorize the transition."""
        artifact = ArtifactRef(
            artifact_id=str(uuid4()),
            workflow_id=workflow_id,
            sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            size_bytes=len(encoded.encode("utf-8")),
        )
        self._db.execute(
            "INSERT INTO workflow_artifacts "
            "(id, workflow_id, tenant, schema_version, sha256, "
            "size_bytes, content_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                artifact.artifact_id,
                workflow_id,
                tenant,
                artifact.schema_version,
                artifact.sha256,
                artifact.size_bytes,
                encoded,
            ),
        )
        state = "awaiting_validation" if succeeded else "failed"
        self._db.execute(
            "UPDATE workflows SET state=?, result=?, result_artifact_id=?, "
            "owner=NULL, "
            "lease_until=NULL WHERE tenant=? AND id=?",
            (state, encoded, artifact.artifact_id, tenant, workflow_id),
        )
        self._event(tenant, workflow_id, state, fence)
        return artifact

    def validate(
        self, tenant: str, workflow_id: str, policy: ValidationPolicy | None = None
    ) -> dict[str, Any]:
        """Commit one artifact-bound decision; replay never reruns inference."""
        with self._transaction():
            binding = self.get_binding(tenant, workflow_id)
            if binding is not None:
                snapshot = binding["policy"]
                if policy is not None and policy_snapshot(policy) != snapshot:
                    raise WorkflowConflict("Validation differs from bound policy")
            elif policy is not None:
                snapshot = policy_snapshot(policy)
            else:
                raise WorkflowConflict("Workflow has no bound acceptance policy")
            row = self._db.execute(
                "SELECT state, fence, result_artifact_id FROM workflows "
                "WHERE tenant=? AND id=?",
                (tenant, workflow_id),
            ).fetchone()
            if row is None:
                raise WorkflowConflict("Workflow is not eligible for validation")
            previous = self._db.execute(
                "SELECT report_json FROM workflow_validations "
                "WHERE tenant=? AND workflow_id=?",
                (tenant, workflow_id),
            ).fetchone()
            artifact = self.get_artifact(tenant, workflow_id, row["result_artifact_id"])
            if artifact is None:
                raise WorkflowConflict("Workflow result artifact is missing")
            if previous is not None:
                report = json.loads(previous[0])
                if report["policy"] != snapshot or report["artifact"] != {
                    "artifact_id": artifact.ref.artifact_id,
                    "sha256": artifact.ref.sha256,
                }:
                    raise WorkflowConflict(
                        "Validation replay conflicts with recorded input"
                    )
                return report
            if row["state"] != "awaiting_validation":
                raise WorkflowConflict("Workflow is not eligible for validation")
            report = validate_artifact(artifact, snapshot)
            state = "succeeded" if report["decision"] == "accepted" else "rejected"
            self._db.execute(
                "INSERT INTO workflow_validations VALUES (?, ?, ?)",
                (workflow_id, tenant, canonical_json(report)),
            )
            self._db.execute(
                "UPDATE workflows SET state=? WHERE tenant=? AND id=?",
                (state, tenant, workflow_id),
            )
            self._event(tenant, workflow_id, state, row["fence"])
            return report

    def cancel(self, tenant: str, workflow_id: str) -> bool:
        with self._transaction():
            row = self._db.execute(
                "SELECT state, fence FROM workflows WHERE tenant=? AND id=?",
                (tenant, workflow_id),
            ).fetchone()
            if row is None:
                return False
            if row["state"] == "cancelled":
                return True
            if row["state"] not in ("ready", "running", "awaiting_validation"):
                return False
            fence = row["fence"] + 1
            self._db.execute(
                "UPDATE workflows SET state='cancelled', fence=?, owner=NULL, "
                "lease_until=NULL WHERE tenant=? AND id=?",
                (fence, tenant, workflow_id),
            )
            self._event(tenant, workflow_id, "cancelled", fence)
            return True

    def recover_expired(self, tenant: str, *, now: datetime | None = None) -> int:
        with self._transaction():
            current = self._now(now).isoformat()
            rows = self._db.execute(
                "SELECT id, fence FROM workflows WHERE tenant=? AND "
                "state='running' AND lease_until<=?",
                (tenant, current),
            ).fetchall()
            for row in rows:
                fence = row["fence"] + 1
                self._db.execute(
                    "UPDATE workflows SET state='uncertain', fence=?, owner=NULL, "
                    "lease_until=NULL WHERE tenant=? AND id=?",
                    (fence, tenant, row["id"]),
                )
                self._event(tenant, row["id"], "uncertain", fence)
            return len(rows)

    def events(self, tenant: str, workflow_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(row)
                for row in self._db.execute(
                    "SELECT sequence, state, fence FROM workflow_events WHERE "
                    "tenant=? AND workflow_id=? ORDER BY sequence",
                    (tenant, workflow_id),
                )
            ]

    def close(self) -> None:
        with self._lock:
            self._db.close()
