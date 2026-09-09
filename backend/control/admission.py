from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any


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
        self._policies = dict(policies)
        self._usage: dict[str, _TenantUsage] = {}
        self._lock = Lock()

    @property
    def configured_tenants(self) -> frozenset[str]:
        """Return an immutable view used by startup configuration validation."""
        return frozenset(self._policies)

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


_ADMIT_SCRIPT = """
local now = redis.call('TIME')
local minute = math.floor(tonumber(now[1]) / 60)
local stored = tonumber(redis.call('HGET', KEYS[1], 'minute') or '-1')
if stored ~= minute then
  redis.call('HSET', KEYS[1], 'minute', minute, 'requests', 0, 'tokens', 0)
end
local requests = tonumber(redis.call('HGET', KEYS[1], 'requests') or '0')
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens') or '0')
local concurrent = tonumber(redis.call('HGET', KEYS[1], 'concurrent') or '0')
if requests >= tonumber(ARGV[1]) or
   tokens + tonumber(ARGV[4]) > tonumber(ARGV[3]) or
   concurrent >= tonumber(ARGV[2]) then
  return 0
end
redis.call('HINCRBY', KEYS[1], 'requests', 1)
redis.call('HINCRBY', KEYS[1], 'tokens', ARGV[4])
redis.call('HINCRBY', KEYS[1], 'concurrent', 1)
-- Never expire an active permit: doing so would silently reopen capacity for a
-- request lasting longer than the idle retention window.
redis.call('PERSIST', KEYS[1])
return 1
"""

_RELEASE_SCRIPT = """
local concurrent = tonumber(redis.call('HGET', KEYS[1], 'concurrent') or '0')
if concurrent > 0 then
  local remaining = redis.call('HINCRBY', KEYS[1], 'concurrent', -1)
  if remaining == 0 then
    redis.call('EXPIRE', KEYS[1], 180)
  end
end
return 1
"""


class RedisAdmissionController:
    """Distributed, atomic quota coordination using one Redis key per tenant."""

    def __init__(
        self,
        policies: Mapping[str, QuotaPolicy],
        *,
        redis_url: str | None = None,
        client: Any | None = None,
        key_prefix: str = "ryuk:admission:v1",
    ) -> None:
        if client is None:
            if not redis_url:
                raise ValueError("redis_url is required without an injected client.")
            from redis import Redis

            client = Redis.from_url(redis_url, decode_responses=True)
        self._client = client
        self._policies = dict(policies)
        self._key_prefix = key_prefix

    @property
    def configured_tenants(self) -> frozenset[str]:
        return frozenset(self._policies)

    def admit(
        self, tenant_id: str, estimated_tokens: int, now: float | None = None
    ) -> bool:
        del now
        policy = self._policies.get(tenant_id)
        if policy is None or estimated_tokens < 0:
            return False
        try:
            result = self._client.eval(
                _ADMIT_SCRIPT,
                1,
                self._key(tenant_id),
                policy.requests_per_minute,
                policy.concurrent_requests,
                policy.tokens_per_minute,
                estimated_tokens,
            )
        except Exception:
            return False
        return result == 1

    def release(self, tenant_id: str) -> None:
        try:
            self._client.eval(_RELEASE_SCRIPT, 1, self._key(tenant_id))
        except Exception:
            # Release is idempotent. An operations reconciliation must clear a
            # leaked permit after a process failure; never reopen active capacity
            # merely because an arbitrary TTL elapsed.
            return

    def health(self) -> dict[str, object]:
        try:
            ready = bool(self._client.ping())
        except Exception:
            ready = False
        return {"ready": ready, "distributed": True}

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()

    def _key(self, tenant_id: str) -> str:
        return f"{self._key_prefix}:{tenant_id}"
