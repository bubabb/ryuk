import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
from backend.control.admission import AdmissionController, QuotaPolicy
from backend.control.api import APIControlPlane
from backend.control.records import SQLiteExecutionRecordStore
from backend.control.security import Principal, Role, issue_api_key
from backend.inference.base import DeploymentProvenance
from backend.inference.capabilities import DeploymentCapabilities, configured_claim
from backend.inference.contracts import (
    FinishReason,
    InferenceResult,
    InferenceTiming,
    TextOutput,
    TokenUsage,
)
from backend.inference.deployment import (
    DeploymentRef,
    IdentityVerification,
    ModelRef,
)
from backend.inference.engines.mock import MockEngine
from backend.inference.errors import UnknownEnginePreferenceFailure
from backend.inference.registry import DeploymentRegistry, RegisteredDeployment
from backend.inference.router import NoAvailableEngineError

client = TestClient(main_module.app)
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def configured_api_control(tmp_path, monkeypatch):
    principal = Principal("test-admin", "tenant-test", frozenset({Role.ADMIN}))
    api_key, record = issue_api_key(principal)
    store = SQLiteExecutionRecordStore(tmp_path / "api-records.db")
    control = APIControlPlane(
        {record.key_id: record},
        AdmissionController(
            {"tenant-test": QuotaPolicy(1_000, 10, 100_000_000)}
        ),
        store,
    )
    monkeypatch.setattr(main_module, "api_control", control)
    client.headers["Authorization"] = f"Bearer {api_key}"
    yield {"principal": principal, "store": store}
    client.headers.pop("Authorization", None)
    store.close()


def typed_result() -> InferenceResult:
    return InferenceResult(
        output=TextOutput("generated"),
        finish_reason=FinishReason.STOP,
        usage=TokenUsage(),
        timing=InferenceTiming(total_ms=1.0),
        provenance=DeploymentProvenance(
            deployment_id="mock-development",
            engine_name="mock",
            model_artifact_id="ryuk/mock",
            model_revision=None,
            model_verification=IdentityVerification.VERIFIED,
            serving_runtime="in_process",
        ),
        adapter_metadata={"mock": True},
    )


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Ryuk AI"


@pytest.mark.asyncio
async def test_production_startup_requires_verified_eligible_deployment() -> None:
    config = main_module.Settings(
        app_env=main_module.AppEnvironment.PRODUCTION,
        mock_enabled=False,
        sglang_enabled=False,
        control_plane_config_path=Path("control.json"),
        execution_record_path=Path("records.db"),
    )
    empty = DeploymentRegistry()
    with pytest.raises(RuntimeError, match="eligible"):
        await main_module.verify_production_deployments(config, empty)

    verified = DeploymentRegistry()
    verified.register(
        RegisteredDeployment(
            ref=DeploymentRef(
                deployment_id="verified",
                model=ModelRef("ryuk/mock", served_name="mock"),
                engine_name="mock",
                endpoint_id="mock",
            ),
            engine=MockEngine(),
            capabilities=DeploymentCapabilities(
                production_eligible=configured_claim(True, "test")
            ),
        )
    )
    await main_module.verify_production_deployments(config, verified)

    unverified = DeploymentRegistry()
    unverified.register(
        RegisteredDeployment(
            ref=DeploymentRef(
                deployment_id="unverified",
                model=ModelRef("ryuk/mock", revision="missing-revision"),
                engine_name="mock",
                endpoint_id="mock",
            ),
            engine=MockEngine(),
            capabilities=DeploymentCapabilities(
                production_eligible=configured_claim(True, "test")
            ),
        )
    )
    with pytest.raises(RuntimeError, match="identity verification"):
        await main_module.verify_production_deployments(config, unverified)


def test_non_health_routes_reject_missing_and_malformed_credentials() -> None:
    client.headers.pop("Authorization")

    missing = client.post(
        "/inference/generate",
        json={"prompt": "hello", "model": "test-model"},
    )
    malformed = client.post(
        "/v1/audit/validate",
        headers={"Authorization": "not-bearer"},
        json={
            "output": "result",
            "generator_deployment_id": "deployment-1",
            "generator_model_artifact_id": "model-1",
        },
    )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "authentication_required"
    assert missing.headers["www-authenticate"] == "Bearer"
    assert malformed.status_code == 401
    assert malformed.json()["error"]["code"] == "invalid_credentials"


