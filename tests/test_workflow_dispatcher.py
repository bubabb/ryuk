import asyncio

import pytest

from backend.inference.router import InferenceRouter
from backend.workflows.dispatcher import LocalWorkflowDispatcher
from backend.workflows.executor import WorkflowExecutor
from backend.workflows.store import SQLiteWorkflowStore
from tests.test_execution import ControlledEngine, registry
from tests.test_workflow_store import packet

BOUND = {
    "version": "dispatcher-test-v1",
    "policy": {
        "required_sections": [],
        "forbidden_phrases": [],
        "require_citations": False,
        "minimum_chars": 1,
        "maximum_chars": 100000,
        "language": None,
    },
    "budget": {
        "deadline_seconds": 10.0,
        "max_attempts": 1,
        "max_output_tokens": 64,
    },
}


class BlockingEngine(ControlledEngine):
    def __init__(self):
        super().__init__("blocking")
        self.release = asyncio.Event()
        self.started = asyncio.Event()
        self.active = 0
        self.maximum_active = 0

    async def generate_task(self, inference_task):
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        self.started.set()
        try:
            await self.release.wait()
            return await super().generate_task(inference_task)
        finally:
            self.active -= 1


@pytest.fixture
def store(tmp_path):
    value = SQLiteWorkflowStore(tmp_path / "dispatcher.db")
    yield value
    value.close()


def create(store, key, tenant="a"):
    return store.create(tenant, key, packet(key), binding=BOUND)


@pytest.mark.asyncio
async def test_dispatcher_requires_explicit_start_and_valid_configuration(store):
    workflow = create(store, "one")
    executor = WorkflowExecutor(
        store, InferenceRouter(registry(ControlledEngine("only")))
    )
    dispatcher = LocalWorkflowDispatcher(executor, owner_prefix="local")
    await asyncio.sleep(0.01)
    assert store.get("a", workflow)["state"] == "ready"
    assert dispatcher.snapshot.state == "new"
    await dispatcher.stop()
    assert dispatcher.snapshot.state == "stopped"
    with pytest.raises(RuntimeError, match="started once"):
        await dispatcher.start()
    for kwargs in (
        {"owner_prefix": ""},
        {"owner_prefix": "local", "concurrency": True},
        {"owner_prefix": "local", "concurrency": 0},
        {"owner_prefix": "local", "poll_interval_seconds": 0},
        {"owner_prefix": "local", "lease_seconds": 0},
        {"owner_prefix": "local", "preferred_engine": " "},
    ):
        with pytest.raises(ValueError):
            LocalWorkflowDispatcher(executor, **kwargs)
    with pytest.raises(ValueError):
        store.list_ready(0)


@pytest.mark.asyncio
async def test_dispatcher_enforces_concurrency_across_tenants(store):
    workflows = [
        (tenant, create(store, f"job-{index}", tenant))
        for index, tenant in enumerate(("a", "b", "a", "b"))
    ]
    engine = BlockingEngine()
    dispatcher = LocalWorkflowDispatcher(
        WorkflowExecutor(store, InferenceRouter(registry(engine))),
        owner_prefix="bounded",
        concurrency=2,
        poll_interval_seconds=0.005,
    )
    await dispatcher.start()
    await asyncio.wait_for(engine.started.wait(), timeout=1)
    while engine.active < 2:
        await asyncio.sleep(0)
    assert engine.maximum_active == 2
    running = sum(
        store.get(tenant, item)["state"] == "running" for tenant, item in workflows
    )
    assert running == 2
    engine.release.set()
    await asyncio.wait_for(dispatcher.wait_idle(), timeout=1)
    await dispatcher.stop()
    assert engine.maximum_active == 2
    assert [store.get(tenant, item)["state"] for tenant, item in workflows] == [
        "awaiting_validation"
    ] * 4
    assert dispatcher.snapshot.active == 0
    assert dispatcher.snapshot.dispatched == 4
    assert dispatcher.snapshot.completed == 4
    assert dispatcher.snapshot.state == "stopped"


@pytest.mark.asyncio
async def test_stop_closes_intake_and_drains_only_started_work(store):
    first = create(store, "first")
    engine = BlockingEngine()
    dispatcher = LocalWorkflowDispatcher(
        WorkflowExecutor(store, InferenceRouter(registry(engine))),
        owner_prefix="drain",
        concurrency=1,
        poll_interval_seconds=0.005,
    )
    await dispatcher.start()
    await asyncio.wait_for(engine.started.wait(), timeout=1)
    second = create(store, "second")
    stopping = asyncio.create_task(dispatcher.stop())
    await asyncio.sleep(0)
    assert dispatcher.snapshot.state == "stopping"
    assert not stopping.done()
    engine.release.set()
    await asyncio.wait_for(stopping, timeout=1)
    assert store.get("a", first)["state"] == "awaiting_validation"
    assert store.get("a", second)["state"] == "ready"
    assert dispatcher.snapshot.dispatched == 1
    assert dispatcher.snapshot.completed == 1


@pytest.mark.asyncio
async def test_unexpected_execution_failure_is_isolated_and_visible(store):
    class FirstCrashes(ControlledEngine):
        async def generate_task(self, inference_task):
            if self.calls == 0:
                self.calls += 1
                raise RuntimeError("synthetic crash")
            return await super().generate_task(inference_task)

    first = create(store, "first")
    second = create(store, "second")
    dispatcher = LocalWorkflowDispatcher(
        WorkflowExecutor(
            store, InferenceRouter(registry(FirstCrashes("sometimes")))
        ),
        owner_prefix="isolate",
        concurrency=1,
        poll_interval_seconds=0.005,
    )
    await dispatcher.start()
    await asyncio.wait_for(dispatcher.wait_idle(), timeout=1)
    await dispatcher.stop()
    assert store.get("a", first)["state"] == "running"
    assert store.get("a", second)["state"] == "awaiting_validation"
    assert dispatcher.snapshot.execution_failures == 1
    assert dispatcher.snapshot.completed == 1
    assert [failure.workflow_id for failure in dispatcher.snapshot.recent_failures] == [
        first
    ]
    assert (
        dispatcher.snapshot.recent_failures[0].code
        == "unexpected_execution_failure"
    )
