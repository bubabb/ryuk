"""Fenced execution of one ready node in a durable workflow graph."""

from __future__ import annotations

from dataclasses import replace

from backend.audit.deterministic import ValidationPolicy
from backend.inference.attempts import serialize_attempt
from backend.inference.contracts import ChatInput, ChatMessage, ChatRole, TextInput
from backend.inference.errors import InferenceFailure
from backend.inference.router import InferenceRouter
from backend.workflows.contracts import StoredArtifact, TaskPacket, canonical_json
from backend.workflows.executor import WorkflowExecution, _result_payload
from backend.workflows.graph_budget import DurableGraphBudget
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict


def bind_dependency_artifacts(
    packet: TaskPacket,
    dependencies: tuple[tuple[str, StoredArtifact], ...],
) -> TaskPacket:
    if not dependencies:
        return packet
    envelope = canonical_json(
        {
            "schema_version": 1,
            "accepted_dependencies": [
                {
                    "node_id": node_id,
                    "artifact_id": artifact.ref.artifact_id,
                    "sha256": artifact.ref.sha256,
                    "output": artifact.payload().get("output"),
                }
                for node_id, artifact in dependencies
            ],
        }
    )
    marker = "RYUK_ACCEPTED_DEPENDENCIES_JSON:\n" + envelope
    task = packet.task
    if isinstance(task.input, TextInput):
        bound_input: TextInput | ChatInput = TextInput(
            task.input.text + "\n\n" + marker
        )
    else:
        bound_input = ChatInput(
            task.input.messages + (ChatMessage(ChatRole.USER, marker),)
        )
    return TaskPacket(replace(task, input=bound_input))


class GraphNodeExecutor:
    def __init__(self, store: SQLiteWorkflowStore, router: InferenceRouter) -> None:
        self.store = store
        self.router = router

    async def execute(
        self,
        tenant: str,
        graph_id: str,
        node_id: str,
        owner: str,
        policy: ValidationPolicy,
        *,
        lease_seconds: int = 30,
        preferred_engine: str | None = None,
    ) -> WorkflowExecution:
        budget = DurableGraphBudget(self.store, tenant, graph_id)
        fence = self.store.claim_graph_node(
            tenant,
            graph_id,
            node_id,
            owner,
            lease_seconds=lease_seconds,
        )
        packet = self.store.get_graph_node_packet(tenant, graph_id, node_id)
        if packet is None:
            raise WorkflowConflict("Graph node disappeared after claim")
        dependencies = self.store.accepted_dependency_artifacts(
            tenant, graph_id, node_id
        )
        bound = bind_dependency_artifacts(packet, dependencies)
        try:
            result = await self.router.generate_task(
                bound.task,
                preferred_engine=preferred_engine,
                budget=budget,  # type: ignore[arg-type]
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
            artifact = self.store.complete_graph_node(
                tenant,
                graph_id,
                node_id,
                owner,
                fence,
                payload,
                succeeded=False,
            )
            return WorkflowExecution(graph_id, artifact, "failed")
        payload = _result_payload(result)
        payload["budget"] = {
            "max_attempts": budget.max_attempts,
            "attempts": budget.attempts,
            "output_tokens": budget.output_tokens,
        }
        artifact = self.store.complete_graph_node(
            tenant,
            graph_id,
            node_id,
            owner,
            fence,
            payload,
            succeeded=True,
        )
        report = self.store.validate_graph_node(tenant, graph_id, node_id, policy)
        return WorkflowExecution(
            graph_id,
            artifact,
            "succeeded" if report["decision"] == "accepted" else "rejected",
        )