def test_audit_requires_operator_role(monkeypatch) -> None:
    principal = Principal(
        "inference-only", "tenant-test", frozenset({Role.INFERENCE})
    )
    api_key, record = issue_api_key(principal)
    control = APIControlPlane(
        {record.key_id: record},
        AdmissionController(
            {"tenant-test": QuotaPolicy(10, 1, 1_000_000)}
        ),
    )
    monkeypatch.setattr(main_module, "api_control", control)

    response = client.post(
        "/v1/audit/validate",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "output": "result",
            "generator_deployment_id": "deployment-1",
            "generator_model_artifact_id": "model-1",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_quota_rejection_does_not_contact_inference(monkeypatch) -> None:
    principal = Principal("limited", "tenant-limited", frozenset({Role.INFERENCE}))
    api_key, record = issue_api_key(principal)
    monkeypatch.setattr(
        main_module,
        "api_control",
        APIControlPlane(
            {record.key_id: record},
            AdmissionController(
                {"tenant-limited": QuotaPolicy(10, 1, 1)}
            ),
        ),
    )
    generate = AsyncMock(side_effect=AssertionError("router must not be contacted"))
    monkeypatch.setattr(main_module.inference_router, "generate_task", generate)

    response = client.post(
        "/inference/generate",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"prompt": "hello", "model": "test-model"},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "quota_exceeded"
    assert generate.await_count == 0


def test_inference_permit_is_released_after_failure(monkeypatch) -> None:
    principal = Principal("limited", "tenant-limited", frozenset({Role.INFERENCE}))
    api_key, record = issue_api_key(principal)
    monkeypatch.setattr(
        main_module,
        "api_control",
        APIControlPlane(
            {record.key_id: record},
            AdmissionController(
                {"tenant-limited": QuotaPolicy(2, 1, 100_000)}
            ),
        ),
    )
    generate = AsyncMock(
        side_effect=[NoAvailableEngineError(), typed_result()]
    )
    monkeypatch.setattr(main_module.inference_router, "generate_task", generate)
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"prompt": "hello", "model": "test-model", "max_tokens": 10}

    failed = client.post("/inference/generate", headers=headers, json=payload)
    retried = client.post("/inference/generate", headers=headers, json=payload)

    assert failed.status_code == 503
    assert retried.status_code == 200
    assert generate.await_count == 2


def test_generate_persists_sanitized_terminal_record(configured_api_control) -> None:
    response = client.post(
        "/inference/generate",
        headers={"x-request-id": "recorded-request"},
        json={
            "prompt": "private prompt",
            "model": "caller-model",
            "preferred_engine": "mock",
        },
    )

    assert response.status_code == 200
    record = configured_api_control["store"].get(
        "tenant-test", "recorded-request"
    )
    assert record is not None
    assert record.status == "accepted"
    assert record.payload == {
        "operation": "inference.generate",
        "deployment_id": "mock-development",
        "model_artifact_id": "ryuk/mock",
        "finish_reason": "stop",
    }
    serialized = json.dumps(record.payload).casefold()
    assert "private prompt" not in serialized
    assert "authorization" not in serialized


def test_every_governed_route_persists_sanitized_terminal_record(
    configured_api_control,
) -> None:
    requests: tuple[tuple[str, Any, str, dict[str, Any], str], ...] = (
        (
            "engine-record",
            client.get,
            "/inference/engines",
            {},
            "deployment.status",
        ),
        (
            "chat-record",
            client.post,
            "/v1/inference/chat",
            {
                "json": {
                    "messages": [{"role": "user", "content": "private chat"}],
                    "preferred_engine": "mock",
                }
            },
            "inference.chat",
        ),
        (
            "audit-record",
            client.post,
            "/v1/audit/validate",
            {
                "json": {
                    "output": "private audited output",
                    "generator_deployment_id": "deployment-1",
                    "generator_model_artifact_id": "model-1",
                }
            },
            "audit.validate",
        ),
    )

    for request_id, method, path, kwargs, operation in requests:
        response = method(
            path,
            headers={"x-request-id": request_id},
            **kwargs,
        )
        assert response.status_code == 200
        record = configured_api_control["store"].get("tenant-test", request_id)
        assert record is not None
        assert record.status == "accepted"
        assert record.payload["operation"] == operation
        serialized = json.dumps(record.payload).casefold()
        assert "private" not in serialized
        assert "authorization" not in serialized
        assert "output" not in serialized


