"""Opt-in offline workflow management; creation never dispatches inference."""

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
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict


class CreateWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    idempotency_key: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=100_000)
    model: str = Field(min_length=1, max_length=256)
    max_tokens: int = Field(ge=1, le=32768)
    temperature: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)

    @field_validator("idempotency_key", "prompt", "model")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def clean_key(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Key must not have outer whitespace")
        return value


def build_workflow_router(
    principal_dependency: Callable[..., Principal],
    get_store: Callable[[], SQLiteWorkflowStore | None],
    get_policies: Callable[[], dict[str, WorkflowPolicy]],
    admit: Callable[..., Any],
    record: Callable[..., None],
    get_input_limits: Callable[[], tuple[int, int]],
) -> APIRouter:
    router = APIRouter(prefix="/v1/workflows", tags=["workflows"])
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
                "workflow_conflict",
                "Workflow operation conflicts with saved state.",
            ) from None
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            raise ControlPlaneFailure(
                503,
                "workflow_store_unavailable",
                "Workflow state could not be verified.",
            ) from None
        finally:
            permit.release()
            record(request, principal, name, status)

    def saved_workflow(
        store: SQLiteWorkflowStore, principal: Principal, workflow_id: str
    ) -> dict[str, Any]:
        # Legacy workflows have no authorized creation binding and are not exposed.
        binding = store.get_binding(principal.tenant_id, workflow_id)
        if binding is None:
            raise ControlPlaneFailure(404, "workflow_not_found", "Workflow not found.")
        row = store.get(principal.tenant_id, workflow_id)
        if row is None:
            raise ControlPlaneFailure(404, "workflow_not_found", "Workflow not found.")
        return row

    def summary(store: SQLiteWorkflowStore, tenant: str, row: dict[str, Any]):
        binding = store.get_binding(tenant, row["id"])
        assert binding is not None
        return {
            "workflow_id": row["id"],
            "state": row["state"],
            "policy_version": binding["version"],
            "result_available": row["state"] == "succeeded",
        }

    @router.post("", status_code=202)
    async def create(
        payload: CreateWorkflowRequest,
        request: Request,
        principal: Principal = authorized,
    ):
        policy = get_policies().get(principal.tenant_id)
        # Admission is still applied to tenants without configured workflow access.
        tokens = payload.max_tokens * policy.budget.max_attempts if policy else 0
        with operation(request, principal, "workflow.create", tokens) as store:
            if policy is None:
                raise ControlPlaneFailure(
                    403, "workflow_policy_required", "No authorized workflow policy."
                )
            prompt_limit, token_limit = get_input_limits()
            if len(payload.prompt) > prompt_limit or payload.max_tokens > min(
                policy.budget.max_output_tokens, token_limit
            ):
                raise ControlPlaneFailure(
                    422,
                    "workflow_limit_exceeded",
                    "Workflow input exceeds configured limits.",
                )
            trace_id = str(
                uuid5(
                    NAMESPACE_URL,
                    canonical_json([principal.tenant_id, payload.idempotency_key]),
                )
            )
            packet = TaskPacket(
                InferenceTask(
                    input=TextInput(payload.prompt),
                    generation=GenerationConfig(
                        max_output_tokens=payload.max_tokens,
                        temperature=payload.temperature,
                    ),
                    requirements=TaskRequirements(requested_model=payload.model),
                    trace=TraceContext(trace_id),
                )
            )
            workflow_id = store.create(
                principal.tenant_id,
                payload.idempotency_key,
                packet,
                binding=policy.binding(),
            )
            row = saved_workflow(store, principal, workflow_id)
            return summary(store, principal.tenant_id, row)

    @router.get("/{workflow_id}")
    async def status(
        workflow_id: str,
        request: Request,
        principal: Principal = authorized,
    ):
        with operation(request, principal, "workflow.status") as store:
            return summary(
                store,
                principal.tenant_id,
                saved_workflow(store, principal, workflow_id),
            )

    @router.post("/{workflow_id}/cancel")
    async def cancel(
        workflow_id: str,
        request: Request,
        principal: Principal = authorized,
    ):
        with operation(request, principal, "workflow.cancel") as store:
            saved_workflow(store, principal, workflow_id)
            if not store.cancel(principal.tenant_id, workflow_id):
                raise WorkflowConflict("Workflow cannot be cancelled")
            return summary(
                store,
                principal.tenant_id,
                saved_workflow(store, principal, workflow_id),
            )

    @router.get("/{workflow_id}/result")
    async def result(
        workflow_id: str,
        request: Request,
        principal: Principal = authorized,
    ):
        with operation(request, principal, "workflow.result") as store:
            row = saved_workflow(store, principal, workflow_id)
            if row["state"] != "succeeded" or row["validation"] is None:
                raise WorkflowConflict("Workflow has no accepted result")
            # Recheck the artifact-bound decision against the immutable bound policy.
            report = store.validate(principal.tenant_id, workflow_id)
            if report["decision"] != "accepted":
                raise WorkflowConflict("Workflow result is not accepted")
            return {
                **summary(store, principal.tenant_id, row),
                "result": row["result"],
                "validation": report,
            }

    return router
