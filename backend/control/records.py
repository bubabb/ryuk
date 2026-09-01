from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    request_id: str
    tenant_id: str
    status: str
    policy_version: str
    payload: dict[str, Any]
    created_at: datetime

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("Execution record timestamps require timezone data.")


class SQLiteExecutionRecordStore:
    """Durable reference store; production HA databases implement this boundary."""

    schema_version = 1

    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL)"
        )
        row = self._connection.execute(
            "SELECT version FROM schema_meta LIMIT 1"
        ).fetchone()
        if row is None:
            self._connection.execute(
                "INSERT INTO schema_meta(version) VALUES (?)", (self.schema_version,)
            )
        elif row[0] != self.schema_version:
            raise RuntimeError("Unsupported execution-record schema version.")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS execution_records ("
            "request_id TEXT NOT NULL, tenant_id TEXT NOT NULL, "
            "status TEXT NOT NULL, policy_version TEXT NOT NULL, "
            "payload_json TEXT NOT NULL, created_at TEXT NOT NULL, "
            "PRIMARY KEY (tenant_id, request_id))"
        )
        self._connection.commit()

    def put(self, record: ExecutionRecord) -> None:
        self._connection.execute(
            "INSERT INTO execution_records VALUES (?, ?, ?, ?, ?, ?)",
            (
                record.request_id,
                record.tenant_id,
                record.status,
                record.policy_version,
                json.dumps(record.payload, sort_keys=True),
                record.created_at.isoformat(),
            ),
        )
        self._connection.commit()

    def get(self, tenant_id: str, request_id: str) -> ExecutionRecord | None:
        row = self._connection.execute(
            "SELECT request_id, tenant_id, status, policy_version, "
            "payload_json, created_at FROM execution_records "
            "WHERE tenant_id = ? AND request_id = ?",
            (tenant_id, request_id),
        ).fetchone()
        if row is None:
            return None
        return ExecutionRecord(
            row[0],
            row[1],
            row[2],
            row[3],
            json.loads(row[4]),
            datetime.fromisoformat(row[5]),
        )

    def backup(self, destination: Path) -> None:
        target = sqlite3.connect(destination)
        try:
            self._connection.backup(target)
        finally:
            target.close()

    def health(self) -> dict[str, object]:
        version = self._connection.execute(
            "SELECT version FROM schema_meta"
        ).fetchone()[0]
        return {"ready": True, "schema_version": version, "durable": True}

    def close(self) -> None:
        self._connection.close()
