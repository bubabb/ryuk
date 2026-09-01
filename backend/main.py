from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend.audit.contracts import AuditIdentity, AuditReport
from backend.audit.deterministic import ValidationPolicy, validate_output
from backend.audit.policy import EvaluationContext, decide
from backend.config import settings
from backend.inference.capabilities import CapabilityClaim, DeploymentCapabilities
from backend.inference.contracts import (
    ChatInput,
    ChatMessage,
    ChatRole,
    GenerationConfig,
    InferenceResult,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.inference.errors import InferenceFailure
from backend.inference.registry import (
    build_deployment_registry,
    engine_registry_from_deployments,
)
from backend.inference.router import InferenceRouter
from backend.inference.runtime import DeploymentRuntimeState, RuntimeStateCollector
from backend.middleware import RequestBodyLimitMiddleware, RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    await runtime_collector.start()
    try:
        yield
    finally:
        await runtime_collector.stop()
        await deployment_registry.aclose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    RequestBodyLimitMiddleware,
    max_bytes=settings.max_request_body_bytes,
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(InferenceFailure)
async def inference_failure_handler(
    request: Request,
    failure: InferenceFailure,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=failure.http_status,
        content={"error": failure.public_payload(request_id)},
    )


deployment_registry = build_deployment_registry()

engine_registry = engine_registry_from_deployments(deployment_registry)

runtime_collector = RuntimeStateCollector(
    deployment_registry,
    probe_timeout=settings.runtime_probe_timeout_seconds,
    ttl_seconds=settings.runtime_state_ttl_seconds,
    interval_seconds=settings.runtime_refresh_interval_seconds,
)

inference_router = InferenceRouter(
    deployment_registry, runtime_states=runtime_collector.store
)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)

    model: str = Field(min_length=1)

    preferred_engine: str | None = None

    max_tokens: int | None = Field(default=None, ge=1)

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    deadline_at: datetime | None = None
    required_model: str | None = Field(default=None, min_length=1)
    required_context_tokens: int | None = Field(default=None, ge=1)
    requires_structured_output: bool = False
    requires_streaming: bool = False
    required_accelerator: str | None = Field(default=None, min_length=1)
    required_topology: str | None = Field(default=None, min_length=1)
    required_data_location: str | None = Field(default=None, min_length=1)
    production_only: bool = False

    @field_validator("prompt")
    @classmethod
    def validate_prompt_size(cls, value: str) -> str:
        if len(value) > settings.max_prompt_chars:
            raise ValueError(
                f"Prompt exceeds the {settings.max_prompt_chars} character limit."
            )
        return value

    @field_validator("max_tokens")
    @classmethod
    def validate_token_limit(cls, value: int | None) -> int | None:
        if value is not None and value > settings.max_generation_tokens:
            raise ValueError(
                "max_tokens exceeds the configured generation-token limit."
            )
        return value

    @field_validator("deadline_at")
    @classmethod
    def validate_deadline(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("deadline_at must include timezone information.")
        return value


class ChatMessageRequest(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message content must not be blank.")
        return value


class ChatGenerateRequest(BaseModel):
    messages: list[ChatMessageRequest] = Field(min_length=1)
    model: str | None = Field(default=None, min_length=1)
    preferred_engine: str | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    deadline_at: datetime | None = None
    required_model: str | None = Field(default=None, min_length=1)
    required_context_tokens: int | None = Field(default=None, ge=1)
    requires_structured_output: bool = False
    requires_streaming: bool = False
    required_accelerator: str | None = Field(default=None, min_length=1)
    required_topology: str | None = Field(default=None, min_length=1)
    required_data_location: str | None = Field(default=None, min_length=1)
    production_only: bool = False

    @field_validator("max_tokens")
    @classmethod
    def validate_token_limit(cls, value: int | None) -> int | None:
        if value is not None and value > settings.max_generation_tokens:
            raise ValueError(
                "max_tokens exceeds the configured generation-token limit."
            )
        return value

    @field_validator("deadline_at")
    @classmethod
    def validate_deadline(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("deadline_at must include timezone information.")
        return value


class AuditValidationRequest(BaseModel):
    output: str = Field(max_length=100_000)
    generator_deployment_id: str = Field(min_length=1)
    generator_model_artifact_id: str = Field(min_length=1)
    generator_model_revision: str | None = None
    required_sections: list[str] = Field(default_factory=list, max_length=32)
    require_citations: bool = False
    minimum_chars: int = Field(default=0, ge=0)
    maximum_chars: int = Field(default=100_000, ge=0)
    language: str | None = None
    forbidden_phrases: list[str] = Field(default_factory=list, max_length=32)
    high_risk: bool = False


def serialize_inference_result(result: InferenceResult) -> dict[str, object]:
    return {
        "text": result.output.text,
        "model": result.provenance.model_artifact_id,
        "engine": result.provenance.engine_name,
        "latency_ms": result.timing.total_ms,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "metadata": result.adapter_metadata,
        "finish_reason": result.finish_reason,
        "attempts": [
            {
                "attempt_id": attempt.attempt_id,
                "sequence": attempt.sequence,
                "deployment_id": attempt.deployment_id,
                "started_at": attempt.started_at.isoformat(),
                "finished_at": attempt.finished_at.isoformat(),
                "duration_ms": attempt.duration_ms,
                "outcome": attempt.outcome,
                "failure_code": attempt.failure_code,
                "retry_classification": attempt.retry_classification,
            }
            for attempt in result.attempts
        ],
        "routing_decision": (
            {
                "policy_version": result.routing_decision.policy_version,
                "ordered_deployment_ids": (
                    result.routing_decision.ordered_deployment_ids
                ),
                "candidates": [
                    {
                        "deployment_id": candidate.deployment_id,
                        "total": candidate.total,
                        "components": dict(candidate.components),
                        "explanation": candidate.explanation,
                    }
                    for candidate in result.routing_decision.candidates
                ],
            }
            if result.routing_decision is not None
            else None
        ),
        "provenance": {
            "deployment_id": result.provenance.deployment_id,
            "engine_name": result.provenance.engine_name,
            "engine_version": result.provenance.engine_version,
            "serving_runtime": result.provenance.serving_runtime,
            "model_artifact_id": result.provenance.model_artifact_id,
            "model_revision": result.provenance.model_revision,
            "model_verification": result.provenance.model_verification,
        },
    }


def serialize_capabilities(capabilities: DeploymentCapabilities) -> dict[str, object]:
    result: dict[str, object] = {}
    for field_name in capabilities.__dataclass_fields__:
        claim = getattr(capabilities, field_name)
        if not isinstance(claim, CapabilityClaim):
            result[field_name] = None
            continue
        value = claim.value
        if isinstance(value, frozenset):
            value = sorted(value)
        result[field_name] = {
            "value": value,
            "source": claim.source,
            "scope": claim.scope,
            "runtime_version": claim.runtime_version,
            "observed_at": (
                claim.observed_at.isoformat() if claim.observed_at else None
            ),
            "expires_at": claim.expires_at.isoformat() if claim.expires_at else None,
            "confidence": claim.confidence,
        }
    return result


def serialize_runtime_state(state: DeploymentRuntimeState) -> dict[str, object]:
    return {
        "liveness": state.liveness,
        "readiness": state.readiness,
        "admission": state.admission,
        "capacity": state.capacity,
        "observed_at": state.observed_at.isoformat() if state.observed_at else None,
        "expires_at": state.expires_at.isoformat() if state.expires_at else None,
        "stale": state.is_stale(),
        "probe_latency_ms": state.probe_latency_ms,
        "probe_error": state.probe_error,
        "summary": {
            "attempt_count": state.summary.attempt_count,
            "failure_count": state.summary.failure_count,
            "recent_failure_rate": state.summary.recent_failure_rate,
            "last_attempt_latency_ms": state.summary.last_attempt_latency_ms,
            "last_failure_code": state.summary.last_failure_code,
        },
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/inference/engines")
async def inference_engines():
    engines = []

    for deployment in deployment_registry.all():
        engine = deployment.engine

        runtime_state = runtime_collector.store.get(deployment.ref.deployment_id)
        available = runtime_state.is_routable()

        engines.append(
            {
                "name": engine.name,
                "deployment_id": deployment.ref.deployment_id,
                "configured_model": (
                    deployment.ref.model.artifact_id
                    if deployment.ref.model is not None
                    else None
                ),
                "available": available,
                "identity": None,
                "capabilities": serialize_capabilities(deployment.capabilities),
                "runtime": serialize_runtime_state(runtime_state),
            }
        )

    return {
        "count": len(engines),
        "engines": engines,
    }


@app.post("/inference/generate")
async def inference_generate(payload: GenerateRequest, http_request: Request):
    traceparent = getattr(http_request.state, "traceparent", None)

    inference_task = InferenceTask(
        input=TextInput(payload.prompt),
        generation=GenerationConfig(
            max_output_tokens=payload.max_tokens,
            temperature=payload.temperature,
        ),
        requirements=TaskRequirements(
            requested_model=payload.model,
            required_model=payload.required_model,
            required_context_tokens=payload.required_context_tokens,
            requires_structured_output=payload.requires_structured_output,
            requires_streaming=payload.requires_streaming,
            required_accelerator=payload.required_accelerator,
            required_topology=payload.required_topology,
            required_data_location=payload.required_data_location,
            production_only=payload.production_only,
        ),
        trace=TraceContext(
            request_id=http_request.state.request_id,
            traceparent=traceparent,
        ),
        deadline_at=payload.deadline_at,
    )

    result = await inference_router.generate_task(
        inference_task,
        preferred_engine=payload.preferred_engine,
    )

    return serialize_inference_result(result)


@app.post("/v1/inference/chat")
async def inference_chat(payload: ChatGenerateRequest, http_request: Request):
    traceparent = getattr(http_request.state, "traceparent", None)
    task = InferenceTask(
        input=ChatInput(
            messages=tuple(
                ChatMessage(role=message.role, content=message.content)
                for message in payload.messages
            )
        ),
        generation=GenerationConfig(
            max_output_tokens=payload.max_tokens,
            temperature=payload.temperature,
        ),
        requirements=TaskRequirements(
            requested_model=payload.model,
            required_model=payload.required_model,
            required_context_tokens=payload.required_context_tokens,
            requires_structured_output=payload.requires_structured_output,
            requires_streaming=payload.requires_streaming,
            required_accelerator=payload.required_accelerator,
            required_topology=payload.required_topology,
            required_data_location=payload.required_data_location,
            production_only=payload.production_only,
        ),
        trace=TraceContext(
            request_id=http_request.state.request_id,
            traceparent=traceparent,
        ),
        deadline_at=payload.deadline_at,
    )

    result = await inference_router.generate_task(
        task,
        preferred_engine=payload.preferred_engine,
    )

    return serialize_inference_result(result)


@app.post("/v1/audit/validate")
async def audit_validate(payload: AuditValidationRequest):
    policy = ValidationPolicy(
        required_sections=tuple(payload.required_sections),
        require_citations=payload.require_citations,
        minimum_chars=payload.minimum_chars,
        maximum_chars=payload.maximum_chars,
        language=payload.language,
        forbidden_phrases=tuple(payload.forbidden_phrases),
    )
    findings = validate_output(payload.output, policy)
    report = AuditReport(
        report_version="ryuk-audit-report-v1",
        generator=AuditIdentity(
            payload.generator_deployment_id,
            payload.generator_model_artifact_id,
            payload.generator_model_revision,
        ),
        auditor=None,
        deterministic_findings=findings,
    )
    decision = decide(
        report,
        EvaluationContext(iteration=0, high_risk=payload.high_risk),
    )
    return {
        "report_version": report.report_version,
        "findings": [
            {"kind": item.kind, "severity": item.severity, "code": item.code}
            for item in findings
        ],
        "decision": {
            "policy_version": decision.policy_version,
            "action": decision.action,
            "reasons": decision.reasons,
            "iteration": decision.iteration,
        },
    }
