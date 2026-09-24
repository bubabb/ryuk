import pytest

from backend.inference.errors import GenerationFailure
from backend.inference.router import InferenceRouter
from backend.workflows.budget import WorkflowBudget
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_execution import ControlledEngine, registry
from tests.test_workflow_store import packet


@pytest.fixture
def workflow_env(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "executor.db")
    yield store
    store.close()


@pytest.mark.asyncio
async def test_executor_binds_one_budget_attempts_and_provenance(workflow_env):
    primary = ControlledEngine("primary", failure=True)
    fallback = ControlledEngine("fallback")
    workflow_id = workflow_env.create("tenant-a", "request-1", packet())
    outcome = await WorkflowExecutor(
        workflow_env, InferenceRouter(registry(primary, fallback))
    ).execute("tenant-a", workflow_id, "worker-a", WorkflowBudget(10, 3))
    assert outcome.state == "awaiting_validation"
    saved = workflow_env.get("tenant-a", workflow_id)
    assert saved is not None
    assert saved["state"] == "awaiting_validation"
    assert saved["result"]["provenance"]["deployment_id"] == "fallback-deployment"
    assert saved["result"]["budget"]["attempts"] == 2
    assert [item["failure_code"] for item in saved["result"]["attempts"]] == [
        "generation_failure",
        None,
    ]
    assert [
        item["configured_deployment"]["deployment_id"]
        for item in saved["result"]["attempts"]
    ] == [
        "primary-deployment",
        "fallback-deployment",
    ]
    assert "hello" not in str(saved["result"])


@pytest.mark.asyncio
async def test_executor_failure_is_terminal_and_does_not_leak_error_or_prompt(
    workflow_env,
):
    class Failing(ControlledEngine):
        async def generate_task(self, inference_task):
            del inference_task
            raise GenerationFailure(
                context={"provider_body": "private", "prompt": "secret"}
            )

    engine = Failing("only")
    workflow_id = workflow_env.create("tenant-a", "request-1", packet("private prompt"))
    outcome = await WorkflowExecutor(
        workflow_env, InferenceRouter(registry(engine))
    ).execute("tenant-a", workflow_id, "worker-a", WorkflowBudget(10, 2))
    assert outcome.state == "failed"
    saved = workflow_env.get("tenant-a", workflow_id)
    assert saved is not None
    assert saved["state"] == "failed"
    assert saved["result"]["failure_code"] == "generation_failure"
    assert "private" not in str(saved["result"])
    assert "prompt" not in str(saved["result"])
    assert engine.calls == 0


@pytest.mark.asyncio
async def test_executor_claims_are_tenant_scoped_and_duplicate_execution_rejected(
    workflow_env,
):
    workflow_id = workflow_env.create("tenant-a", "request-1", packet())
    executor = WorkflowExecutor(
        workflow_env, InferenceRouter(registry(ControlledEngine("only")))
    )
    with pytest.raises(WorkflowConflict):
        await executor.execute(
            "tenant-b", workflow_id, "worker-b", WorkflowBudget(10, 1)
        )
    await executor.execute("tenant-a", workflow_id, "worker-a", WorkflowBudget(10, 1))
    with pytest.raises(WorkflowConflict):
        await executor.execute(
            "tenant-a", workflow_id, "worker-b", WorkflowBudget(10, 1)
        )


@pytest.mark.asyncio
async def test_executor_rejects_wrong_budget_before_claim(workflow_env):
    workflow_id = workflow_env.create("tenant-a", "request-1", packet())
    with pytest.raises(ValueError, match="WorkflowBudget"):
        await WorkflowExecutor(
            workflow_env, InferenceRouter(registry(ControlledEngine("only")))
        ).execute("tenant-a", workflow_id, "worker-a", object())  # type: ignore[arg-type]
    assert workflow_env.get("tenant-a", workflow_id)["state"] == "ready"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "minimum,decision,state",
    [(1, "accepted", "succeeded"), (100, "rejected", "rejected")],
)
async def test_executor_result_requires_explicit_acceptance(
    workflow_env, minimum, decision, state
):
    from backend.audit.deterministic import ValidationPolicy

    engine = ControlledEngine("only")
    workflow_id = workflow_env.create("tenant-a", "validation", packet())
    execution = await WorkflowExecutor(
        workflow_env, InferenceRouter(registry(engine))
    ).execute("tenant-a", workflow_id, "worker", WorkflowBudget(10, 1))
    assert execution.state == "awaiting_validation"
    policy = ValidationPolicy(minimum_chars=minimum)
    report = workflow_env.validate("tenant-a", workflow_id, policy)
    assert report["decision"] == decision
    assert workflow_env.get("tenant-a", workflow_id)["state"] == state
    assert workflow_env.validate("tenant-a", workflow_id, policy) == report
    assert engine.calls == 1
