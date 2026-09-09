# Distributed Control-Plane Foundation Review — 2026-09-09

## Scope and conclusion

Ryuk now has concrete PostgreSQL execution-record and Redis admission
implementations behind its own control-plane interfaces. The implementation is
suitable for continued integration and failure testing. It is not yet evidence
for the Phase 10 production exit gate.

## Correctness evidence

- PostgreSQL records survive store restart and remain tenant-qualified.
- Redis admission is atomic across clients and enforces request, token, and
  concurrency limits.
- A real concurrent Redis test admits exactly the configured number of permits.
- Active Redis permits do not expire on an arbitrary idle-data TTL; idle quota
  state receives bounded retention after the final release.
- Dependency failures reject admission and production startup fails closed.
- Partially initialized pools/coordinators and startup failures close owned
  resources.
- Vault resolution requires HTTPS in production and returns only the requested
  KV field at the adapter boundary.
- Client tenant headers cannot elevate or replace authenticated tenant identity.

## Remaining production gates

- Design permit leases/fencing and crash reconciliation. The current conservative
  behavior can leak capacity after process death, but does not silently reopen it.
- Prove Redis behavior during network partitions and failover.
- Prove PostgreSQL backup, restore, migration concurrency, and required RPO/RTO.
- Add Vault workload authentication plus rotation and revocation drills.
- Add multi-replica load, soak, chaos, observability, and operational runbooks.
- Certify the exact model deployments separately under Phase 2.

## Commands exercised

```text
scripts/local_postgres.sh test
scripts/local_redis.sh test
python -m pytest -q
python -m ruff check backend tests scripts
python -m mypy backend tests scripts
python -m compileall -q backend tests scripts
python -m scripts.evaluate_routing
python -m scripts.evaluate_audit
git diff --check
```
