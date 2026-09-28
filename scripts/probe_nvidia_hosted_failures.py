"""Collect bounded, sanitized NVIDIA hosted failure-contract observations."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx

BASE_URL = "https://integrate.api.nvidia.com"
APPROVED_MODELS = (
    "moonshotai/kimi-k3",
    "deepseek-ai/deepseek-v4.1-flash",
)
PROMPT = "Reply with exactly the single word ready."


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def sanitize_error_shape(payload: object) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    error = body.get("error")
    error = error if isinstance(error, dict) else {}
    return {
        "error_object_present": bool(error),
        "error_type_present": isinstance(error.get("type"), str),
        "error_code_present": (
            isinstance(error.get("code"), str | int)
            and not isinstance(error.get("code"), bool)
        ),
    }


async def _malformed_request(client: httpx.AsyncClient, model: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": "intentionally-invalid-not-an-array",
                "temperature": 0,
                "max_tokens": 1,
                "stream": False,
            },
        )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return {
            "model": model,
            "observed_at": _timestamp(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "status_code": response.status_code,
            "rejected": 400 <= response.status_code < 500,
            "error_shape": sanitize_error_shape(payload),
            "failure_type": None,
        }
    except httpx.HTTPError as exc:
        return {
            "model": model,
            "observed_at": _timestamp(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "status_code": None,
            "rejected": False,
            "error_shape": sanitize_error_shape(None),
            "failure_type": type(exc).__name__,
        }


async def _open_stream(client: httpx.AsyncClient, model: str) -> int:
    async with client.stream(
        "POST",
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0,
            "max_tokens": 64,
            "stream": True,
        },
    ) as response:
        return response.status_code


async def _cancel_request(
    client: httpx.AsyncClient, model: str, cancellation_seconds: float
) -> dict[str, Any]:
    started = time.perf_counter()
    task = asyncio.create_task(_open_stream(client, model))
    status_code: int | None = None
    failure_type: str | None = None
    client_cancelled = False
    try:
        status_code = await asyncio.wait_for(task, timeout=cancellation_seconds)
    except TimeoutError:
        client_cancelled = True
    except httpx.HTTPError as exc:
        failure_type = type(exc).__name__
    return {
        "model": model,
        "observed_at": _timestamp(),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "cancellation_deadline_seconds": cancellation_seconds,
        "client_cancelled": client_cancelled,
        "client_stream_closed": client_cancelled or status_code is not None,
        "response_headers_observed": status_code is not None,
        "status_code": status_code,
        "provider_cancellation_acknowledged": None,
        "provider_execution_stopped": None,
        "late_result_observed": None,
        "failure_type": failure_type,
    }


async def collect_failure_evidence(
    api_key: str,
    *,
    cancellation_seconds: float = 2.0,
    request_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    if cancellation_seconds <= 0:
        raise ValueError("cancellation_seconds must be positive")
    if request_timeout_seconds <= cancellation_seconds:
        raise ValueError("request_timeout_seconds must exceed cancellation_seconds")
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "probe": "p2b-004-hosted-failures",
        "base_url": BASE_URL,
        "started_at": _timestamp(),
        "settings": {
            "cancellation_seconds": cancellation_seconds,
            "request_timeout_seconds": request_timeout_seconds,
            "synthetic_public_input": True,
            "overload_induced": False,
        },
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    timeout = httpx.Timeout(request_timeout_seconds, connect=10.0, pool=10.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        evidence["malformed_requests"] = await asyncio.gather(
            *(_malformed_request(client, model) for model in APPROVED_MODELS)
        )
        evidence["client_cancellation"] = await asyncio.gather(
            *(
                _cancel_request(client, model, cancellation_seconds)
                for model in APPROVED_MODELS
            )
        )
    evidence["completed_at"] = _timestamp()
    return evidence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--cancellation-seconds", type=float, default=2.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is not set")
    evidence = asyncio.run(
        collect_failure_evidence(
            api_key,
            cancellation_seconds=args.cancellation_seconds,
            request_timeout_seconds=args.request_timeout_seconds,
        )
    )
    with open(args.output, "x", encoding="utf-8") as output:
        json.dump(evidence, output, indent=2, sort_keys=True)
        output.write("\n")
    malformed_passed = all(item["rejected"] for item in evidence["malformed_requests"])
    cancellation_observed = all(
        item["client_stream_closed"] for item in evidence["client_cancellation"]
    )
    return 0 if malformed_passed and cancellation_observed else 1


if __name__ == "__main__":
    raise SystemExit(main())
