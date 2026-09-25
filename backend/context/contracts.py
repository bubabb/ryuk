from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from backend.inference.contracts import ChatInput, ChatRole


def _identifier(value: str, field: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty without outer whitespace.")


class ContextTrust(StrEnum):
    POLICY = "policy"
    USER = "user"
    SOURCE = "source"
    TOOL_OUTPUT = "tool_output"
    GENERATED_SUMMARY = "generated_summary"
    ASSISTANT_HISTORY = "assistant_history"


class ContextScope(StrEnum):
    USER = "user"
    PROJECT = "project"


@dataclass(frozen=True, slots=True)
class ContextPrincipal:
    """Trusted identity/scope resolved by the application authorization layer."""

    tenant_id: str
    user_id: str
    project_ids: frozenset[str]

    def __post_init__(self) -> None:
        _identifier(self.tenant_id, "tenant_id")
        _identifier(self.user_id, "user_id")
        if not isinstance(self.project_ids, frozenset):
            raise ValueError("Project memberships must be an immutable set.")
        for project_id in self.project_ids:
            _identifier(project_id, "project_id")


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    conversation_id: str
    tenant_id: str
    project_id: str
    owner_id: str
    scope: ContextScope
    created_at: str


@dataclass(frozen=True, slots=True)
class ContextSourceRef:
    source_id: str
    revision: str
    required: bool
    priority: int = 0

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source_id")
        _identifier(self.revision, "revision")
        if type(self.required) is not bool or type(self.priority) is not int:
            raise ValueError("Source selection required and priority are invalid.")
        if type(self.required) is not bool or type(self.priority) is not int:
            raise ValueError("Source selection required and priority are invalid.")


@dataclass(frozen=True, slots=True)
class BuiltContext:
    conversation_id: str
    tenant_id: str
    project_id: str
    segments: tuple[ContextSegment, ...]


class TokenCountMethod(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"


class CountConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContextCapacityEvidence(StrEnum):
    ADVERTISED = "advertised"
    CONTRACT_TESTED = "contract_tested"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class ContextSegment:
    source_id: str
    source_revision: str
    role: ChatRole
    content: str
    trust: ContextTrust
    required: bool = False
    priority: int = 0

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source_id")
        _identifier(self.source_revision, "source_revision")
        if not isinstance(self.role, ChatRole) or not isinstance(
            self.trust, ContextTrust
        ):
            raise ValueError("Context role and trust must use Ryuk-owned enums.")
        if not self.content or not self.content.strip():
            raise ValueError("Context content must contain non-whitespace text.")
        if self.role is ChatRole.SYSTEM and self.trust is not ContextTrust.POLICY:
            raise ValueError("Only trusted policy content may use the system role.")
        if self.role is not ChatRole.SYSTEM and self.trust is ContextTrust.POLICY:
            raise ValueError("Trusted policy content must use the system role.")
        if self.trust is ContextTrust.POLICY and not self.required:
            raise ValueError("Policy context must be required and cannot be dropped.")
        if self.trust is ContextTrust.ASSISTANT_HISTORY:
            if self.role is not ChatRole.ASSISTANT:
                raise ValueError("Assistant history must use the assistant role.")
        elif self.trust is not ContextTrust.POLICY and self.role is not ChatRole.USER:
            raise ValueError("Non-policy context must use the user role.")
        if type(self.required) is not bool or type(self.priority) is not int:
            raise ValueError("Context required and priority fields have invalid types.")


@dataclass(frozen=True, slots=True)
class ContextPreparationProfile:
    """Candidate-specific limits and counting identity for one preparation."""

    profile_id: str
    profile_revision: str
    model_id: str
    model_revision: str | None
    max_context_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    capacity_evidence: ContextCapacityEvidence
    capacity_evidence_ref: str
    counter_id: str
    counter_revision: str
    template_id: str
    template_revision: str

    def __post_init__(self) -> None:
        for field in (
            "profile_id",
            "profile_revision",
            "model_id",
            "counter_id",
            "counter_revision",
            "template_id",
            "template_revision",
            "capacity_evidence_ref",
        ):
            _identifier(getattr(self, field), field)
        if self.model_revision is not None:
            _identifier(self.model_revision, "model_revision")
        if self.max_context_tokens < 1:
            raise ValueError("max_context_tokens must be positive.")
        if self.reserved_output_tokens < 1:
            raise ValueError("reserved_output_tokens must be positive.")
        if self.safety_margin_tokens < 0:
            raise ValueError("safety_margin_tokens cannot be negative.")
        if self.reserved_output_tokens + self.safety_margin_tokens >= (
            self.max_context_tokens
        ):
            raise ValueError("Output reserve and safety margin exhaust context.")


@dataclass(frozen=True, slots=True)
class TokenCount:
    tokens: int
    method: TokenCountMethod
    confidence: CountConfidence
    counter_id: str
    counter_revision: str
    template_id: str
    template_revision: str

    def __post_init__(self) -> None:
        if self.tokens < 0:
            raise ValueError("Token count cannot be negative.")
        for field in (
            "counter_id",
            "counter_revision",
            "template_id",
            "template_revision",
        ):
            _identifier(getattr(self, field), field)
        if self.method is TokenCountMethod.EXACT and (
            self.confidence is not CountConfidence.HIGH
        ):
            raise ValueError("Exact counts must report high confidence.")


class ContextTokenCounter(Protocol):
    """Counts the fully rendered candidate input, including template overhead."""

    def count(self, chat: ChatInput) -> TokenCount: ...


class ExclusionReason(StrEnum):
    DUPLICATE = "duplicate"
    OVER_BUDGET = "over_budget"


@dataclass(frozen=True, slots=True)
class ExcludedContextSource:
    source_id: str
    source_revision: str
    reason: ExclusionReason
    duplicate_of: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedContext:
    chat: ChatInput
    profile: ContextPreparationProfile
    input_tokens: int
    total_reserved_tokens: int
    count_method: TokenCountMethod
    count_confidence: CountConfidence
    included_source_ids: tuple[str, ...]
    included_source_revisions: tuple[tuple[str, str], ...]
    excluded_sources: tuple[ExcludedContextSource, ...]
    payload_sha256: str


@dataclass(frozen=True, slots=True)
class ContextOverflow(Exception):
    required_tokens: int
    available_input_tokens: int

    def __str__(self) -> str:
        return (
            f"Required context uses {self.required_tokens} tokens, but only "
            f"{self.available_input_tokens} input tokens are available."
        )
