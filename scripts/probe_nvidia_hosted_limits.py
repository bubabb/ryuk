"""Measure bounded DeepSeek input/output safe points without retaining content."""

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
MODEL = "deepseek-ai/deepseek-v4.1-flash"
INPUT_PADDING_WORDS = 1024
OUTPUT_WORDS = 64
INPUT_PROMPT = (
    "Read the synthetic padding, then reply with exactly ready. Padding: "
    + "alpha " * INPUT_PADDING_WORDS
)
OUTPUT_PROMPT = (
    f"Return the word ready exactly {OUTPUT_WORDS} times, separated by single "
    "spaces, and return nothing else."
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _count(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def sanitize_limit_observation(
    *,
    case: str,
    status_code: int | None,
    elapsed_ms: float,
    payload: object = None,
    failure_type: str | None = None,
) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    choices = body.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else {}
    choice = choice if isinstance(choice, dict) else {}
    message = choice.get("message")
    message = message if isinstance(message, dict) else {}
    content = message.get("content")
    words = content.split() if isinstance(content, str) else []
    response_model = body.get("model")
    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    if case == "larger_input":
        contract_valid = isinstance(content, str) and content.strip() == "ready"
    elif case == "longer_output":
        contract_valid = words == ["ready"] * OUTPUT_WORDS
    else:
        raise ValueError("unknown limit case")
    return {
        "case": case,
        "observed_at": _timestamp(),
        "status_code": status_code,
        "elapsed_ms": round(elapsed_ms, 3),
        "response_model": response_model if isinstance(response_model, str) else None,
        "identity_matches": response_model == MODEL,
        "finish_reason": (
            choice.get("finish_reason")
            if isinstance(choice.get("finish_reason"), str)
            else None
        ),
        "output_present": isinstance(content, str) and bool(content),
        "output_characters": len(content) if isinstance(content, str) else None,
        "output_words": len(words) if isinstance(content, str) else None,
        "contract_valid": contract_valid,
        "usage": {
            "prompt_tokens": _count(usage.get("prompt_tokens")),
            "completion_tokens": _count(usage.get("completion_tokens")),
            "total_tokens": _count(usage.get("total_tokens")),
        },
        "failure_type": failure_type,
    }


async def _probe_case(client: httpx.AsyncClient, *, case: str) -> dict[str, Any]:
    if case == "larger_input":
        prompt = INPUT_PROMPT
        max_tokens = 64
    elif case == "longer_output":
        prompt = OUTPUT_PROMPT
        max_tokens = 256
    else:
        raise ValueError("unknown limit case")
    started = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/v1/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": max_tokens,
                "stream": False,
            },
        )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return sanitize_limit_observation(
            case=case,
            status_code=response.status_code,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            payload=payload,
            failure_type=(
                None if response.is_success else f"HTTP_{response.status_code}"
            ),
        )
    except httpx.HTTPError as exc:
        return sanitize_limit_observation(
            case=case,
            status_code=None,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            failure_type=type(exc).__name__,
        )


async def collect_limit_evidence(
    api_key: str, *, timeout_seconds: float = 300.0
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "probe": "p2b-003-deepseek-safe-limits",
        "base_url": BASE_URL,
        "model": MODEL,
        "started_at": _timestamp(),
        "settings": {
            "timeout_seconds": timeout_seconds,
            "temperature": 0,
            "stream": False,
            "synthetic_public_input": True,
            "requests_concurrent": True,
            "larger_input": {
                "prompt_characters": len(INPUT_PROMPT),
                "padding_words": INPUT_PADDING_WORDS,
                "max_tokens": 64,
            },
            "longer_output": {
                "prompt_characters": len(OUTPUT_PROMPT),
                "required_output_words": OUTPUT_WORDS,
                "max_tokens": 256,
            },
        },
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    timeout = httpx.Timeout(timeout_seconds, connect=10.0, pool=10.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        evidence["observations"] = await asyncio.gather(
            _probe_case(client, case="larger_input"),
            _probe_case(client, case="longer_output"),
        )
    evidence["completed_at"] = _timestamp()
    return evidence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is not set")
    evidence = asyncio.run(
        collect_limit_evidence(api_key, timeout_seconds=args.timeout_seconds)
    )
    with open(args.output, "x", encoding="utf-8") as output:
        json.dump(evidence, output, indent=2, sort_keys=True)
        output.write("\n")
    return 0 if all(item["contract_valid"] for item in evidence["observations"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
