from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from backend.context.contracts import (
    ContextPrincipal,
    ContextScope,
    ContextSegment,
    ContextSourceRef,
    ContextTrust,
    ConversationRecord,
)
from backend.inference.contracts import ChatRole

MAX_CONTEXT_SOURCE_CHARS = 200_000


class ContextAccessDenied(PermissionError):
    """The requested conversation or source is outside the actor's scope."""


class ContextConflict(ValueError):
    """An immutable context record conflicts with an existing record."""


class ContextIntegrityError(ValueError):
    """Stored source bytes do not match their saved checksum."""


class SQLiteContextStore:
    """Offline tenant/project/user-scoped conversations and immutable sources."""

    schema_version = 1

    def __init__(self, path: Path) -> None:
        self._lock = RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        try:
            with self._transaction():
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS context_schema "
                    "(version INTEGER NOT NULL)"
                )
                versions = [
                    row["version"]
                    for row in self._db.execute("SELECT version FROM context_schema")
                ]
                if versions and versions != [self.schema_version]:
                    raise ValueError("Unsupported context schema version")
                if not versions:
                    self._db.execute(
                        "INSERT INTO context_schema(version) VALUES (?)",
                        (self.schema_version,),
                    )
                self._db.execute(
                    """CREATE TABLE IF NOT EXISTS context_conversations (
                    tenant_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    scope TEXT NOT NULL CHECK(scope IN ('user', 'project')),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, conversation_id))"""
                )
                self._db.execute(
                    """CREATE TABLE IF NOT EXISTS context_sources (
                    tenant_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    scope TEXT NOT NULL CHECK(scope IN ('user', 'project')),
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    trust TEXT NOT NULL CHECK(trust IN (
                        'user', 'source', 'tool_output', 'generated_summary',
                        'assistant_history')),
                    content TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, source_id, revision))"""
                )
                self._db.execute(
                    """CREATE TABLE IF NOT EXISTS context_entries (
                    tenant_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    source_id TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, conversation_id, sequence),
                    UNIQUE(tenant_id, conversation_id, source_id, source_revision),
                    FOREIGN KEY(tenant_id, conversation_id)
                        REFERENCES context_conversations(tenant_id, conversation_id),
                    FOREIGN KEY(tenant_id, source_id, source_revision)
                        REFERENCES context_sources(tenant_id, source_id, revision))"""
                )
                self._db.execute(
                    "CREATE INDEX IF NOT EXISTS context_entries_recent "
                    "ON context_entries(tenant_id, conversation_id, sequence DESC)"
                )
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

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @staticmethod
    def _id(value: str, name: str) -> None:
        if not value or value != value.strip():
            raise ValueError(f"{name} must be non-empty without outer whitespace.")

    @classmethod
    def _project_member(cls, actor: ContextPrincipal, project_id: str) -> None:
        cls._id(project_id, "project_id")
        if project_id not in actor.project_ids:
            raise ContextAccessDenied("Context is not accessible.")

    @staticmethod
    def _conversation_allowed(row: sqlite3.Row, actor: ContextPrincipal) -> bool:
        if row["tenant_id"] != actor.tenant_id:
            return False
        if row["scope"] == ContextScope.USER.value:
            return row["owner_id"] == actor.user_id
        return row["project_id"] in actor.project_ids

    def _conversation_row(
        self, actor: ContextPrincipal, conversation_id: str
    ) -> sqlite3.Row | None:
        self._id(conversation_id, "conversation_id")
        row = self._db.execute(
            "SELECT * FROM context_conversations "
            "WHERE tenant_id=? AND conversation_id=?",
            (actor.tenant_id, conversation_id),
        ).fetchone()
        if row is None or not self._conversation_allowed(row, actor):
            return None
        return row

    @staticmethod
    def _source_allowed(row: sqlite3.Row, actor: ContextPrincipal) -> bool:
        if row["tenant_id"] != actor.tenant_id:
            return False
        if row["scope"] == ContextScope.USER.value:
            return row["owner_id"] == actor.user_id
        return row["project_id"] in actor.project_ids

    def _next_sequence(self, tenant_id: str, conversation_id: str) -> int:
        row = self._db.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM context_entries "
            "WHERE tenant_id=? AND conversation_id=?",
            (tenant_id, conversation_id),
        ).fetchone()
        return int(row[0])

    def create_conversation(
        self,
        actor: ContextPrincipal,
        project_id: str,
        scope: ContextScope,
    ) -> ConversationRecord:
        if not isinstance(scope, ContextScope):
            raise ValueError("Unsupported conversation scope.")
        self._project_member(actor, project_id)
        conversation_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._transaction():
            self._db.execute(
                "INSERT INTO context_conversations VALUES (?, ?, ?, ?, ?, ?)",
                (
                    actor.tenant_id,
                    conversation_id,
                    project_id,
                    actor.user_id,
                    scope.value,
                    created_at,
                ),
            )
        return ConversationRecord(
            conversation_id,
            actor.tenant_id,
            project_id,
            actor.user_id,
            scope,
            created_at,
        )

    def get_conversation(
        self, actor: ContextPrincipal, conversation_id: str
    ) -> ConversationRecord | None:
        with self._lock:
            row = self._conversation_row(actor, conversation_id)
            if row is None:
                return None
            return ConversationRecord(
                row["conversation_id"],
                row["tenant_id"],
                row["project_id"],
                row["owner_id"],
                ContextScope(row["scope"]),
                row["created_at"],
            )

    def add_source(
        self,
        actor: ContextPrincipal,
        *,
        project_id: str,
        revision: str,
        role: ChatRole,
        trust: ContextTrust,
        content: str,
        scope: ContextScope = ContextScope.USER,
        source_id: str | None = None,
    ) -> ContextSourceRef:
        if not isinstance(scope, ContextScope):
            raise ValueError("Unsupported context source scope.")
        self._project_member(actor, project_id)
        source_id = str(uuid4()) if source_id is None else source_id
        self._id(source_id, "source_id")
        self._id(revision, "revision")
        if len(content) > MAX_CONTEXT_SOURCE_CHARS:
            raise ValueError("Context source exceeds the offline size limit.")
        # Enforce the same role/trust rules used by candidate preparation.
        ContextSegment(source_id, revision, role, content, trust)
        if trust is ContextTrust.POLICY:
            raise ValueError("Policy is server configuration, not a content source.")
        created_at = datetime.now(UTC).isoformat()
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._transaction():
            existing = self._db.execute(
                "SELECT * FROM context_sources WHERE tenant_id=? AND source_id=? "
                "AND revision=?",
                (actor.tenant_id, source_id, revision),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["project_id"] == project_id
                    and existing["owner_id"] == actor.user_id
                    and existing["scope"] == scope.value
                    and existing["role"] == role.value
                    and existing["trust"] == trust.value
                    and existing["content_sha256"] == digest
                    and existing["content"] == content
                )
                if not same:
                    raise ContextConflict("Context source revision is immutable.")
                return ContextSourceRef(source_id, revision, required=False)
            self._db.execute(
                "INSERT INTO context_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    actor.tenant_id,
                    source_id,
                    revision,
                    project_id,
                    actor.user_id,
                    scope.value,
                    role.value,
                    trust.value,
                    content,
                    digest,
                    created_at,
                ),
            )
        return ContextSourceRef(source_id, revision, required=False)

    def append_message(
        self,
        actor: ContextPrincipal,
        conversation_id: str,
        role: ChatRole,
        content: str,
    ) -> ContextSourceRef:
        if role not in (ChatRole.USER, ChatRole.ASSISTANT):
            raise ValueError("Conversation messages must be user or assistant turns.")
        trust = (
            ContextTrust.USER
            if role is ChatRole.USER
            else ContextTrust.ASSISTANT_HISTORY
        )
        source_id = str(uuid4())
        revision = "1"
        source = ContextSegment(source_id, revision, role, content, trust)
        if len(source.content) > MAX_CONTEXT_SOURCE_CHARS:
            raise ValueError("Conversation message exceeds the offline size limit.")
        created_at = datetime.now(UTC).isoformat()
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._transaction():
            conversation = self._conversation_row(actor, conversation_id)
            if conversation is None:
                raise ContextAccessDenied("Context is not accessible.")
            self._db.execute(
                "INSERT INTO context_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    actor.tenant_id,
                    source_id,
                    revision,
                    conversation["project_id"],
                    actor.user_id,
                    conversation["scope"],
                    role.value,
                    trust.value,
                    content,
                    digest,
                    created_at,
                ),
            )
            sequence = self._next_sequence(actor.tenant_id, conversation_id)
            self._db.execute(
                "INSERT INTO context_entries VALUES (?, ?, ?, ?, ?, ?)",
                (
                    actor.tenant_id,
                    conversation_id,
                    sequence,
                    source_id,
                    revision,
                    created_at,
                ),
            )
        return ContextSourceRef(source_id, revision, required=False)

    def attach_source(
        self,
        actor: ContextPrincipal,
        conversation_id: str,
        source_ref: ContextSourceRef,
    ) -> None:
        with self._transaction():
            conversation = self._conversation_row(actor, conversation_id)
            if conversation is None:
                raise ContextAccessDenied("Context is not accessible.")
            source = self._db.execute(
                "SELECT tenant_id, source_id, revision, project_id, owner_id, scope "
                "FROM context_sources WHERE tenant_id=? AND source_id=? AND revision=?",
                (actor.tenant_id, source_ref.source_id, source_ref.revision),
            ).fetchone()
            if (
                source is None
                or source["project_id"] != conversation["project_id"]
                or not self._source_allowed(source, actor)
                or (
                    conversation["scope"] == ContextScope.PROJECT.value
                    and source["scope"] != ContextScope.PROJECT.value
                )
            ):
                raise ContextAccessDenied("Context is not accessible.")
            created_at = datetime.now(UTC).isoformat()
            sequence = self._next_sequence(actor.tenant_id, conversation_id)
            try:
                self._db.execute(
                    "INSERT INTO context_entries VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        actor.tenant_id,
                        conversation_id,
                        sequence,
                        source_ref.source_id,
                        source_ref.revision,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ContextConflict(
                    "Source is already attached to conversation."
                ) from exc

    @staticmethod
    def _validate_source_integrity(row: sqlite3.Row) -> None:
        digest = hashlib.sha256(row["content"].encode("utf-8")).hexdigest()
        if digest != row["content_sha256"]:
            raise ContextIntegrityError("Stored context source failed integrity check.")

    @staticmethod
    def _as_segment(
        row: sqlite3.Row, *, required: bool, priority: int
    ) -> ContextSegment:
        SQLiteContextStore._validate_source_integrity(row)
        return ContextSegment(
            source_id=row["source_id"],
            source_revision=row["revision"],
            role=ChatRole(row["role"]),
            content=row["content"],
            trust=ContextTrust(row["trust"]),
            required=required,
            priority=priority,
        )

    def resolve_sources(
        self,
        actor: ContextPrincipal,
        conversation_id: str,
        refs: Sequence[ContextSourceRef],
    ) -> tuple[ContextSegment, ...]:
        """Authorize every ref before reading any selected source content."""
        with self._lock:
            conversation = self._conversation_row(actor, conversation_id)
            if conversation is None:
                raise ContextAccessDenied("Context is not accessible.")
            authorized: list[tuple[ContextSourceRef, sqlite3.Row]] = []
            for ref in refs:
                metadata = self._db.execute(
                    "SELECT tenant_id, source_id, revision, project_id, owner_id, "
                    "scope FROM context_sources WHERE tenant_id=? AND source_id=? "
                    "AND revision=?",
                    (actor.tenant_id, ref.source_id, ref.revision),
                ).fetchone()
                if (
                    metadata is None
                    or metadata["project_id"] != conversation["project_id"]
                    or not self._source_allowed(metadata, actor)
                    or (
                        conversation["scope"] == ContextScope.PROJECT.value
                        and metadata["scope"] != ContextScope.PROJECT.value
                    )
                ):
                    raise ContextAccessDenied("Context is not accessible.")
                authorized.append((ref, metadata))

            segments: list[ContextSegment] = []
            for ref, _ in authorized:
                row = self._db.execute(
                    "SELECT * FROM context_sources WHERE tenant_id=? AND source_id=? "
                    "AND revision=?",
                    (actor.tenant_id, ref.source_id, ref.revision),
                ).fetchone()
                if row is None:
                    raise ContextAccessDenied("Context is not accessible.")
                segments.append(
                    self._as_segment(row, required=ref.required, priority=ref.priority)
                )
            return tuple(segments)

    def recent_messages(
        self,
        actor: ContextPrincipal,
        conversation_id: str,
        *,
        limit: int,
        priority: int,
    ) -> tuple[ContextSegment, ...]:
        if type(limit) is not int or not 0 <= limit <= 100:
            raise ValueError("Recent message limit must be between 0 and 100.")
        with self._lock:
            conversation = self._conversation_row(actor, conversation_id)
            if conversation is None:
                raise ContextAccessDenied("Context is not accessible.")
            if limit == 0:
                return ()
            entries = self._db.execute(
                "SELECT s.tenant_id, s.source_id, s.revision, s.project_id, "
                "s.owner_id, s.scope "
                "FROM context_entries e JOIN context_sources s ON "
                "s.tenant_id=e.tenant_id AND s.source_id=e.source_id "
                "AND s.revision=e.source_revision WHERE e.tenant_id=? "
                "AND e.conversation_id=? ORDER BY e.sequence DESC LIMIT ?",
                (actor.tenant_id, conversation_id, limit),
            ).fetchall()
            if any(
                row["project_id"] != conversation["project_id"]
                or not self._source_allowed(row, actor)
                or (
                    conversation["scope"] == ContextScope.PROJECT.value
                    and row["scope"] != ContextScope.PROJECT.value
                )
                for row in entries
            ):
                raise ContextAccessDenied("Context is not accessible.")
            segments: list[ContextSegment] = []
            for entry in reversed(entries):
                row = self._db.execute(
                    "SELECT * FROM context_sources WHERE tenant_id=? AND source_id=? "
                    "AND revision=?",
                    (actor.tenant_id, entry["source_id"], entry["revision"]),
                ).fetchone()
                if row is None:
                    raise ContextAccessDenied("Context is not accessible.")
                segments.append(
                    self._as_segment(row, required=False, priority=priority)
                )
            return tuple(segments)
