"""Collect bounded, content-free identity evidence from NVIDIA hosted routes.

This probe is intentionally narrower than a general integration test. It never
prints prompts, generated content, credentials, headers, or response bodies.
"""

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


def _usage_presence(payload: object) -> dict[str, bool]:
    usage = payload if isinstance(payload, dict) else {}
    return {
        "usage_object": isinstance(payload, dict),
        "prompt_tokens": isinstance(usage.get("prompt_tokens"), int),
        "completion_tokens": isinstance(usage.get("completion_tokens"), int),
        "total_tokens": isinstance(usage.get("total_tokens"), int),
    }


def sanitize_generation_observation(
    *,
    model: str,
    status_code: int | None,
    elapsed_ms: float,
    payload: object = None,
    failure_type: str | None = None,
) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    choices = body.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else None
    finish_reason = (
        first_choice.get("finish_reason") if isinstance(first_choice, dict) else None
    )
    response_model = body.get("model")
    return {
        "configured_model": model,
        "observed_at": _timestamp(),
        "status_code": status_code,
        "elapsed_ms": round(elapsed_ms, 3),
        "response_model": response_model if isinstance(response_model, str) else None,
        "identity_matches": response_model == model,
        "response_id_present": isinstance(body.get("id"), str),
        "choices_present": isinstance(choices, list) and bool(choices),
        "finish_reason": finish_reason if isinstance(finish_reason, str) else None,
        "usage_fields_present": _usage_presence(body.get("usage")),
        "failure_type": failure_type,
    }


async def collect_identity_evidence(
    api_key: str, *, timeout_seconds: float = 120.0
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}"}
    timeout = httpx.Timeout(timeout_seconds, connect=10.0, pool=10.0)
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "probe": "p2b-002-hosted-identity",
        "base_url": BASE_URL,
        "started_at": _timestamp(),
        "request_settings": {
            "temperature": 0,
            "max_tokens": 8,
            "stream": False,
            "synthetic_public_input": True,
        },
        "catalog": {},
        "generation": [],
    }
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        catalog_started = time.perf_counter()
        try:
            response = await client.get(f"{BASE_URL}/v1/models")
            elapsed_ms = (time.perf_counter() - catalog_started) * 1000
            payload = response.json() if response.is_success else None
            rows = payload.get("data") if isinstance(payload, dict) else None
            ids = {
                item.get("id")
                for item in rows or ()
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            evidence["catalog"] = {
                "observed_at": _timestamp(),
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed_ms, 3),
                "approved_models_present": {
                    model: model in ids for model in APPROVED_MODELS
                },
                "failure_type": None,
            }
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            evidence["catalog"] = {
                "observed_at": _timestamp(),
                "status_code": None,
                "elapsed_ms": round((time.perf_counter() - catalog_started) * 1000, 3),
                "approved_models_present": {model: False for model in APPROVED_MODELS},
                "failure_type": type(exc).__name__,
            }
            evidence["completed_at"] = _timestamp()
            return evidence

        for model in APPROVED_MODELS:
            started = time.perf_counter()
            try:
                response = await client.post(
                    f"{BASE_URL}/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": PROMPT}],
                        "temperature": 0,
                        "max_tokens": 8,
                        "stream": False,
                    },
                )
                elapsed_ms = (time.perf_counter() - started) * 1000
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                failure = (
                    None if response.is_success else f"HTTP_{response.status_code}"
                )
                evidence["generation"].append(
                    sanitize_generation_observation(
                        model=model,
                        status_code=response.status_code,
                        elapsed_ms=elapsed_ms,
                        payload=payload,
                        failure_type=failure,
                    )
                )
            except httpx.HTTPError as exc:
                evidence["generation"].append(
                    sanitize_generation_observation(
                        model=model,
                        status_code=None,
                        elapsed_ms=(time.perf_counter() - started) * 1000,
                        failure_type=type(exc).__name__,
                    )
                )
    evidence["completed_at"] = _timestamp()
    return evidence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Write sanitized JSON to this path.")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is not set")
    evidence = asyncio.run(
        collect_identity_evidence(api_key, timeout_seconds=args.timeout_seconds)
    )
    rendered = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "x", encoding="utf-8") as output:
            output.write(rendered)
    else:
        print(rendered, end="")
    observations = evidence["generation"]
    passed = (
        all(evidence["catalog"]["approved_models_present"].values())
        and len(observations) == len(APPROVED_MODELS)
        and all(
            item["status_code"] == 200 and item["identity_matches"]
            for item in observations
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
