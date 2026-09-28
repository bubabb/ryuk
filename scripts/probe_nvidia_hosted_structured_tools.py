"""Probe hosted structured-output and tool-call contracts without executing tools."""

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
TOOL_NAME = "lookup_status"
STRUCTURED_PROMPT = 'Return exactly this JSON object: {"status":"ready"}'
TOOL_PROMPT = "Call lookup_status once with item set to ryuk."


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _count(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _response_parts(payload: object) -> tuple[dict[str, Any], dict[str, Any]]:
    body = payload if isinstance(payload, dict) else {}
    choices = body.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else {}
    choice = choice if isinstance(choice, dict) else {}
    message = choice.get("message")
    return body, message if isinstance(message, dict) else {}


def _base_observation(
    *,
    model: str,
    status_code: int | None,
    elapsed_ms: float,
    payload: object,
    failure_type: str | None,
) -> dict[str, Any]:
    body, _ = _response_parts(payload)
    response_model = body.get("model")
    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    error = body.get("error")
    error = error if isinstance(error, dict) else {}
    return {
        "model": model,
        "observed_at": _timestamp(),
        "elapsed_ms": round(elapsed_ms, 3),
        "status_code": status_code,
        "response_model": response_model if isinstance(response_model, str) else None,
        "identity_matches": response_model == model,
        "usage": {
            "prompt_tokens": _count(usage.get("prompt_tokens")),
            "completion_tokens": _count(usage.get("completion_tokens")),
            "total_tokens": _count(usage.get("total_tokens")),
        },
        "error_object_present": bool(error),
        "failure_type": failure_type,
    }


def sanitize_structured_observation(
    *,
    model: str,
    status_code: int | None,
    elapsed_ms: float,
    payload: object = None,
    failure_type: str | None = None,
) -> dict[str, Any]:
    observation = _base_observation(
        model=model,
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        payload=payload,
        failure_type=failure_type,
    )
    _, message = _response_parts(payload)
    content = message.get("content")
    parsed: object = None
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except ValueError:
            pass
    contract_valid = (
        isinstance(parsed, dict)
        and set(parsed) == {"status"}
        and parsed.get("status") == "ready"
    )
    observation.update(
        {
            "content_present": isinstance(content, str) and bool(content),
            "content_characters": len(content) if isinstance(content, str) else None,
            "json_object_valid": isinstance(parsed, dict),
            "contract_valid": contract_valid,
            "support_decision": (
                "supported"
                if status_code == 200
                and observation["identity_matches"]
                and contract_valid
                else "not_verified"
            ),
        }
    )
    return observation


def sanitize_tool_observation(
    *,
    model: str,
    status_code: int | None,
    elapsed_ms: float,
    payload: object = None,
    failure_type: str | None = None,
) -> dict[str, Any]:
    observation = _base_observation(
        model=model,
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        payload=payload,
        failure_type=failure_type,
    )
    _, message = _response_parts(payload)
    tool_calls = message.get("tool_calls")
    calls = tool_calls if isinstance(tool_calls, list) else []
    first = calls[0] if calls and isinstance(calls[0], dict) else {}
    function = first.get("function")
    function = function if isinstance(function, dict) else {}
    arguments = function.get("arguments")
    parsed_arguments: object = None
    if isinstance(arguments, str):
        try:
            parsed_arguments = json.loads(arguments)
        except ValueError:
            pass
    contract_valid = (
        len(calls) == 1
        and function.get("name") == TOOL_NAME
        and parsed_arguments == {"item": "ryuk"}
    )
    observation.update(
        {
            "tool_calls_present": bool(calls),
            "tool_call_count": len(calls),
            "requested_tool_name_matches": function.get("name") == TOOL_NAME,
            "arguments_json_valid": isinstance(parsed_arguments, dict),
            "arguments_contract_valid": parsed_arguments == {"item": "ryuk"},
            "contract_valid": contract_valid,
            "tool_executed": False,
            "support_decision": (
                "supported"
                if status_code == 200
                and observation["identity_matches"]
                and contract_valid
                else "not_verified"
            ),
        }
    )
    return observation


async def _post_contract(
    client: httpx.AsyncClient,
    *,
    model: str,
    kind: str,
    max_tokens: int,
    temperature: float,
    kimi_reasoning_effort: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if model == "moonshotai/kimi-k3" and kimi_reasoning_effort is not None:
        payload["reasoning_effort"] = kimi_reasoning_effort
    if kind == "structured":
        payload.update(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": STRUCTURED_PROMPT,
                    }
                ],
                "response_format": {"type": "json_object"},
            }
        )
        sanitizer = sanitize_structured_observation
    elif kind == "tool":
        payload.update(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": TOOL_PROMPT,
                    }
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": TOOL_NAME,
                            "description": "Return status for a public test item.",
                            "parameters": {
                                "type": "object",
                                "properties": {"item": {"type": "string"}},
                                "required": ["item"],
                                "additionalProperties": False,
                            },
                        },
                    }
                ],
            }
        )
        sanitizer = sanitize_tool_observation
    else:  # pragma: no cover
        raise ValueError("unknown contract kind")

    started = time.perf_counter()
    try:
        response = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = None
        return sanitizer(
            model=model,
            status_code=response.status_code,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            payload=response_payload,
            failure_type=(
                None if response.is_success else f"HTTP_{response.status_code}"
            ),
        )
    except httpx.HTTPError as exc:
        return sanitizer(
            model=model,
            status_code=None,
            elapsed_ms=(time.perf_counter() - started) * 1000,
            failure_type=type(exc).__name__,
        )


async def collect_structured_tool_evidence(
    api_key: str,
    *,
    models: tuple[str, ...] = APPROVED_MODELS,
    max_tokens: int = 128,
    timeout_seconds: float = 180.0,
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
        "probe": "p2b-005-hosted-structured-tools",
        "base_url": BASE_URL,
        "started_at": _timestamp(),
        "settings": {
            "max_tokens": max_tokens,
            "timeout_seconds": timeout_seconds,
            "temperature": temperature,
            "stream": False,
            "synthetic_public_input": True,
            "tools_executed": False,
            "models": list(models),
            "kimi_reasoning_effort": kimi_reasoning_effort,
        },
    }
    timeout = httpx.Timeout(timeout_seconds, connect=10.0, pool=10.0)
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        results = await asyncio.gather(
            *(
                _post_contract(
                    client,
                    model=model,
                    kind=kind,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    kimi_reasoning_effort=kimi_reasoning_effort,
                )
                for model in models
                for kind in ("structured", "tool")
            )
        )
    evidence["structured_output"] = results[::2]
    evidence["tool_calls"] = results[1::2]
    evidence["completed_at"] = _timestamp()
    return evidence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
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
        collect_structured_tool_evidence(
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
    observations = evidence["structured_output"] + evidence["tool_calls"]
    return 0 if all(item["contract_valid"] for item in observations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
