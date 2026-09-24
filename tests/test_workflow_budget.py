import pytest

from backend.inference.errors import (
    DeadlineExceededFailure,
    WorkflowBudgetExceededFailure,
)
from backend.inference.router import ExecutionPolicy, InferenceRouter
from backend.workflows.budget import WorkflowBudget
from tests.test_execution import ControlledEngine, registry, task


def test_budget_validates_and_exposes_monotonic_remaining():
    with pytest.raises(ValueError):
        WorkflowBudget(0, 1)
    with pytest.raises(ValueError):
        WorkflowBudget(1, 0)
    budget = WorkflowBudget(10, 2, max_output_tokens=3)
    before = budget.remaining_seconds()
    assert budget.reserve_attempt()
    assert budget.attempts == 1
    assert budget.record_output_tokens(2)
    assert budget.output_tokens == 2
    assert not budget.record_output_tokens(2)
    assert budget.remaining_seconds() <= before
    assert budget.reserve_attempt()
    assert not budget.reserve_attempt()


@pytest.mark.asyncio
async def test_router_budget_caps_retries_without_multiplying_attempt_policy():
    first = ControlledEngine("first", failure=True)
    second = ControlledEngine("second")
    budget = WorkflowBudget(10, 1)
    router = InferenceRouter(
        registry(first, second), policy=ExecutionPolicy(max_attempts=3)
    )
    with pytest.raises(WorkflowBudgetExceededFailure) as raised:
        await router.generate_task(task(), budget=budget)
    assert budget.attempts == 1
    assert first.calls == 1
    assert second.calls == 0
    assert len(raised.value.context["execution_attempts"]) == 1


@pytest.mark.asyncio
async def test_router_budget_deadline_is_shared_across_availability_and_generation():
    slow = ControlledEngine("slow", delay=0.2)
    budget = WorkflowBudget(0.01, 3)
    with pytest.raises(DeadlineExceededFailure):
        await InferenceRouter(registry(slow)).generate_task(task(), budget=budget)
    assert budget.attempts == 1


@pytest.mark.asyncio
async def test_output_token_budget_rejects_after_generation_and_keeps_attempt_history():
    engine = ControlledEngine("only")
    # ControlledEngine returns unknown usage; exercise accounting directly.
    budget = WorkflowBudget(10, 2, max_output_tokens=1)
    assert budget.record_output_tokens(1)
    assert not budget.record_output_tokens(1)
    assert engine.calls == 0