def test_authenticated_quota_rejection_is_recorded(monkeypatch, tmp_path) -> None:
    principal = Principal("limited", "tenant-limited", frozenset({Role.INFERENCE}))
    api_key, key_record = issue_api_key(principal)
    store = SQLiteExecutionRecordStore(tmp_path / "rejections.db")
    control = APIControlPlane(
        {key_record.key_id: key_record},
        AdmissionController({"tenant-limited": QuotaPolicy(10, 1, 1)}),
        store,
    )
    monkeypatch.setattr(main_module, "api_control", control)

    response = client.post(
        "/inference/generate",
        headers={
            "Authorization": f"Bearer {api_key}",
            "x-request-id": "quota-record",
        },
        json={"prompt": "private prompt", "model": "test-model"},
    )

    assert response.status_code == 429
    record = store.get("tenant-limited", "quota-record")
    assert record is not None
    assert record.status == "rejected"
    assert record.payload == {
        "operation": "inference.generate",
        "failure_code": "quota_exceeded",
    }
    store.close()


def test_control_events_are_emitted_without_request_payloads(caplog) -> None:
    caplog.set_level(logging.INFO, logger="ryuk.control")

    response = client.post(
        "/inference/generate",
        json={
            "prompt": "private-event-prompt",
            "model": "caller-model",
            "preferred_engine": "mock",
        },
    )

    assert response.status_code == 200
    events = [
        record
        for record in caplog.records
        if getattr(record, "event_name", None) is not None
    ]
    assert {record.event_name for record in events} == {
        "api.request.authorized",
        "api.admission.accepted",
        "api.request.terminal",
    }
    serialized = repr([record.__dict__ for record in events]).casefold()
    assert "private-event-prompt" not in serialized
    assert "authorization" not in serialized


