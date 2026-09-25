from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from backend.context.contracts import (
    BuiltContext,
    ContextPrincipal,
    ContextSegment,
    ContextSourceRef,
    ContextTrust,
)
from backend.context.store import (
    ContextAccessDenied,
    ContextConflict,
    SQLiteContextStore,
)


class ContextPolicyUnavailable(RuntimeError):
    """No server-owned policy is configured for this tenant/project."""


class ContextBuilder:
    """Build an authorized, source-linked context before token fitting."""

    def __init__(
        self,
        store: SQLiteContextStore,
        trusted_policies: Mapping[tuple[str, str], Sequence[ContextSegment]],
        *,
        recent_message_priority: int = 50,
    ) -> None:
        self._store = store
        self._policies: dict[tuple[str, str], tuple[ContextSegment, ...]] = {}
        if type(recent_message_priority) is not int:
            raise ValueError("Recent message priority must be an integer.")
        self._recent_message_priority = recent_message_priority
        for scope, segments in trusted_policies.items():
            if (
                not isinstance(scope, tuple)
                or len(scope) != 2
                or any(not value or value != value.strip() for value in scope)
            ):
                raise ValueError(
                    "Trusted policy keys must be tenant/project identifiers."
                )
            policy = tuple(segments)
            if not policy or any(
                segment.trust is not ContextTrust.POLICY or not segment.required
                for segment in policy
            ):
                raise ValueError(
                    "Configured context policy must be non-empty and required."
                )
            ids = [segment.source_id for segment in policy]
            if len(ids) != len(set(ids)):
                raise ValueError("Configured policy source identifiers must be unique.")
            self._policies[scope] = policy

    @staticmethod
    def _append_unique(
        destination: list[ContextSegment],
        index_by_id: dict[str, int],
        segment: ContextSegment,
    ) -> None:
        index = index_by_id.get(segment.source_id)
        if index is None:
            index_by_id[segment.source_id] = len(destination)
            destination.append(segment)
            return
        current = destination[index]
        if (
            current.source_revision != segment.source_revision
            or current.role is not segment.role
            or current.content != segment.content
            or current.trust is not segment.trust
        ):
            raise ContextConflict("Selected context source identifiers conflict.")
        destination[index] = replace(
            current,
            required=current.required or segment.required,
            priority=max(current.priority, segment.priority),
        )

    def build(
        self,
        actor: ContextPrincipal,
        conversation_id: str,
        sources: Sequence[ContextSourceRef],
        *,
        recent_message_limit: int = 12,
    ) -> BuiltContext:
        """Authorize the conversation and every source before returning text.

        `actor` must be created from the authenticated principal and trusted
        project-membership data. Missing or foreign conversations/sources fail
        closed with the same access error; unauthorized content is never skipped
        silently to create a partial prompt.
        """

        conversation = self._store.get_conversation(actor, conversation_id)
        if conversation is None:
            raise ContextAccessDenied("Context is not accessible.")
        if conversation.project_id not in actor.project_ids:
            raise ContextAccessDenied("Context is not accessible.")
        policy = self._policies.get((conversation.tenant_id, conversation.project_id))
        if policy is None:
            raise ContextPolicyUnavailable(
                "No trusted context policy is configured for this scope."
            )
        if not sources or not any(source.required for source in sources):
            raise ValueError(
                "At least one required objective/criteria source is required."
            )

        resolved = self._store.resolve_sources(actor, conversation_id, sources)
        recent = self._store.recent_messages(
            actor,
            conversation_id,
            limit=recent_message_limit,
            priority=self._recent_message_priority,
        )

        ordered: list[ContextSegment] = []
        index_by_id: dict[str, int] = {}
        for segment in policy:
            self._append_unique(ordered, index_by_id, segment)
        for segment in resolved:
            if segment.required:
                self._append_unique(ordered, index_by_id, segment)
        for segment in recent:
            self._append_unique(ordered, index_by_id, segment)
        for segment in resolved:
            if not segment.required:
                self._append_unique(ordered, index_by_id, segment)
        return BuiltContext(
            conversation_id=conversation_id,
            tenant_id=conversation.tenant_id,
            project_id=conversation.project_id,
            segments=tuple(ordered),
        )
