"""Explicit, bounded offline lifecycle for queued single-task workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend.workflows.executor import WorkflowExecutor
from backend.workflows.graph_executor import GraphNodeExecutor
from backend.workflows.store import WorkflowConflict
from backend.workflows.validation import validation_policy_from_snapshot


@dataclass(frozen=True, slots=True)
class DispatcherFailure:
    tenant: str
    workflow_id: str
    code: str


@dataclass(frozen=True, slots=True)
class DispatcherSnapshot:
    state: str
    active: int
    dispatched: int
    completed: int
    workflow_conflicts: int
    execution_failures: int
    recent_failures: tuple[DispatcherFailure, ...]


class LocalWorkflowDispatcher:
    """Opt-in local dispatcher; construction and API creation never start it."""

    def __init__(
        self,
        executor: WorkflowExecutor,
        *,
        owner_prefix: str,
        concurrency: int = 1,
        poll_interval_seconds: float = 0.05,
        lease_seconds: int = 30,
        preferred_engine: str | None = None,
    ) -> None:
        if not isinstance(executor, WorkflowExecutor):
            raise ValueError("Dispatcher requires a WorkflowExecutor")
        if not owner_prefix or owner_prefix != owner_prefix.strip():
            raise ValueError("Owner prefix must be nonempty without outer whitespace")
        if type(concurrency) is not int or not 1 <= concurrency <= 64:
            raise ValueError("Concurrency must be between 1 and 64")
        if (
            type(poll_interval_seconds) not in (int, float)
            or isinstance(poll_interval_seconds, bool)
            or not 0.001 <= poll_interval_seconds <= 60
        ):
            raise ValueError("Poll interval must be between 0.001 and 60 seconds")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("Lease must be between 1 and 3600 seconds")
        if preferred_engine is not None and (
            not isinstance(preferred_engine, str) or not preferred_engine.strip()
        ):
            raise ValueError("Preferred engine must be a nonblank string")
        self._executor = executor
        self._owner_prefix = owner_prefix
        self._concurrency = concurrency
        self._poll_interval = float(poll_interval_seconds)
        self._lease_seconds = lease_seconds
        self._preferred_engine = preferred_engine
        self._state = "new"
        self._sequence = 0
        self._dispatched = 0
        self._completed = 0
        self._workflow_conflicts = 0
        self._execution_failures = 0
        self._recent_failures: list[DispatcherFailure] = []
        self._active: set[asyncio.Task[None]] = set()
        self._stop = asyncio.Event()
        self._changed = asyncio.Event()
        self._coordinator: asyncio.Task[None] | None = None

    @property
    def snapshot(self) -> DispatcherSnapshot:
        return DispatcherSnapshot(
            state=self._state,
            active=len(self._active),
            dispatched=self._dispatched,
            completed=self._completed,
            workflow_conflicts=self._workflow_conflicts,
            execution_failures=self._execution_failures,
            recent_failures=tuple(self._recent_failures),
        )

    async def start(self) -> None:
        """Start intake explicitly; a stopped dispatcher cannot be restarted."""
        if self._state != "new":
            raise RuntimeError("Dispatcher can only be started once")
        self._state = "running"
        self._coordinator = asyncio.create_task(
            self._run(), name=f"{self._owner_prefix}:coordinator"
        )
        await asyncio.sleep(0)

    async def stop(self) -> None:
        """Stop new intake and drain already-started executions."""
        if self._state == "new":
            self._state = "stopped"
            return
        if self._state == "stopped":
            return
        self._state = "stopping"
        self._stop.set()
        self._changed.set()
        if self._coordinator is not None:
            await self._coordinator

    async def wait_idle(self) -> None:
        """Wait until this dispatcher has no work and sees no ready workflow."""
        if self._state != "running":
            raise RuntimeError("Dispatcher must be running")
        while True:
            self._reap()
            if not self._active and not self._executor.store.list_ready(1):
                return
            self._changed.clear()
            try:
                await asyncio.wait_for(
                    self._changed.wait(), timeout=self._poll_interval
                )
            except TimeoutError:
                pass

    async def _execute(self, tenant: str, workflow_id: str, owner: str) -> None:
        try:
            await self._executor.execute(
                tenant,
                workflow_id,
                owner,
                lease_seconds=self._lease_seconds,
                preferred_engine=self._preferred_engine,
            )
        except WorkflowConflict:
            self._workflow_conflicts += 1
            self._record_failure(tenant, workflow_id, "workflow_conflict")
        except Exception:
            # Unexpected execution failures stay fenced in workflow state and are
            # operator-visible through this counter; they never stop other work.
            self._execution_failures += 1
            self._record_failure(tenant, workflow_id, "unexpected_execution_failure")
        else:
            self._completed += 1
        finally:
            self._changed.set()

    def _record_failure(self, tenant: str, workflow_id: str, code: str) -> None:
        self._recent_failures.append(DispatcherFailure(tenant, workflow_id, code))
        del self._recent_failures[:-100]

    def _reap(self) -> None:
        self._active = {task for task in self._active if not task.done()}

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._reap()
                slots = self._concurrency - len(self._active)
                if slots:
                    for tenant, workflow_id in self._executor.store.list_ready(slots):
                        if self._stop.is_set():
                            break
                        self._sequence += 1
                        owner = f"{self._owner_prefix}:{self._sequence}"
                        task = asyncio.create_task(
                            self._execute(tenant, workflow_id, owner),
                            name=f"{owner}:{workflow_id}",
                        )
                        self._active.add(task)
                        self._dispatched += 1
                        self._changed.set()
                if self._active:
                    await asyncio.wait(
                        self._active,
                        timeout=self._poll_interval,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                else:
                    self._changed.clear()
                    try:
                        await asyncio.wait_for(
                            self._changed.wait(), timeout=self._poll_interval
                        )
                    except TimeoutError:
                        pass
        finally:
            if self._active:
                await asyncio.gather(*self._active, return_exceptions=True)
            self._reap()
            self._state = "stopped"
            self._changed.set()


class LocalGraphDispatcher:
    """Explicit bounded dispatcher for ready graph nodes; never auto-started."""

    def __init__(
        self,
        executor: GraphNodeExecutor,
        *,
        owner_prefix: str,
        concurrency: int = 1,
        poll_interval_seconds: float = 0.05,
        lease_seconds: int = 30,
    ) -> None:
        if not isinstance(executor, GraphNodeExecutor):
            raise ValueError("Graph dispatcher requires a GraphNodeExecutor")
        if not owner_prefix or owner_prefix != owner_prefix.strip():
            raise ValueError("Owner prefix must be canonical nonblank text")
        if type(concurrency) is not int or not 1 <= concurrency <= 64:
            raise ValueError("Concurrency must be between 1 and 64")
        if not 0.001 <= poll_interval_seconds <= 60:
            raise ValueError("Poll interval must be between 0.001 and 60 seconds")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("Lease must be between 1 and 3600 seconds")
        self._executor = executor
        self._owner_prefix = owner_prefix
        self._concurrency = concurrency
        self._poll_interval = float(poll_interval_seconds)
        self._lease_seconds = lease_seconds
        self._state = "new"
        self._sequence = 0
        self._active: set[asyncio.Task[None]] = set()
        self._stop = asyncio.Event()
        self._changed = asyncio.Event()
        self._coordinator: asyncio.Task[None] | None = None
        self._dispatched = 0
        self._completed = 0
        self._workflow_conflicts = 0
        self._execution_failures = 0
        self._recent_failures: list[DispatcherFailure] = []

    @property
    def snapshot(self) -> DispatcherSnapshot:
        return DispatcherSnapshot(
            self._state,
            len(self._active),
            self._dispatched,
            self._completed,
            self._workflow_conflicts,
            self._execution_failures,
            tuple(self._recent_failures),
        )

    async def start(self) -> None:
        if self._state != "new":
            raise RuntimeError("Dispatcher can only be started once")
        self._state = "running"
        self._coordinator = asyncio.create_task(self._run())
        await asyncio.sleep(0)

    async def stop(self) -> None:
        if self._state == "new":
            self._state = "stopped"
            return
        if self._state == "stopped":
            return
        self._state = "stopping"
        self._stop.set()
        self._changed.set()
        if self._coordinator is not None:
            await self._coordinator

    async def wait_idle(self) -> None:
        if self._state != "running":
            raise RuntimeError("Dispatcher must be running")
        while True:
            self._reap()
            if not self._active and not self._executor.store.list_ready_graph_nodes(1):
                return
            self._changed.clear()
            try:
                await asyncio.wait_for(
                    self._changed.wait(), timeout=self._poll_interval
                )
            except TimeoutError:
                pass

    async def _execute(
        self, tenant: str, graph_id: str, node_id: str, owner: str
    ) -> None:
        try:
            binding = self._executor.store.get_graph_binding(tenant, graph_id)
            if binding is None:
                raise WorkflowConflict("Graph has no bound validation policy")
            policy = validation_policy_from_snapshot(binding["policy"])
            await self._executor.execute(
                tenant,
                graph_id,
                node_id,
                owner,
                policy,
                lease_seconds=self._lease_seconds,
            )
        except WorkflowConflict:
            self._workflow_conflicts += 1
            self._record_failure(tenant, graph_id, "workflow_conflict")
        except Exception:
            self._execution_failures += 1
            self._record_failure(tenant, graph_id, "unexpected_execution_failure")
        else:
            self._completed += 1
        finally:
            self._changed.set()

    def _record_failure(self, tenant: str, graph_id: str, code: str) -> None:
        self._recent_failures.append(DispatcherFailure(tenant, graph_id, code))
        del self._recent_failures[:-100]

    def _reap(self) -> None:
        self._active = {task for task in self._active if not task.done()}

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._reap()
                slots = self._concurrency - len(self._active)
                if slots:
                    for (
                        tenant,
                        graph_id,
                        node_id,
                    ) in self._executor.store.list_ready_graph_nodes(slots):
                        if self._stop.is_set():
                            break
                        self._sequence += 1
                        owner = f"{self._owner_prefix}:{self._sequence}"
                        task = asyncio.create_task(
                            self._execute(tenant, graph_id, node_id, owner)
                        )
                        self._active.add(task)
                        self._dispatched += 1
                if self._active:
                    await asyncio.wait(
                        self._active,
                        timeout=self._poll_interval,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                else:
                    self._changed.clear()
                    try:
                        await asyncio.wait_for(
                            self._changed.wait(), timeout=self._poll_interval
                        )
                    except TimeoutError:
                        pass
        finally:
            if self._active:
                await asyncio.gather(*self._active, return_exceptions=True)
            self._reap()
            self._state = "stopped"
            self._changed.set()
