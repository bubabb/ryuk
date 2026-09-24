import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from backend.control.records import ExecutionRecord, SQLiteExecutionRecordStore
from backend.inference.attempts import deserialize_attempt, serialize_attempt
from backend.inference.contracts import AttemptOutcome, ExecutionAttempt
from backend.inference.deployment import DeploymentRef, ModelRef
from backend.inference.registry import DeploymentRegistry
from backend.inference.router import InferenceRouter
from tests.test_execution import ControlledEngine, registry, task


@pytest.mark.asyncio
async def test_attempt_snapshots_survive_registry_replacement_and_store_reopen(
    tmp_path,
):
    original = registry(
        ControlledEngine("first", failure=True), ControlledEngine("second")
    )
    result = await InferenceRouter(original).generate_task(task())
    encoded = [serialize_attempt(attempt) for attempt in result.attempts]
    store = SQLiteExecutionRecordStore(tmp_path / "history.db")
    record = ExecutionRecord(
        "request-1",
        "tenant-a",
        "accepted",
        "test",
        {"attempts": encoded},
        datetime.now(UTC),
    )
    store.put(record)
    store.close()
    replacement = DeploymentRegistry()
    for deployment in original.all():
        replacement.register(
            replace(
                deployment,
                ref=replace(deployment.ref, model=ModelRef("replacement/model")),
            )
        )
    store = SQLiteExecutionRecordStore(tmp_path / "history.db")
    try:
        saved = store.get("tenant-a", "request-1")
        assert saved is not None
        recovered = tuple(
            deserialize_attempt(item) for item in saved.payload["attempts"]
        )
        assert recovered == result.attempts
        for attempt in recovered:
            assert attempt.schema_version == 2
            assert (
                attempt.configured_deployment == original.get(attempt.deployment_id).ref
            )
            assert (
                attempt.configured_deployment
                != replacement.get(attempt.deployment_id).ref
            )
            with pytest.raises(FrozenInstanceError):
                attempt.configured_deployment.model = ModelRef("changed")  # type: ignore[misc]
        assert store.get("tenant-b", "request-1") is None
        assert "model_verification" not in json.dumps(encoded)
    finally:
        store.close()


def legacy_attempt():
    return ExecutionAttempt(
        "old",
        1,
        "deployment",
        datetime.now(UTC),
        datetime.now(UTC),
        1,
        AttemptOutcome.SUCCEEDED,
    )


def test_legacy_attempts_remain_readable_without_invented_identity():
    payload = serialize_attempt(legacy_attempt())
    del payload["schema_version"]
    del payload["configured_deployment"]
    decoded = deserialize_attempt(json.loads(json.dumps(payload)))
    assert decoded.schema_version == 1
    assert decoded.configured_deployment is None


def test_attempt_rejects_missing_mismatched_or_future_snapshots():
    attempt = legacy_attempt()
    with pytest.raises(ValueError, match="require a configured"):
        replace(attempt, schema_version=2)
    with pytest.raises(ValueError, match="Unsupported"):
        replace(attempt, schema_version=3)
    with pytest.raises(ValueError, match="must match"):
        replace(
            attempt,
            configured_deployment=DeploymentRef("other", None, "test", "endpoint"),
        )
