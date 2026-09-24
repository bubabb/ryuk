from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class WorkflowBudget:
    """One mutable budget shared by a workflow and every router attempt."""

    deadline_seconds: float
    max_attempts: int
    max_output_tokens: int | None = None
    _started: float = field(default_factory=time.monotonic, init=False)
    _attempts: int = field(default=0, init=False)
    _output_tokens: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.max_output_tokens is not None and self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive when provided")

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def output_tokens(self) -> int:
        return self._output_tokens

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_seconds - (time.monotonic() - self._started))

    def reserve_attempt(self) -> bool:
        """Reserve one attempt; retries cannot create a fresh nested budget."""
        if self.remaining_seconds() <= 0 or self._attempts >= self.max_attempts:
            return False
        self._attempts += 1
        return True

    def record_output_tokens(self, count: int | None) -> bool:
        if count is None:
            return True
        if count < 0:
            raise ValueError("output token count cannot be negative")
        if self.max_output_tokens is not None and (
            self._output_tokens + count > self.max_output_tokens
        ):
            return False
        self._output_tokens += count
        return True
