"""Typed startup recovery orchestration for the offline workflow store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.workflows.store import SQLiteWorkflowStore


@dataclass(frozen=True, slots=True)
class ExpiredWorkflow:
    tenant: str
    workflow_id: str


@dataclass(frozen=True, slots=True)
class ReconciledWorkflow:
    tenant: str
    workflow_id: str
    state: str


@dataclass(frozen=True, slots=True)
class UnresolvedWorkflow:
    tenant: str
    workflow_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class StartupRecoveryReport:
    scanned: int
    expired: tuple[ExpiredWorkflow, ...]
    reconciled: tuple[ReconciledWorkflow, ...]
    unresolved: tuple[UnresolvedWorkflow, ...]


def recover_workflows_at_startup(
    store: SQLiteWorkflowStore,
    *,
    limit: int,
    now: datetime | None = None,
) -> StartupRecoveryReport:
    """Reconcile durable outcomes only; unresolved execution stays uncertain."""
    if not isinstance(store, SQLiteWorkflowStore):
        raise ValueError("Startup recovery requires a SQLiteWorkflowStore")
    raw = store.recover_startup(limit=limit, now=now)
    return StartupRecoveryReport(
        scanned=raw["scanned"],
        expired=tuple(ExpiredWorkflow(**item) for item in raw["expired"]),
        reconciled=tuple(ReconciledWorkflow(**item) for item in raw["reconciled"]),
        unresolved=tuple(UnresolvedWorkflow(**item) for item in raw["unresolved"]),
    )
