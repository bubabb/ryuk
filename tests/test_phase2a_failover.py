"""Offline router contracts; synthetic HTTP evidence never certifies a deployment."""

import json
from dataclasses import replace

import httpx
import pytest

from backend.inference.capabilities import (
    DeploymentCapabilities,
    TaskKind,
    configured_claim,
)
from backend.inference.contracts import AttemptOutcome, TaskRequirements
from backend.inference.deployment import DeploymentRef, IdentityVerification, ModelRef
from backend.inference.engines.nim import NVIDIAHostedNIMEngine
from backend.inference.errors import InferenceFailure
from backend.inference.profiles import load_offline_deployment_profiles
from backend.inference.registry import DeploymentRegistry, RegisteredDeployment
from backend.inference.router import InferenceRouter
from tests.test_phase2a_contract_fixtures import (
    FIXTURE_PATHS,
    PROFILE_DIRECTORY,
    inference_task,
    load_fixture,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_index", (0, 1))
@pytest.mark.parametrize(
    "failure_case", ("overload", "timeout", "malformed_choices", "response_limit")
)
@pytest.mark.parametrize("require_primary_model", (False, True))
async def test_offline_failover_preserves_identity_and_hard_model_constraint(
    primary_index: int, failure_case: str, require_primary_model: bool
) -> None:
    fixtures = [load_fixture(path) for path in FIXTURE_PATHS]
    primary = fixtures.pop(primary_index)
    fallback = fixtures[0]
    profiles = {
        profile.profile_id: profile
        for profile in load_offline_deployment_profiles(PROFILE_DIRECTORY)
    }
    failure = next(case for case in primary["cases"] if case["id"] == failure_case)
    success = next(
        case for case in fallback["cases"] if case["id"] == "success_with_usage"
    )
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/v1/models"
            return httpx.Response(200, json=primary["identity"]["response"])
        assert request.url.path == "/v1/chat/completions"
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == primary["model"]:
            if failure["behavior"] == "read_timeout":
                raise httpx.ReadTimeout("synthetic timeout", request=request)
            if failure["behavior"] == "oversized_response":
                return httpx.Response(200, content=b"x" * 4096)
            return httpx.Response(failure["status"], json=failure["response"])
        assert model == fallback["model"]
        return httpx.Response(success["status"], json=success["response"])

    registry = DeploymentRegistry()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for fixture in (primary, fallback):
            profile = profiles[fixture["profile_id"]]
            adapter = NVIDIAHostedNIMEngine(
                str(profile.base_url),
                model=profile.served_model_name,
                max_response_bytes=2048,
                client=client,
            )
            registry.register(
                RegisteredDeployment(
                    ref=DeploymentRef(
                        deployment_id=profile.profile_id,
                        model=ModelRef(
                            profile.model_artifact_id,
                            profile.model_revision,
                            profile.served_model_name,
                        ),
                        engine_name=adapter.name,
                        endpoint_id="offline-nvidia-catalog",
                    ),
                    engine=adapter,
                    capabilities=DeploymentCapabilities(
                        task_kinds=configured_claim(
                            frozenset({TaskKind.CHAT}), "offline"
                        ),
                        served_models=configured_claim(
                            frozenset({profile.served_model_name}), "offline"
                        ),
                        production_eligible=configured_claim(False, "offline"),
                    ),
                )
            )
        task = inference_task(primary["model"])
        if not require_primary_model:
            task = replace(task, requirements=TaskRequirements())
        router = InferenceRouter(registry)
        if require_primary_model:
            with pytest.raises(InferenceFailure) as raised:
                await router.generate_task(task)
            assert raised.value.code == failure["expected_failure"]
            attempts = raised.value.context["execution_attempts"]
            assert calls == [primary["model"]]
            assert len(attempts) == 1
        else:
            result = await router.generate_task(task)
            attempts = result.attempts
            assert calls == [primary["model"], fallback["model"]]
            assert result.provenance.deployment_id == fallback["profile_id"]
            assert result.provenance.model_artifact_id == fallback["model"]
            assert result.provenance.model_verification is (
                IdentityVerification.CONFIGURED_ONLY
                if profiles[fallback["profile_id"]].model_revision is not None
                else IdentityVerification.OBSERVED
            )
            assert result.provenance.model_revision is None
            assert result.provenance.engine_version is None
            assert result.provenance.serving_runtime is None
            assert result.output.text == success["expected"]["text"]
            assert result.reasoning is not None
            assert result.reasoning.text == success["expected"]["reasoning"]
            assert result.usage.input_tokens == success["expected"]["input_tokens"]
            assert result.usage.output_tokens == success["expected"]["output_tokens"]
            assert (
                result.adapter_metadata[adapter.name]["served_model"]
                == fallback["model"]
            )
            assert len(attempts) == 2
            assert attempts[1].outcome == AttemptOutcome.SUCCEEDED
            assert attempts[1].deployment_id == fallback["profile_id"]
            assert attempts[1].failure_code is None
        assert attempts[0].deployment_id == primary["profile_id"]
        assert attempts[0].outcome == AttemptOutcome.FAILED
        assert attempts[0].failure_code == failure["expected_failure"]
        assert [attempt.sequence for attempt in attempts] == list(
            range(1, len(attempts) + 1)
        )
        assert len({attempt.attempt_id for attempt in attempts}) == len(attempts)
        for attempt, model in zip(attempts, calls, strict=True):
            ref = registry.get(attempt.deployment_id).ref
            assert ref.model is not None
            assert ref.model.artifact_id == model
            assert attempt.schema_version == 2
            assert attempt.configured_deployment == ref
            assert attempt.finished_at >= attempt.started_at
            assert attempt.duration_ms >= 0
