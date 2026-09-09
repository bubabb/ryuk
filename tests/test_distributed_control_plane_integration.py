import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from redis import Redis

from backend.control.admission import QuotaPolicy, RedisAdmissionController
from backend.control.records import ExecutionRecord, PostgreSQLExecutionRecordStore


@pytest.mark.integration
def test_real_postgresql_records_are_durable_and_tenant_scoped() -> None:
    database_url = os.getenv("POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("Set POSTGRES_TEST_URL to run PostgreSQL record contracts")
    store = PostgreSQLExecutionRecordStore(database_url)
    request_id = f"integration-{uuid4()}"
    record = ExecutionRecord(
        request_id=request_id,
        tenant_id="integration-tenant-a",
        status="accepted",
        policy_version="integration-v1",
        payload={"safe": True},
        created_at=datetime.now(UTC),
    )
    try:
        store.put(record)
        assert store.get("integration-tenant-a", request_id) == record
        assert store.get("integration-tenant-b", request_id) is None
        assert store.health()["ready"] is True
    finally:
        store.close()

    reopened = PostgreSQLExecutionRecordStore(database_url)
    try:
        assert reopened.get("integration-tenant-a", request_id) == record
        assert reopened.get("integration-tenant-b", request_id) is None
    finally:
        reopened.close()


@pytest.mark.integration
def test_real_redis_admission_is_shared_and_atomic() -> None:
    redis_url = os.getenv("REDIS_TEST_URL")
    if not redis_url:
        pytest.skip("Set REDIS_TEST_URL to run distributed admission contracts")
    tenant_id = f"integration-{uuid4()}"
    policy = {tenant_id: QuotaPolicy(10, 1, 100)}
    first = RedisAdmissionController(policy, redis_url=redis_url)
    second = RedisAdmissionController(policy, redis_url=redis_url)
    try:
        assert first.admit(tenant_id, 10)
        assert not second.admit(tenant_id, 10)
        first.release(tenant_id)
        assert second.admit(tenant_id, 10)
        second.release(tenant_id)
        assert first.health()["ready"] is True
    finally:
        first.close()
        second.close()


@pytest.mark.integration
def test_real_redis_admission_enforces_concurrency_under_contention() -> None:
    redis_url = os.getenv("REDIS_TEST_URL")
    if not redis_url:
        pytest.skip("Set REDIS_TEST_URL to run distributed admission contracts")
    tenant_id = f"integration-contention-{uuid4()}"
    concurrency_limit = 3
    policy = {tenant_id: QuotaPolicy(100, concurrency_limit, 1_000)}
    controllers = [
        RedisAdmissionController(policy, redis_url=redis_url) for _ in range(8)
    ]
    client = Redis.from_url(redis_url, decode_responses=True)
    key = f"ryuk:admission:v1:{tenant_id}"
    try:
        with ThreadPoolExecutor(max_workers=len(controllers)) as executor:
            admitted = list(
                executor.map(
                    lambda controller: controller.admit(tenant_id, 1),
                    controllers,
                )
            )
        assert sum(admitted) == concurrency_limit
        assert client.ttl(key) == -1

        for _ in range(concurrency_limit):
            controllers[0].release(tenant_id)
        assert client.ttl(key) > 0
        assert all(
            controllers[index].admit(tenant_id, 1)
            for index in range(concurrency_limit)
        )
    finally:
        client.delete(key)
        client.close()
        for controller in controllers:
            controller.close()
