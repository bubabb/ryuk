from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from backend.inference.attempts import serialize_attempt
from backend.inference.errors import InferenceFailure
from backend.inference.router import InferenceRouter
from backend.workflows.budget import WorkflowBudget
from backend.workflows.contracts import ArtifactRef
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict


@dataclass(frozen=True, slots=True)
class WorkflowExecution:
    workflow_id: str
    artifact: ArtifactRef
    state: str


def _result_payload(result: Any) -> dict[str, Any]:
    """Create a JSON-safe terminal payload without prompt/provider error bodies."""
    return {
        "output": {"text": result.output.text},
        "reasoning": (
            {"text": result.reasoning.text} if result.reasoning is not None else None
        ),
        "finish_reason": result.finish_reason.value,
        "usage": asdict(result.usage),
        "timing": asdict(result.timing),
        "provenance": asdict(result.provenance),
        "attempts": [serialize_attempt(attempt) for attempt in result.attempts],
    }


class WorkflowExecutor:
    """Offline single-task dispatcher bound to one store claim and one budget."""

    def __init__(self, store: SQLiteWorkflowStore, router: InferenceRouter) -> None:
        self.store = store
        self.router = router

    async def execute(
        self,
        tenant: str,
        workflow_id: str,
        owner: str,
        budget: WorkflowBudget | None = None,
        *,
        lease_seconds: int = 30,
        preferred_engine: str | None = None,
    ) -> WorkflowExecution:
        binding = self.store.get_binding(tenant, workflow_id)
        if binding is not None:
            if budget is not None:
                raise WorkflowConflict("Bound workflow budgets cannot be overridden")
            budget = WorkflowBudget(**binding["budget"])
        if not isinstance(budget, WorkflowBudget):
            raise ValueError("A WorkflowBudget is required")
        fence = self.store.claim(
            tenant, workflow_id, owner, lease_seconds=lease_seconds
        )
        packet = self.store.get_packet(tenant, workflow_id)
        if packet is None:  # Defensive: claim already requires the row.
            raise WorkflowConflict("Workflow disappeared after claim")
        self.store.begin_dispatch(
            tenant,
            workflow_id,
            owner,
            fence,
            {
                "max_attempts": budget.max_attempts,
                "max_output_tokens": budget.max_output_tokens,
                "remaining_seconds_at_dispatch": budget.remaining_seconds(),
                "attempts": budget.attempts,
                "output_tokens": budget.output_tokens,
            },
        )
        try:
            result = await self.router.generate_task(
                packet.task, preferred_engine=preferred_engine, budget=budget
            )
        except InferenceFailure as failure:
            attempts = failure.context.get("execution_attempts", ())
            payload = {
                "failure_code": failure.code,
                "attempts": [serialize_attempt(attempt) for attempt in attempts],
                "budget": {
                    "max_attempts": budget.max_attempts,
                    "attempts": budget.attempts,
                    "output_tokens": budget.output_tokens,
                },
            }
            self.store.record_outcome(
                tenant, workflow_id, owner, fence, payload, succeeded=False
            )
            artifact = self.store.complete(
                tenant, workflow_id, owner, fence, payload, succeeded=False
            )
            return WorkflowExecution(workflow_id, artifact, "failed")

        payload = _result_payload(result)
        payload["budget"] = {
            "max_attempts": budget.max_attempts,
            "attempts": budget.attempts,
            "output_tokens": budget.output_tokens,
        }
        self.store.record_outcome(
            tenant, workflow_id, owner, fence, payload, succeeded=True
        )
        artifact = self.store.complete(
            tenant, workflow_id, owner, fence, payload, succeeded=True
        )
        return WorkflowExecution(workflow_id, artifact, "awaiting_validation")
