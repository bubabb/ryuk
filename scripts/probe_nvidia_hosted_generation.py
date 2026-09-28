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
            if isinstance(choice, dict) and isinstance(choice.get("finish_reason"), str)
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
    client: httpx.AsyncClient,
    model: str,
    max_tokens: int,
    temperature: float,
    kimi_reasoning_effort: str | None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if model == "moonshotai/kimi-k3" and kimi_reasoning_effort is not None:
        request["reasoning_effort"] = kimi_reasoning_effort
    started = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json=request,
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
    api_key: str,
    *,
    models: tuple[str, ...] = APPROVED_MODELS,
    max_tokens: int = 64,
    timeout_seconds: float = 300.0,
    temperature: float = 0,
    kimi_reasoning_effort: str | None = None,
) -> dict[str, Any]:
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if not models or len(set(models)) != len(models):
        raise ValueError("models must be non-empty and unique")
    if any(model not in APPROVED_MODELS for model in models):
        raise ValueError("models must contain only approved model IDs")
    if not 0 <= temperature <= 1:
        raise ValueError("temperature must be between zero and one")
    if kimi_reasoning_effort not in {None, "low", "high", "max"}:
        raise ValueError("kimi_reasoning_effort must be low, high, max, or omitted")
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "probe": "p2b-003-hosted-generation",
        "base_url": BASE_URL,
        "started_at": _timestamp(),
        "request_settings": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "prompt_characters": len(PROMPT),
            "synthetic_public_input": True,
            "requests_concurrent": True,
            "models": list(models),
            "kimi_reasoning_effort": kimi_reasoning_effort,
        },
        "generation": [],
    }
    timeout = httpx.Timeout(timeout_seconds, connect=10.0, pool=10.0)
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        evidence["generation"] = await asyncio.gather(
            *(
                _probe_model(
                    client,
                    model,
                    max_tokens,
                    temperature,
                    kimi_reasoning_effort,
                )
                for model in models
            )
        )
    evidence["completed_at"] = _timestamp()
    return evidence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument(
        "--model", action="append", choices=APPROVED_MODELS, dest="models"
    )
    parser.add_argument("--kimi-reasoning-effort", choices=("low", "high", "max"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is not set")
    evidence = asyncio.run(
        collect_generation_evidence(
            api_key,
            models=tuple(args.models or APPROVED_MODELS),
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
            temperature=args.temperature,
            kimi_reasoning_effort=args.kimi_reasoning_effort,
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
