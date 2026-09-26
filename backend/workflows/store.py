from __future__ import annotations

import hashlib
import json
import math
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
from backend.workflows.graph import GraphState, NodeState, WorkflowGraph
from backend.workflows.validation import policy_snapshot, validate_artifact


class WorkflowConflict(ValueError):
    pass


class SQLiteWorkflowStore:
    """Offline workflow store. Expired execution is uncertain, never replayed."""

    schema_version = 8

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
                    self._db.execute("INSERT INTO workflow_schema VALUES (8)")
                elif len(versions) != 1 or versions[0][0] not in (
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7,
                    8,
                ):
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
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_graphs (
                    id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
                    graph_json TEXT NOT NULL, binding_json TEXT,
                    UNIQUE(tenant, idempotency_key))""")
                graph_columns = {
                    row["name"]
                    for row in self._db.execute("PRAGMA table_info(workflow_graphs)")
                }
                if "binding_json" not in graph_columns:
                    self._db.execute(
                        "ALTER TABLE workflow_graphs ADD COLUMN binding_json TEXT"
                    )
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_graph_nodes (
                    graph_id TEXT NOT NULL, node_id TEXT NOT NULL,
                    tenant TEXT NOT NULL, state TEXT NOT NULL,
                    fence INTEGER NOT NULL DEFAULT 0, owner TEXT, lease_until TEXT,
                    result_artifact_id TEXT,
                    PRIMARY KEY(graph_id, node_id),
                    FOREIGN KEY(graph_id) REFERENCES workflow_graphs(id))""")
                graph_node_columns = {
                    row["name"]
                    for row in self._db.execute(
                        "PRAGMA table_info(workflow_graph_nodes)"
                    )
                }
                for definition in (
                    "fence INTEGER NOT NULL DEFAULT 0",
                    "owner TEXT",
                    "lease_until TEXT",
                    "result_artifact_id TEXT",
                ):
                    name = definition.split()[0]
                    if name not in graph_node_columns:
                        self._db.execute(
                            f"ALTER TABLE workflow_graph_nodes ADD COLUMN {definition}"
                        )
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_graph_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_id TEXT NOT NULL, node_id TEXT NOT NULL,
                    tenant TEXT NOT NULL, state TEXT NOT NULL,
                    FOREIGN KEY(graph_id) REFERENCES workflow_graphs(id))""")
                self._db.execute("""CREATE TABLE IF NOT EXISTS workflow_graph_budgets (
                    graph_id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                    deadline_at TEXT NOT NULL, max_attempts INTEGER NOT NULL,
                    max_output_tokens INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(graph_id) REFERENCES workflow_graphs(id))""")
                self._db.execute("""CREATE TABLE IF NOT EXISTS
                    workflow_graph_artifacts (
                    id TEXT PRIMARY KEY, graph_id TEXT NOT NULL, node_id TEXT NOT NULL,
                    tenant TEXT NOT NULL, schema_version INTEGER NOT NULL,
                    sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                    content_json TEXT NOT NULL, accepted INTEGER NOT NULL DEFAULT 0,
                    validation_json TEXT,
                    FOREIGN KEY(graph_id) REFERENCES workflow_graphs(id))""")
                graph_artifact_columns = {
                    row["name"]
                    for row in self._db.execute(
                        "PRAGMA table_info(workflow_graph_artifacts)"
                    )
                }
                if "validation_json" not in graph_artifact_columns:
                    self._db.execute(
                        "ALTER TABLE workflow_graph_artifacts "
                        "ADD COLUMN validation_json TEXT"
                    )
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
                self._db.execute("UPDATE workflow_schema SET version=8")
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

    def create_graph(
        self,
        tenant: str,
        key: str,
        graph: WorkflowGraph,
        *,
        budget: tuple[float, int, int | None] | None = None,
        binding: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> str:
        """Persist a canonical graph and its initial scheduler state atomically."""
        self._identifier(tenant)
        self._identifier(key)
        if not isinstance(graph, WorkflowGraph):
            raise ValueError("Graph creation requires a WorkflowGraph")
        validated = WorkflowGraph.from_dict(graph.to_dict())
        encoded = canonical_json(validated.to_dict())
        bound = canonical_json(binding) if binding is not None else None
        if budget is not None or bound is not None:
            budget_value: dict[str, Any] | None = None
            if budget is not None:
                deadline_seconds, max_attempts, max_output_tokens = budget
                self._validate_graph_budget(
                    deadline_seconds, max_attempts, max_output_tokens
                )
                budget_value = {
                    "deadline_seconds": deadline_seconds,
                    "max_attempts": max_attempts,
                    "max_output_tokens": max_output_tokens,
                }
            hashed = canonical_json(
                {
                    "graph": validated.to_dict(),
                    "budget": budget_value,
                    "binding": json.loads(bound) if bound is not None else None,
                }
            )
        else:
            hashed = encoded
        digest = hashlib.sha256(hashed.encode("utf-8")).hexdigest()
        initial = validated.initial_state()
        with self._transaction():
            row = self._db.execute(
                "SELECT id, request_hash FROM workflow_graphs WHERE tenant=? AND "
                "idempotency_key=?",
                (tenant, key),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != digest:
                    raise WorkflowConflict(
                        "Graph idempotency key conflicts with existing input"
                    )
                return row["id"]
            graph_id = str(uuid4())
            self._db.execute(
                "INSERT INTO workflow_graphs"
                "(id, tenant, idempotency_key, request_hash, graph_json, "
                "binding_json) VALUES (?, ?, ?, ?, ?, ?)",
                (graph_id, tenant, key, digest, encoded, bound),
            )
            for node_id, state in initial.node_states:
                self._db.execute(
                    "INSERT INTO workflow_graph_nodes"
                    "(graph_id, node_id, tenant, state) VALUES (?, ?, ?, ?)",
                    (graph_id, node_id, tenant, state.value),
                )
                self._graph_event(tenant, graph_id, node_id, state)
            if budget is not None:
                deadline_seconds, max_attempts, max_output_tokens = budget
                deadline = (
                    self._now(now) + timedelta(seconds=deadline_seconds)
                ).isoformat()
                self._db.execute(
                    "INSERT INTO workflow_graph_budgets"
                    "(graph_id, tenant, deadline_at, max_attempts, "
                    "max_output_tokens) VALUES (?, ?, ?, ?, ?)",
                    (
                        graph_id,
                        tenant,
                        deadline,
                        max_attempts,
                        max_output_tokens,
                    ),
                )
            return graph_id

    def get_graph_binding(self, tenant: str, graph_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT binding_json FROM workflow_graphs WHERE tenant=? AND id=?",
                (tenant, graph_id),
            ).fetchone()
            if row is None or row["binding_json"] is None:
                return None
            return json.loads(row["binding_json"])

    def _graph_event(
        self,
        tenant: str,
        graph_id: str,
        node_id: str,
        state: NodeState,
    ) -> None:
        self._db.execute(
            "INSERT INTO workflow_graph_events(graph_id, node_id, tenant, state) "
            "VALUES (?, ?, ?, ?)",
            (graph_id, node_id, tenant, state.value),
        )

    def _get_graph_state(self, tenant: str, graph_id: str) -> GraphState | None:
        row = self._db.execute(
            "SELECT graph_json FROM workflow_graphs WHERE tenant=? AND id=?",
            (tenant, graph_id),
        ).fetchone()
        if row is None:
            return None
        graph = WorkflowGraph.from_dict(json.loads(row["graph_json"]))
        rows = self._db.execute(
            "SELECT node_id, state FROM workflow_graph_nodes "
            "WHERE tenant=? AND graph_id=? ORDER BY node_id",
            (tenant, graph_id),
        ).fetchall()
        try:
            states = tuple((item["node_id"], NodeState(item["state"])) for item in rows)
            return GraphState(graph, states)
        except ValueError as exc:
            raise ValueError("Invalid persisted workflow graph state") from exc

    def get_graph_state(self, tenant: str, graph_id: str) -> GraphState | None:
        with self._lock:
            return self._get_graph_state(tenant, graph_id)

    def get_graph_node_packet(
        self, tenant: str, graph_id: str, node_id: str
    ) -> TaskPacket | None:
        state = self.get_graph_state(tenant, graph_id)
        if state is None:
            return None
        for node in state.graph.nodes:
            if node.node_id == node_id:
                return node.packet
        return None

    def transition_graph_node(
        self,
        tenant: str,
        graph_id: str,
        node_id: str,
        target: NodeState,
    ) -> GraphState:
        """Commit one transition and all derived readiness/skip changes atomically."""
        if not isinstance(target, NodeState):
            raise ValueError("Graph transition target must be a NodeState")
        with self._transaction():
            return self._transition_graph_node(tenant, graph_id, node_id, target)

    def _transition_graph_node(
        self, tenant: str, graph_id: str, node_id: str, target: NodeState
    ) -> GraphState:
        """Apply a transition while the caller holds the write transaction."""
        current = self._get_graph_state(tenant, graph_id)
        if current is None:
            raise WorkflowConflict("Workflow graph not found")
        try:
            updated = current.transition(node_id, target)
        except ValueError as exc:
            raise WorkflowConflict("Illegal workflow graph transition") from exc
        before = dict(current.node_states)
        after = dict(updated.node_states)
        pending = {
            changed_node
            for changed_node, state in updated.node_states
            if before[changed_node] is not state
        }
        ordered: list[str] = []
        if node_id in pending:
            ordered.append(node_id)
            pending.remove(node_id)
        dependencies = {
            node.node_id: set(node.depends_on) for node in updated.graph.nodes
        }
        while pending:
            eligible = [
                node.node_id
                for node in updated.graph.nodes
                if node.node_id in pending and not dependencies[node.node_id] & pending
            ]
            if not eligible:  # Defensive: graph validation already rejects cycles.
                raise ValueError("Invalid derived graph transition ordering")
            ordered.extend(eligible)
            pending.difference_update(eligible)
        for changed_node in ordered:
            state = after[changed_node]
            cursor = self._db.execute(
                "UPDATE workflow_graph_nodes SET state=? "
                "WHERE tenant=? AND graph_id=? AND node_id=? AND state=?",
                (
                    state.value,
                    tenant,
                    graph_id,
                    changed_node,
                    before[changed_node].value,
                ),
            )
            if cursor.rowcount != 1:
                raise WorkflowConflict("Workflow graph state changed concurrently")
            self._graph_event(tenant, graph_id, changed_node, state)
        return updated

    def list_ready_graph_nodes(self, limit: int) -> list[tuple[str, str, str]]:
        """Return a bounded advisory snapshot; WF-016 will define claiming."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Ready graph-node limit must be between 1 and 1000")
        with self._lock:
            return [
                (row["tenant"], row["graph_id"], row["node_id"])
                for row in self._db.execute(
                    "SELECT tenant, graph_id, node_id FROM workflow_graph_nodes "
                    "WHERE state=? ORDER BY rowid LIMIT ?",
                    (NodeState.READY.value, limit),
                )
            ]

    def graph_events(self, tenant: str, graph_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(row)
                for row in self._db.execute(
                    "SELECT sequence, node_id, state FROM workflow_graph_events "
                    "WHERE tenant=? AND graph_id=? ORDER BY sequence",
                    (tenant, graph_id),
                )
            ]

    def bind_graph_budget(
        self,
        tenant: str,
        graph_id: str,
        *,
        deadline_seconds: float,
        max_attempts: int,
        max_output_tokens: int | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._validate_graph_budget(deadline_seconds, max_attempts, max_output_tokens)
        deadline = (self._now(now) + timedelta(seconds=deadline_seconds)).isoformat()
        with self._transaction():
            if self._get_graph_state(tenant, graph_id) is None:
                raise WorkflowConflict("Workflow graph not found")
            existing = self._db.execute(
                "SELECT * FROM workflow_graph_budgets WHERE tenant=? AND graph_id=?",
                (tenant, graph_id),
            ).fetchone()
            if existing is not None:
                actual = (
                    existing["max_attempts"],
                    existing["max_output_tokens"],
                )
                if actual != (max_attempts, max_output_tokens):
                    raise WorkflowConflict("Graph budget is already bound")
                return dict(existing)
            self._db.execute(
                "INSERT INTO workflow_graph_budgets"
                "(graph_id, tenant, deadline_at, max_attempts, max_output_tokens) "
                "VALUES (?, ?, ?, ?, ?)",
                (graph_id, tenant, deadline, max_attempts, max_output_tokens),
            )
            return dict(
                self._db.execute(
                    "SELECT * FROM workflow_graph_budgets WHERE graph_id=?",
                    (graph_id,),
                ).fetchone()
            )

    @staticmethod
    def _validate_graph_budget(
        deadline_seconds: float,
        max_attempts: int,
        max_output_tokens: int | None,
    ) -> None:
        if (
            type(deadline_seconds) not in (int, float)
            or deadline_seconds <= 0
            or not math.isfinite(deadline_seconds)
            or type(max_attempts) is not int
            or max_attempts < 1
            or (
                max_output_tokens is not None
                and (type(max_output_tokens) is not int or max_output_tokens < 1)
            )
        ):
            raise ValueError("Invalid graph budget")

    def get_graph_budget(self, tenant: str, graph_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM workflow_graph_budgets WHERE tenant=? AND graph_id=?",
                (tenant, graph_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def reserve_graph_attempt(
        self, tenant: str, graph_id: str, *, now: datetime | None = None
    ) -> bool:
        with self._transaction():
            row = self._db.execute(
                "SELECT * FROM workflow_graph_budgets WHERE tenant=? AND graph_id=?",
                (tenant, graph_id),
            ).fetchone()
            if row is None:
                raise WorkflowConflict("Graph budget is not bound")
            if (
                datetime.fromisoformat(row["deadline_at"]) <= self._now(now)
                or row["attempts"] >= row["max_attempts"]
            ):
                return False
            self._db.execute(
                "UPDATE workflow_graph_budgets SET attempts=attempts+1 "
                "WHERE tenant=? AND graph_id=?",
                (tenant, graph_id),
            )
            return True

    def record_graph_output_tokens(
        self, tenant: str, graph_id: str, count: int | None
    ) -> bool:
        if count is None:
            return True
        if type(count) is not int or count < 0:
            raise ValueError("Output token count must be a nonnegative integer")
        with self._transaction():
            row = self._db.execute(
                "SELECT * FROM workflow_graph_budgets WHERE tenant=? AND graph_id=?",
                (tenant, graph_id),
            ).fetchone()
            if row is None:
                raise WorkflowConflict("Graph budget is not bound")
            if (
                row["max_output_tokens"] is not None
                and row["output_tokens"] + count > row["max_output_tokens"]
            ):
                return False
            self._db.execute(
                "UPDATE workflow_graph_budgets SET output_tokens=output_tokens+? "
                "WHERE tenant=? AND graph_id=?",
                (count, tenant, graph_id),
            )
            return True

    def claim_graph_node(
        self,
        tenant: str,
        graph_id: str,
        node_id: str,
        owner: str,
        *,
        lease_seconds: int = 30,
        now: datetime | None = None,
    ) -> int:
        self._identifier(owner)
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("Lease must be between 1 and 3600 seconds")
        with self._transaction():
            budget = self._db.execute(
                "SELECT deadline_at FROM workflow_graph_budgets "
                "WHERE tenant=? AND graph_id=?",
                (tenant, graph_id),
            ).fetchone()
            current = self._now(now)
            if budget is None or datetime.fromisoformat(budget[0]) <= current:
                raise WorkflowConflict("Graph budget is missing or expired")
            row = self._db.execute(
                "SELECT state, fence FROM workflow_graph_nodes "
                "WHERE tenant=? AND graph_id=? AND node_id=?",
                (tenant, graph_id, node_id),
            ).fetchone()
            if row is None or row["state"] != NodeState.READY.value:
                raise WorkflowConflict("Graph node is not claimable")
            fence = row["fence"] + 1
            expiry = (current + timedelta(seconds=lease_seconds)).isoformat()
            cursor = self._db.execute(
                "UPDATE workflow_graph_nodes SET state=?, fence=?, owner=?, "
                "lease_until=? WHERE tenant=? AND graph_id=? AND node_id=? "
                "AND state=? AND fence=?",
                (
                    NodeState.RUNNING.value,
                    fence,
                    owner,
                    expiry,
                    tenant,
                    graph_id,
                    node_id,
                    NodeState.READY.value,
                    row["fence"],
                ),
            )
            if cursor.rowcount != 1:
                raise WorkflowConflict("Graph node claim changed concurrently")
            self._graph_event(tenant, graph_id, node_id, NodeState.RUNNING)
            return fence

    def _require_graph_lease(
        self,
        tenant: str,
        graph_id: str,
        node_id: str,
        owner: str,
        fence: int,
        now: datetime | None,
    ) -> None:
        row = self._db.execute(
            "SELECT state, owner, fence, lease_until FROM workflow_graph_nodes "
            "WHERE tenant=? AND graph_id=? AND node_id=?",
            (tenant, graph_id, node_id),
        ).fetchone()
        if (
            row is None
            or row["state"] != NodeState.RUNNING.value
            or row["owner"] != owner
            or row["fence"] != fence
            or datetime.fromisoformat(row["lease_until"]) <= self._now(now)
        ):
            raise WorkflowConflict("Stale or unauthorized graph-node execution")

    def complete_graph_node(
        self,
        tenant: str,
        graph_id: str,
        node_id: str,
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
            self._require_graph_lease(tenant, graph_id, node_id, owner, fence, now)
            artifact = ArtifactRef(
                str(uuid4()),
                graph_id,
                hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                len(encoded.encode("utf-8")),
            )
            self._db.execute(
                "INSERT INTO workflow_graph_artifacts"
                "(id, graph_id, node_id, tenant, schema_version, sha256, "
                "size_bytes, content_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact.artifact_id,
                    graph_id,
                    node_id,
                    tenant,
                    artifact.schema_version,
                    artifact.sha256,
                    artifact.size_bytes,
                    encoded,
                ),
            )
            target = NodeState.AWAITING_VALIDATION if succeeded else NodeState.FAILED
            self._transition_graph_node(tenant, graph_id, node_id, target)
            self._db.execute(
                "UPDATE workflow_graph_nodes SET owner=NULL, lease_until=NULL, "
                "result_artifact_id=? WHERE tenant=? AND graph_id=? AND node_id=?",
                (artifact.artifact_id, tenant, graph_id, node_id),
            )
            return artifact

    def get_graph_artifact(
        self, tenant: str, graph_id: str, node_id: str
    ) -> StoredArtifact | None:
        with self._lock:
            row = self._db.execute(
                "SELECT a.* FROM workflow_graph_artifacts a "
                "JOIN workflow_graph_nodes n ON n.result_artifact_id=a.id "
                "WHERE a.tenant=? AND a.graph_id=? AND a.node_id=?",
                (tenant, graph_id, node_id),
            ).fetchone()
            if row is None:
                return None
            return StoredArtifact(
                ArtifactRef(
                    row["id"],
                    row["graph_id"],
                    row["sha256"],
                    row["size_bytes"],
                    row["schema_version"],
                ),
                row["content_json"],
            )

    def validate_graph_node(
        self,
        tenant: str,
        graph_id: str,
        node_id: str,
        policy: ValidationPolicy,
    ) -> dict[str, Any]:
        snapshot = policy_snapshot(policy)
        with self._transaction():
            row = self._db.execute(
                "SELECT n.state, a.* FROM workflow_graph_nodes n "
                "JOIN workflow_graph_artifacts a ON n.result_artifact_id=a.id "
                "WHERE n.tenant=? AND n.graph_id=? AND n.node_id=?",
                (tenant, graph_id, node_id),
            ).fetchone()
            if row is None:
                raise WorkflowConflict("Graph node has no result artifact")
            artifact = StoredArtifact(
                ArtifactRef(
                    row["id"],
                    row["graph_id"],
                    row["sha256"],
                    row["size_bytes"],
                    row["schema_version"],
                ),
                row["content_json"],
            )
            if row["validation_json"] is not None:
                report = json.loads(row["validation_json"])
                if report["policy"] != snapshot:
                    raise WorkflowConflict("Graph validation policy changed")
                return report
            if row["state"] != NodeState.AWAITING_VALIDATION.value:
                raise WorkflowConflict("Graph node is not eligible for validation")
            report = validate_artifact(artifact, snapshot)
            accepted = report["decision"] == "accepted"
            self._db.execute(
                "UPDATE workflow_graph_artifacts SET accepted=?, validation_json=? "
                "WHERE id=?",
                (int(accepted), canonical_json(report), artifact.ref.artifact_id),
            )
            self._transition_graph_node(
                tenant,
                graph_id,
                node_id,
                NodeState.SUCCEEDED if accepted else NodeState.REJECTED,
            )
            return report

    def accepted_dependency_artifacts(
        self, tenant: str, graph_id: str, node_id: str
    ) -> tuple[tuple[str, StoredArtifact], ...]:
        with self._lock:
            state = self._get_graph_state(tenant, graph_id)
            if state is None:
                raise WorkflowConflict("Workflow graph not found")
            nodes = {node.node_id: node for node in state.graph.nodes}
            if node_id not in nodes:
                raise WorkflowConflict("Workflow graph node not found")
            artifacts: list[tuple[str, StoredArtifact]] = []
            for dependency in nodes[node_id].depends_on:
                if state.state_of(dependency) is not NodeState.SUCCEEDED:
                    raise WorkflowConflict("Graph dependency is not accepted")
                row = self._db.execute(
                    "SELECT a.* FROM workflow_graph_nodes n "
                    "JOIN workflow_graph_artifacts a ON n.result_artifact_id=a.id "
                    "WHERE n.tenant=? AND n.graph_id=? AND n.node_id=? "
                    "AND a.accepted=1",
                    (tenant, graph_id, dependency),
                ).fetchone()
                if row is None:
                    raise WorkflowConflict("Accepted dependency artifact is missing")
                artifacts.append(
                    (
                        dependency,
                        StoredArtifact(
                            ArtifactRef(
                                row["id"],
                                row["graph_id"],
                                row["sha256"],
                                row["size_bytes"],
                                row["schema_version"],
                            ),
                            row["content_json"],
                        ),
                    )
                )
            return tuple(artifacts)

    def graph_node_records(self, tenant: str, graph_id: str) -> list[dict[str, Any]]:
        with self._lock:
            if self._get_graph_state(tenant, graph_id) is None:
                return []
            return [
                dict(row)
                for row in self._db.execute(
                    "SELECT node_id, state, fence, result_artifact_id "
                    "FROM workflow_graph_nodes WHERE tenant=? AND graph_id=? "
                    "ORDER BY node_id",
                    (tenant, graph_id),
                )
            ]

    def cancel_graph(self, tenant: str, graph_id: str) -> GraphState:
        """Fence active nodes and deterministically skip blocked descendants."""
        with self._transaction():
            state = self._get_graph_state(tenant, graph_id)
            if state is None:
                raise WorkflowConflict("Workflow graph not found")
            for node_id, node_state in tuple(state.node_states):
                if node_state not in {
                    NodeState.READY,
                    NodeState.RUNNING,
                    NodeState.AWAITING_VALIDATION,
                }:
                    continue
                state = self._get_graph_state(tenant, graph_id)
                assert state is not None
                current = state.state_of(node_id)
                if current not in {
                    NodeState.READY,
                    NodeState.RUNNING,
                    NodeState.AWAITING_VALIDATION,
                }:
                    continue
                self._transition_graph_node(
                    tenant, graph_id, node_id, NodeState.CANCELLED
                )
                self._db.execute(
                    "UPDATE workflow_graph_nodes SET fence=fence+1, owner=NULL, "
                    "lease_until=NULL WHERE tenant=? AND graph_id=? AND node_id=?",
                    (tenant, graph_id, node_id),
                )
            final = self._get_graph_state(tenant, graph_id)
            assert final is not None
            return final

    def accepted_graph_results(
        self, tenant: str, graph_id: str
    ) -> tuple[tuple[str, StoredArtifact, dict[str, Any]], ...]:
        with self._lock:
            state = self._get_graph_state(tenant, graph_id)
            if state is None:
                raise WorkflowConflict("Workflow graph not found")
            depended_on = {
                dependency
                for node in state.graph.nodes
                for dependency in node.depends_on
            }
            sinks = [
                node.node_id
                for node in state.graph.nodes
                if node.node_id not in depended_on
            ]
            if not state.terminal or any(
                state.state_of(node_id) is not NodeState.SUCCEEDED for node_id in sinks
            ):
                raise WorkflowConflict("Workflow graph has no accepted result")
            results = []
            for node_id in sinks:
                row = self._db.execute(
                    "SELECT * FROM workflow_graph_artifacts WHERE tenant=? "
                    "AND graph_id=? AND node_id=? AND accepted=1",
                    (tenant, graph_id, node_id),
                ).fetchone()
                if row is None or row["validation_json"] is None:
                    raise WorkflowConflict("Accepted graph result evidence is missing")
                artifact = StoredArtifact(
                    ArtifactRef(
                        row["id"],
                        row["graph_id"],
                        row["sha256"],
                        row["size_bytes"],
                        row["schema_version"],
                    ),
                    row["content_json"],
                )
                results.append((node_id, artifact, json.loads(row["validation_json"])))
            return tuple(results)

    def recover_graph_nodes_startup(
        self, *, limit: int, now: datetime | None = None
    ) -> list[dict[str, str]]:
        """Fence expired graph nodes as uncertain; never replay them."""
        if type(limit) is not int or not 1 <= limit <= 100_000:
            raise ValueError("Recovery scan limit must be between 1 and 100000")
        with self._transaction():
            current = self._now(now).isoformat()
            rows = self._db.execute(
                "SELECT tenant, graph_id, node_id FROM workflow_graph_nodes "
                "WHERE state=? AND lease_until<=? ORDER BY rowid LIMIT ?",
                (NodeState.RUNNING.value, current, limit + 1),
            ).fetchall()
            if len(rows) > limit:
                raise WorkflowConflict("Graph recovery scan limit exceeded")
            recovered = []
            for row in rows:
                self._transition_graph_node(
                    row["tenant"],
                    row["graph_id"],
                    row["node_id"],
                    NodeState.UNCERTAIN,
                )
                self._db.execute(
                    "UPDATE workflow_graph_nodes SET fence=fence+1, owner=NULL, "
                    "lease_until=NULL WHERE tenant=? AND graph_id=? AND node_id=?",
                    (row["tenant"], row["graph_id"], row["node_id"]),
                )
                recovered.append(
                    {
                        "tenant": row["tenant"],
                        "graph_id": row["graph_id"],
                        "node_id": row["node_id"],
                        "reason": "outcome_unknown",
                    }
                )
            return recovered

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

    def recover_startup(
        self, *, limit: int, now: datetime | None = None
    ) -> dict[str, Any]:
        """Recover and reconcile a bounded snapshot without replaying inference."""
        if type(limit) is not int or not 1 <= limit <= 100_000:
            raise ValueError("Recovery scan limit must be between 1 and 100000")
        with self._transaction():
            current = self._now(now).isoformat()
            candidates = self._db.execute(
                "SELECT id, tenant, state, fence FROM workflows WHERE "
                "state='uncertain' OR (state='running' AND lease_until<=?) "
                "ORDER BY rowid LIMIT ?",
                (current, limit + 1),
            ).fetchall()
            if len(candidates) > limit:
                raise WorkflowConflict("Startup recovery scan limit exceeded")
            expired = [row for row in candidates if row["state"] == "running"]
            for row in expired:
                fence = row["fence"] + 1
                self._db.execute(
                    "UPDATE workflows SET state='uncertain', fence=?, owner=NULL, "
                    "lease_until=NULL WHERE tenant=? AND id=?",
                    (fence, row["tenant"], row["id"]),
                )
                self._event(row["tenant"], row["id"], "uncertain", fence)

            reconciled: list[dict[str, str]] = []
            unresolved: list[dict[str, str]] = []
            for candidate in candidates:
                tenant, workflow_id = candidate["tenant"], candidate["id"]
                row = self._db.execute(
                    "SELECT fence FROM workflows WHERE tenant=? AND id=?",
                    (tenant, workflow_id),
                ).fetchone()
                journal = self._db.execute(
                    "SELECT * FROM workflow_dispatches "
                    "WHERE tenant=? AND workflow_id=?",
                    (tenant, workflow_id),
                ).fetchone()
                if journal is None or journal["outcome_json"] is None:
                    unresolved.append(
                        {
                            "tenant": tenant,
                            "workflow_id": workflow_id,
                            "reason": "outcome_unknown",
                        }
                    )
                    continue
                encoded = journal["outcome_json"]
                try:
                    valid = (
                        journal["fence"] + 1 == row["fence"]
                        and hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                        == journal["outcome_sha256"]
                        and journal["succeeded"] in (0, 1)
                        and isinstance(json.loads(encoded), dict)
                    )
                except (AttributeError, TypeError, ValueError):
                    valid = False
                if not valid:
                    unresolved.append(
                        {
                            "tenant": tenant,
                            "workflow_id": workflow_id,
                            "reason": "invalid_outcome_evidence",
                        }
                    )
                    continue
                succeeded = bool(journal["succeeded"])
                self._commit_result(
                    tenant, workflow_id, row["fence"], encoded, succeeded
                )
                reconciled.append(
                    {
                        "tenant": tenant,
                        "workflow_id": workflow_id,
                        "state": "awaiting_validation" if succeeded else "failed",
                    }
                )
            return {
                "scanned": len(candidates),
                "expired": [
                    {"tenant": row["tenant"], "workflow_id": row["id"]}
                    for row in expired
                ],
                "reconciled": reconciled,
                "unresolved": unresolved,
            }

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
