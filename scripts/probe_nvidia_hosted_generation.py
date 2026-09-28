"""Measure bounded NVIDIA hosted generation without retaining model content."""

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


def _count(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def sanitize_generation_measurement(
    *,
    model: str,
    status_code: int | None,
    elapsed_ms: float,
    payload: object = None,
    failure_type: str | None = None,
) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    choices = body.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get("message") if isinstance(choice, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    response_model = body.get("model")
    return {
        "configured_model": model,
        "observed_at": _timestamp(),
        "status_code": status_code,
        "elapsed_ms": round(elapsed_ms, 3),
        "response_model": response_model if isinstance(response_model, str) else None,
        "identity_matches": response_model == model,
        "finish_reason": (
            choice.get("finish_reason")
            if isinstance(choice, dict)
            and isinstance(choice.get("finish_reason"), str)
            else None
        ),
        "output_text_present": isinstance(content, str) and bool(content),
        "output_characters": len(content) if isinstance(content, str) else None,
        "usage": {
            "prompt_tokens": _count(usage.get("prompt_tokens")),
            "completion_tokens": _count(usage.get("completion_tokens")),
            "total_tokens": _count(usage.get("total_tokens")),
        },
        "failure_type": failure_type,
    }


async def _probe_model(
    client: httpx.AsyncClient, model: str, max_tokens: int
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": PROMPT}],
                "temperature": 0,
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return sanitize_generation_measurement(
            model=model,
            status_code=response.status_code,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            payload=payload,
            failure_type=(
                None if response.is_success else f"HTTP_{response.status_code}"
            ),
        )
    except httpx.HTTPError as exc:
        return sanitize_generation_measurement(
            model=model,
            status_code=None,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            failure_type=type(exc).__name__,
        )


async def collect_generation_evidence(
    api_key: str, *, max_tokens: int = 64, timeout_seconds: float = 300.0
) -> dict[str, Any]:
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "probe": "p2b-003-hosted-generation",
        "base_url": BASE_URL,
        "started_at": _timestamp(),
        "request_settings": {
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
            "prompt_characters": len(PROMPT),
            "synthetic_public_input": True,
            "requests_concurrent": True,
        },
        "generation": [],
    }
    timeout = httpx.Timeout(timeout_seconds, connect=10.0, pool=10.0)
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        evidence["generation"] = await asyncio.gather(
            *(_probe_model(client, model, max_tokens) for model in APPROVED_MODELS)
        )
    evidence["completed_at"] = _timestamp()
    return evidence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is not set")
    evidence = asyncio.run(
        collect_generation_evidence(
            api_key,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
        )
    )
    with open(args.output, "x", encoding="utf-8") as output:
        json.dump(evidence, output, indent=2, sort_keys=True)
        output.write("\n")
    passed = all(
        item["status_code"] == 200
        and item["identity_matches"]
        and item["output_text_present"]
        for item in evidence["generation"]
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
