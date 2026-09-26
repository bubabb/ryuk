"""Governed offline multi-step workflow graph management routes."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.control.api import ControlPlaneFailure
from backend.control.security import Principal
from backend.inference.contracts import (
    GenerationConfig,
    InferenceTask,
    TaskRequirements,
    TextInput,
    TraceContext,
)
from backend.workflows.contracts import TaskPacket, canonical_json
from backend.workflows.governance import WorkflowPolicy
from backend.workflows.graph import GraphNode, NodeState, WorkflowGraph
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict


class CreateGraphNodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    node_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=100_000)
    model: str = Field(min_length=1, max_length=256)
    max_tokens: int = Field(ge=1, le=32768)
    temperature: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)
    depends_on: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("node_id", "prompt", "model")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @field_validator("node_id")
    @classmethod
    def clean_id(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Node ID must not have outer whitespace")
        return value

    @field_validator("depends_on")
    @classmethod
    def clean_dependencies(cls, value: list[str]) -> list[str]:
        if any(not item or item != item.strip() for item in value):
            raise ValueError("Dependencies must be canonical node IDs")
        if len(set(value)) != len(value):
            raise ValueError("Dependencies must be unique")
        return value


class CreateWorkflowGraphRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    idempotency_key: str = Field(min_length=1, max_length=128)
    nodes: list[CreateGraphNodeRequest] = Field(min_length=1, max_length=100)

    @field_validator("idempotency_key")
    @classmethod
    def clean_key(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("Key must be canonical nonblank text")
        return value


def build_workflow_graph_router(
    principal_dependency: Callable[..., Principal],
    get_store: Callable[[], SQLiteWorkflowStore | None],
    get_policies: Callable[[], dict[str, WorkflowPolicy]],
    admit: Callable[..., Any],
    record: Callable[..., None],
    get_input_limits: Callable[[], tuple[int, int]],
) -> APIRouter:
    router = APIRouter(prefix="/v1/workflow-graphs", tags=["workflow-graphs"])
    authorized = Depends(principal_dependency)

    @contextmanager
    def operation(
        request: Request, principal: Principal, name: str, tokens: int = 0
    ) -> Iterator[SQLiteWorkflowStore]:
        permit = admit(request, principal, name, tokens)
        status = "failed"
        try:
            store = get_store()
            if store is None:
                raise ControlPlaneFailure(
                    503, "workflows_disabled", "Offline workflows are not enabled."
                )
            yield store
            status = "accepted"
        except WorkflowConflict:
            raise ControlPlaneFailure(
                409,
                "workflow_graph_conflict",
                "Workflow graph operation conflicts with saved state.",
            ) from None
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            raise ControlPlaneFailure(
                503,
                "workflow_store_unavailable",
                "Workflow graph state could not be verified.",
            ) from None
        finally:
            permit.release()
            record(request, principal, name, status)

    def saved_graph(store: SQLiteWorkflowStore, principal: Principal, graph_id: str):
        if store.get_graph_binding(principal.tenant_id, graph_id) is None:
            raise ControlPlaneFailure(
                404, "workflow_graph_not_found", "Graph not found."
            )
        state = store.get_graph_state(principal.tenant_id, graph_id)
        if state is None:
            raise ControlPlaneFailure(
                404, "workflow_graph_not_found", "Graph not found."
            )
        return state

    def summary(store: SQLiteWorkflowStore, tenant: str, graph_id: str):
        state = store.get_graph_state(tenant, graph_id)
        assert state is not None
        states = dict(state.node_states)
        aggregate = "active"
        if state.terminal:
            aggregate = (
                "succeeded"
                if all(value is NodeState.SUCCEEDED for value in states.values())
                else "completed_with_failures"
            )
        return {
            "graph_id": graph_id,
            "state": aggregate,
            "terminal": state.terminal,
            "nodes": [
                {"node_id": node_id, "state": node_state.value}
                for node_id, node_state in state.node_states
            ],
        }

    @router.post("", status_code=202)
    async def create(
        payload: CreateWorkflowGraphRequest,
        request: Request,
        principal: Principal = authorized,
    ):
        policy = get_policies().get(principal.tenant_id)
        tokens = policy.budget.max_output_tokens if policy else 0
        with operation(request, principal, "workflow_graph.create", tokens) as store:
            if policy is None:
                raise ControlPlaneFailure(
                    403, "workflow_policy_required", "No authorized workflow policy."
                )
            prompt_limit, token_limit = get_input_limits()
            if any(
                len(node.prompt) > prompt_limit
                or node.max_tokens > min(policy.budget.max_output_tokens, token_limit)
                for node in payload.nodes
            ):
                raise ControlPlaneFailure(
                    422,
                    "workflow_limit_exceeded",
                    "Workflow graph input exceeds configured limits.",
                )
            graph_nodes = []
            for node in sorted(payload.nodes, key=lambda item: item.node_id):
                trace_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        canonical_json(
                            [
                                principal.tenant_id,
                                payload.idempotency_key,
                                node.node_id,
                            ]
                        ),
                    )
                )
                graph_nodes.append(
                    GraphNode(
                        node.node_id,
                        TaskPacket(
                            InferenceTask(
                                TextInput(node.prompt),
                                GenerationConfig(node.max_tokens, node.temperature),
                                TaskRequirements(requested_model=node.model),
                                TraceContext(trace_id),
                            )
                        ),
                        tuple(sorted(node.depends_on)),
                    )
                )
            try:
                graph = WorkflowGraph(tuple(graph_nodes))
            except ValueError:
                raise ControlPlaneFailure(
                    422, "invalid_workflow_graph", "Workflow graph is invalid."
                ) from None
            graph_id = store.create_graph(
                principal.tenant_id,
                payload.idempotency_key,
                graph,
                budget=(
                    policy.budget.deadline_seconds,
                    policy.budget.max_attempts,
                    policy.budget.max_output_tokens,
                ),
                binding=policy.binding(),
            )
            return summary(store, principal.tenant_id, graph_id)

    @router.get("/{graph_id}")
    async def status(
        graph_id: str, request: Request, principal: Principal = authorized
    ):
        with operation(request, principal, "workflow_graph.status") as store:
            saved_graph(store, principal, graph_id)
            return summary(store, principal.tenant_id, graph_id)

    @router.post("/{graph_id}/cancel")
    async def cancel(
        graph_id: str, request: Request, principal: Principal = authorized
    ):
        with operation(request, principal, "workflow_graph.cancel") as store:
            saved_graph(store, principal, graph_id)
            store.cancel_graph(principal.tenant_id, graph_id)
            return summary(store, principal.tenant_id, graph_id)

    @router.get("/{graph_id}/result")
    async def result(
        graph_id: str, request: Request, principal: Principal = authorized
    ):
        with operation(request, principal, "workflow_graph.result") as store:
            saved_graph(store, principal, graph_id)
            results = store.accepted_graph_results(principal.tenant_id, graph_id)
            return {
                **summary(store, principal.tenant_id, graph_id),
                "results": [
                    {
                        "node_id": node_id,
                        "artifact": artifact.payload(),
                        "validation": validation,
                    }
                    for node_id, artifact, validation in results
                ],
            }

    return router
