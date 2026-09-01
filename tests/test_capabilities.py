import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from backend.inference.capabilities import (
    CapabilityClaim,
    DeploymentCapabilities,
    EvidenceSource,
    TaskKind,
    configured_claim,
    evaluate_capabilities,
)
from backend.inference.contracts import (
    GenerationConfig,
    InferenceTask,
    RoutingRequirements,
    TextInput,
    TraceContext,
)

FIXTURE = Path(__file__).parent / "fixtures" / "capability_matrix.json"


def make_task(values: dict[str, Any]) -> InferenceTask:
    return InferenceTask(
        input=TextInput("hello"),
        generation=GenerationConfig(),
        requirements=RoutingRequirements(
            required_model=values.get("required_model"),
            required_context_tokens=values.get("required_context_tokens"),
            requires_structured_output=values.get("requires_structured_output", False),
            requires_streaming=values.get("requires_streaming", False),
            required_accelerator=values.get("required_accelerator"),
            required_topology=values.get("required_topology"),
            required_data_location=values.get("required_data_location"),
            production_only=values.get("production_only", False),
        ),
        trace=TraceContext(request_id="request-1"),
    )


def make_capabilities(values: dict[str, Any]) -> DeploymentCapabilities:
    def string_set(name: str):
        value = values.get(name)
        return configured_claim(frozenset(value), "fixture") if value else None

    task_kinds = values.get("task_kinds")
    return DeploymentCapabilities(
        task_kinds=(
            configured_claim(
                frozenset(TaskKind(item) for item in task_kinds), "fixture"
            )
            if task_kinds
            else None
        ),
        served_models=string_set("served_models"),
        max_context_tokens=(
            configured_claim(values["max_context_tokens"], "fixture")
            if "max_context_tokens" in values
            else None
        ),
        structured_output=(
            configured_claim(values["structured_output"], "fixture")
            if "structured_output" in values
            else None
        ),
        streaming=(
            configured_claim(values["streaming"], "fixture")
            if "streaming" in values
            else None
        ),
        accelerators=string_set("accelerators"),
        topologies=string_set("topologies"),
        data_locations=string_set("data_locations"),
        production_eligible=(
            configured_claim(values["production_eligible"], "fixture")
            if "production_eligible" in values
            else None
        ),
    )


@pytest.mark.parametrize(
    "case", json.loads(FIXTURE.read_text()), ids=lambda case: case["name"]
)
def test_capability_fixture_matrix(case: dict[str, object]) -> None:
    requirements = cast(dict[str, Any], case["requirements"])
    capabilities = cast(dict[str, Any], case["capabilities"])
    decision = evaluate_capabilities(
        make_task(requirements),
        make_capabilities(capabilities),
    )

    assert decision.eligible is case["eligible"]
    assert [rejection.code for rejection in decision.rejections] == case["codes"]


def test_expired_claim_is_unknown_not_supported() -> None:
    expired = CapabilityClaim(
        value=True,
        source=EvidenceSource.MEASURED,
        scope="deployment",
        observed_at=datetime.now(UTC) - timedelta(minutes=2),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    capabilities = DeploymentCapabilities(
        task_kinds=configured_claim(frozenset({TaskKind.TEXT}), "test"),
        streaming=expired,
    )

    decision = evaluate_capabilities(
        make_task({"requires_streaming": True}), capabilities
    )

    assert decision.rejections[0].code == "unknown_streaming"


def test_claim_rejects_invalid_evidence_metadata() -> None:
    with pytest.raises(ValueError, match="confidence"):
        CapabilityClaim(
            value=True, source=EvidenceSource.DECLARED, scope="x", confidence=1.1
        )
