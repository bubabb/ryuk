from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from backend.context.contracts import (
    ContextOverflow,
    ContextPreparationProfile,
    ContextSegment,
    ContextTokenCounter,
    ExcludedContextSource,
    ExclusionReason,
    PreparedContext,
    TokenCount,
)
from backend.inference.contracts import ChatInput, ChatMessage


def _validate_counter(count: TokenCount, profile: ContextPreparationProfile) -> None:
    expected = (
        profile.counter_id,
        profile.counter_revision,
        profile.template_id,
        profile.template_revision,
    )
    actual = (
        count.counter_id,
        count.counter_revision,
        count.template_id,
        count.template_revision,
    )
    if actual != expected:
        raise ValueError("Token counter does not match the candidate profile.")


def _deduplicate_optional(
    segments: Sequence[ContextSegment],
) -> tuple[list[ContextSegment], list[ExcludedContextSource]]:
    optional = [segment for segment in segments if not segment.required]
    chosen: dict[tuple[str, str, str], ContextSegment] = {}
    for segment in optional:
        key = (segment.role.value, segment.trust.value, segment.content)
        current = chosen.get(key)
        if current is None or segment.priority > current.priority:
            chosen[key] = segment

    kept_optional = set(chosen.values())
    result = [
        segment for segment in segments if segment.required or segment in kept_optional
    ]
    exclusions: list[ExcludedContextSource] = []
    for segment in optional:
        if segment in kept_optional:
            continue
        winner = chosen[(segment.role.value, segment.trust.value, segment.content)]
        exclusions.append(
            ExcludedContextSource(
                source_id=segment.source_id,
                source_revision=segment.source_revision,
                reason=ExclusionReason.DUPLICATE,
                duplicate_of=winner.source_id,
            )
        )
    return result, exclusions


def _chat(segments: Sequence[ContextSegment]) -> ChatInput:
    return ChatInput(
        messages=tuple(
            ChatMessage(segment.role, segment.content) for segment in segments
        )
    )


def _payload_digest(chat: ChatInput) -> str:
    payload = [
        {"role": message.role.value, "content": message.content}
        for message in chat.messages
    ]
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prepare_context(
    segments: Sequence[ContextSegment],
    profile: ContextPreparationProfile,
    counter: ContextTokenCounter,
) -> PreparedContext:
    """Fit source-linked messages to one candidate; fallback must call again.

    Required content is never truncated or dropped. Optional duplicate sources
    are removed deterministically, followed by lowest-priority optional sources
    (later source first on a tie) until the candidate's input/output/margin bound
    fits. Candidate counters must include their own chat template overhead.
    """

    if not segments:
        raise ValueError("At least one context segment is required.")
    ids = [segment.source_id for segment in segments]
    if len(ids) != len(set(ids)):
        raise ValueError("Context source identifiers must be unique.")
    if not any(segment.required for segment in segments):
        raise ValueError("At least one required context segment is required.")

    available = (
        profile.max_context_tokens
        - profile.reserved_output_tokens
        - profile.safety_margin_tokens
    )
    kept, excluded = _deduplicate_optional(segments)
    counted = counter.count(_chat(kept))
    _validate_counter(counted, profile)
    if counted.tokens > available:
        optional = [
            (index, segment)
            for index, segment in enumerate(kept)
            if not segment.required
        ]
        drop_order = sorted(optional, key=lambda pair: (pair[1].priority, -pair[0]))
        dropped: set[str] = set()
        for _, segment in drop_order:
            kept = [item for item in kept if item.source_id != segment.source_id]
            dropped.add(segment.source_id)
            counted = counter.count(_chat(kept))
            _validate_counter(counted, profile)
            if counted.tokens <= available:
                break
        excluded.extend(
            ExcludedContextSource(
                source_id=segment.source_id,
                source_revision=segment.source_revision,
                reason=ExclusionReason.OVER_BUDGET,
            )
            for _, segment in drop_order
            if segment.source_id in dropped
        )

    if counted.tokens > available:
        raise ContextOverflow(counted.tokens, available)

    chat = _chat(kept)
    return PreparedContext(
        chat=chat,
        profile=profile,
        input_tokens=counted.tokens,
        total_reserved_tokens=(
            counted.tokens
            + profile.reserved_output_tokens
            + profile.safety_margin_tokens
        ),
        count_method=counted.method,
        count_confidence=counted.confidence,
        included_source_ids=tuple(segment.source_id for segment in kept),
        included_source_revisions=tuple(
            (segment.source_id, segment.source_revision) for segment in kept
        ),
        excluded_sources=tuple(excluded),
        payload_sha256=_payload_digest(chat),
    )
