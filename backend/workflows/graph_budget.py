"""Durable budget adapter shared by every execution in one workflow graph."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict


class DurableGraphBudget:
    def __init__(self, store: SQLiteWorkflowStore, tenant: str, graph_id: str) -> None:
        self.store = store
        self.tenant = tenant
        self.graph_id = graph_id
        if store.get_graph_budget(tenant, graph_id) is None:
            raise WorkflowConflict("Graph budget is not bound")

    def _snapshot(self) -> dict[str, Any]:
        value = self.store.get_graph_budget(self.tenant, self.graph_id)
        if value is None:
            raise WorkflowConflict("Graph budget is not bound")
        return value

    @property
    def max_attempts(self) -> int:
        return int(self._snapshot()["max_attempts"])

    @property
    def max_output_tokens(self) -> int | None:
        value = self._snapshot()["max_output_tokens"]
        return None if value is None else int(value)

    @property
    def attempts(self) -> int:
        return int(self._snapshot()["attempts"])

    @property
    def output_tokens(self) -> int:
        return int(self._snapshot()["output_tokens"])

    def remaining_seconds(self) -> float:
        deadline = datetime.fromisoformat(str(self._snapshot()["deadline_at"]))
        return max(0.0, (deadline - datetime.now(UTC)).total_seconds())

    def reserve_attempt(self) -> bool:
        return self.store.reserve_graph_attempt(self.tenant, self.graph_id)

    def record_output_tokens(self, count: int | None) -> bool:
        return self.store.record_graph_output_tokens(self.tenant, self.graph_id, count)
