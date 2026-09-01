from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class QuotaPolicy:
    requests_per_minute: int
    concurrent_requests: int
    tokens_per_minute: int

    def __post_init__(self) -> None:
        if (
            min(
                self.requests_per_minute,
                self.concurrent_requests,
                self.tokens_per_minute,
            )
            < 1
        ):
            raise ValueError("Quota limits must be positive.")


@dataclass(slots=True)
class _TenantUsage:
    window_started: float
    requests: int = 0
    tokens: int = 0
    concurrent: int = 0


class AdmissionController:
    """Single-process admission implementation behind a replaceable boundary."""

    def __init__(self, policies: dict[str, QuotaPolicy]) -> None:
        self._policies = policies
        self._usage: dict[str, _TenantUsage] = {}
        self._lock = Lock()

    def admit(
        self, tenant_id: str, estimated_tokens: int, now: float | None = None
    ) -> bool:
        with self._lock:
            policy = self._policies.get(tenant_id)
            if policy is None or estimated_tokens < 0:
                return False
            current = time.monotonic() if now is None else now
            usage = self._usage.setdefault(tenant_id, _TenantUsage(current))
            if current - usage.window_started >= 60:
                usage.window_started = current
                usage.requests = 0
                usage.tokens = 0
            if (
                usage.requests >= policy.requests_per_minute
                or usage.tokens + estimated_tokens > policy.tokens_per_minute
                or usage.concurrent >= policy.concurrent_requests
            ):
                return False
            usage.requests += 1
            usage.tokens += estimated_tokens
            usage.concurrent += 1
            return True

    def release(self, tenant_id: str) -> None:
        with self._lock:
            usage = self._usage.get(tenant_id)
            if usage is not None and usage.concurrent > 0:
                usage.concurrent -= 1