def test_deterministic_audit_endpoint_is_structured_and_bounded() -> None:
    response = client.post(
        "/v1/audit/validate",
        json={
            "output": "No citation",
            "generator_deployment_id": "deployment-1",
            "generator_model_artifact_id": "model-1",
            "require_citations": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["findings"][0]["code"] == "citation_missing"
    assert response.json()["decision"]["action"] == "revise"


def test_engine_status_reports_cached_runtime_without_probing(monkeypatch) -> None:
    probes = []
    for deployment in main_module.deployment_registry.all():
        probe = AsyncMock(side_effect=AssertionError("status must use cache"))
        monkeypatch.setattr(deployment.engine, "is_available", probe)
        probes.append(probe)
    response = client.get("/inference/engines")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    by_name = {engine["name"]: engine for engine in payload["engines"]}
    assert by_name["sglang"] == {
        "name": "sglang",
        "deployment_id": "sglang-local",
        "configured_model": None,
        "available": False,
        "identity": None,
        "capabilities": by_name["sglang"]["capabilities"],
        "runtime": by_name["sglang"]["runtime"],
    }
    assert by_name["sglang"]["capabilities"]["task_kinds"]["value"] == ["text"]
    assert by_name["mock"]["capabilities"]["production_eligible"]["value"] is False
    assert by_name["mock"]["deployment_id"] == "mock-development"
    assert by_name["mock"]["configured_model"] == "ryuk/mock"
    assert by_name["mock"]["identity"] is None
    assert by_name["mock"]["runtime"]["readiness"] == "ready"
    assert by_name["sglang"]["runtime"]["readiness"] == "unknown"
    assert all(probe.await_count == 0 for probe in probes)


def test_generate_endpoint_returns_normalized_response(monkeypatch) -> None:
    generate = AsyncMock(return_value=typed_result())
    monkeypatch.setattr(main_module.inference_router, "generate_task", generate)

    response = client.post(
        "/inference/generate",
        json={
            "prompt": "hello",
            "model": "test-model",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    expected = json.loads((FIXTURES / "v0_generate_response.json").read_text())
    assert response.json() == expected

    assert generate.await_args is not None
    routed_task = generate.await_args.args[0]
    assert routed_task.trace.request_id == response.headers["x-request-id"]
    assert routed_task.input.text == "hello"
    assert routed_task.requirements.requested_model == "test-model"


def test_generate_propagates_valid_trace_context(monkeypatch) -> None:
    generate = AsyncMock(return_value=typed_result())
    monkeypatch.setattr(main_module.inference_router, "generate_task", generate)
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    response = client.post(
        "/inference/generate",
        headers={"x-request-id": "request-123", "traceparent": traceparent},
        json={"prompt": "hello", "model": "test-model"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"
    assert generate.await_args is not None
    routed_task = generate.await_args.args[0]
    assert routed_task.trace == main_module.TraceContext(
        request_id="request-123",
        traceparent=traceparent,
    )


def test_generate_endpoint_maps_no_engine_to_503(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module.inference_router,
        "generate_task",
        AsyncMock(side_effect=NoAvailableEngineError()),
    )

    response = client.post(
        "/inference/generate",
        json={"prompt": "hello", "model": "test-model"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "deployment_unavailable",
            "message": "No inference deployment is currently available.",
            "retryable": True,
            "request_id": response.headers["x-request-id"],
        }
    }


def test_generate_endpoint_maps_unknown_engine_to_safe_400(monkeypatch) -> None:
    failure = UnknownEnginePreferenceFailure(
        context={"preferred_engine": "secret-internal-name"}
    )
    monkeypatch.setattr(
        main_module.inference_router,
        "generate_task",
        AsyncMock(side_effect=failure),
    )

    response = client.post(
        "/inference/generate",
        headers={"x-request-id": "request-error-1"},
        json={"prompt": "hello", "model": "test-model"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "unknown_engine_preference",
            "message": "The requested inference engine is not registered.",
            "retryable": False,
            "request_id": "request-error-1",
        }
    }
    assert "secret-internal-name" not in response.text


def test_generate_with_mock_returns_deployment_provenance() -> None:
    response = client.post(
        "/inference/generate",
        json={
            "prompt": "hello",
            "model": "caller-controlled-name",
            "preferred_engine": "mock",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "ryuk/mock"
    assert payload["engine"] == "mock"
    assert payload["provenance"] == {
        "deployment_id": "mock-development",
        "engine_name": "mock",
        "engine_version": None,
        "serving_runtime": "in_process",
        "model_artifact_id": "ryuk/mock",
        "model_revision": None,
        "model_verification": "verified",
    }
    assert payload["finish_reason"] == "stop"
    assert payload["metadata"]["input_kind"] == "text"


def test_generate_rejects_empty_prompt() -> None:
    response = client.post(
        "/inference/generate",
        json={"prompt": "", "model": "test-model"},
    )

    assert response.status_code == 422


def test_generate_rejects_invalid_temperature() -> None:
    response = client.post(
        "/inference/generate",
        json={"prompt": "hello", "model": "test-model", "temperature": 2.1},
    )

    assert response.status_code == 422


def test_generate_rejects_non_positive_max_tokens() -> None:
    response = client.post(
        "/inference/generate",
        json={"prompt": "hello", "model": "test-model", "max_tokens": 0},
    )

    assert response.status_code == 422


def test_generate_rejects_configured_token_limit() -> None:
    response = client.post(
        "/inference/generate",
        json={
            "prompt": "hello",
            "model": "test-model",
            "max_tokens": main_module.settings.max_generation_tokens + 1,
        },
    )

    assert response.status_code == 422


def test_hard_capability_rejection_is_structured_before_health(monkeypatch) -> None:
    for deployment in main_module.deployment_registry.all():
        monkeypatch.setattr(
            deployment.engine,
            "is_available",
            AsyncMock(side_effect=AssertionError("health must not be called")),
        )

    response = client.post(
        "/inference/generate",
        json={
            "prompt": "hello",
            "model": "soft-preference",
            "requires_structured_output": True,
        },
    )

    assert response.status_code == 422
    payload = response.json()["error"]
    assert payload["code"] == "capability_mismatch"
    assert payload["retryable"] is False
    assert {item["reason"] for item in payload["rejections"]} == {"unsupported"}
    assert {item["deployment_id"] for item in payload["rejections"]} == {
        "sglang-local",
        "mock-development",
    }


def test_versioned_chat_endpoint_uses_native_typed_mock() -> None:
    response = client.post(
        "/v1/inference/chat",
        json={
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Explain Ryuk."},
            ],
            "preferred_engine": "sglang",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "Mock chat response for: Explain Ryuk."
    assert payload["model"] == "ryuk/mock"
    assert payload["finish_reason"] == "stop"
    assert payload["metadata"]["input_kind"] == "chat"
    assert payload["routing_decision"]["ordered_deployment_ids"] == ["mock-development"]
    assert payload["provenance"]["model_verification"] == "verified"


def test_versioned_chat_endpoint_rejects_empty_messages() -> None:
    response = client.post(
        "/v1/inference/chat",
        json={"messages": [], "preferred_engine": "mock"},
    )

    assert response.status_code == 422


def test_versioned_chat_endpoint_rejects_blank_content() -> None:
    response = client.post(
        "/v1/inference/chat",
        json={
            "messages": [{"role": "user", "content": "   "}],
            "preferred_engine": "mock",
        },
    )

    assert response.status_code == 422
