import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.audit.deterministic import ValidationPolicy
from backend.inference.advanced import JSONSchemaConstraint
from backend.workflows.store import SQLiteWorkflowStore, WorkflowConflict
from tests.test_workflow_store import packet


@pytest.fixture
def store(tmp_path):
    value = SQLiteWorkflowStore(tmp_path / "validation.db")
    yield value
    value.close()


def completed(store, text="Summary: synthetic result", key="key", succeeded=True):
    workflow = store.create("a", key, packet())
    fence = store.claim("a", workflow, "worker")
    ref = store.complete(
        "a", workflow, "worker", fence, {"output": {"text": text}}, succeeded=succeeded
    )
    return workflow, ref


def test_acceptance_requires_validation_and_replay_is_immutable(store):
    workflow, ref = completed(store)
    assert store.get("a", workflow)["state"] == "awaiting_validation"
    policy = ValidationPolicy(required_sections=("Summary:",), minimum_chars=5)
    report = store.validate("a", workflow, policy)
    assert report["decision"] == "accepted"
    assert report["artifact"] == {"artifact_id": ref.artifact_id, "sha256": ref.sha256}
    assert store.get("a", workflow)["state"] == "succeeded"
    assert store.get("a", workflow)["validation"] == report
    assert store.validate("a", workflow, policy) == report
    assert [e["state"] for e in store.events("a", workflow)] == [
        "ready",
        "running",
        "awaiting_validation",
        "succeeded",
    ]
    report["policy"]["minimum_chars"] = 0
    assert store.get("a", workflow)["validation"]["policy"]["minimum_chars"] == 5
    with pytest.raises(WorkflowConflict):
        store.validate("a", workflow, ValidationPolicy())


@pytest.mark.parametrize(
    "policy,text,kind",
    [
        (
            ValidationPolicy(required_sections=("Conclusion",)),
            "Summary",
            "required_section",
        ),
        (ValidationPolicy(minimum_chars=20), "short", "length"),
        (ValidationPolicy(maximum_chars=2), "long", "length"),
        (ValidationPolicy(forbidden_phrases=("blocked",)), "BLOCKED", "policy"),
        (ValidationPolicy(require_citations=True), "no citation", "citation"),
        (ValidationPolicy(language="ascii"), "résumé", "language"),
        (ValidationPolicy(), "sk-0123456789abcdef", "secret"),
        (ValidationPolicy(), "", "schema"),
        (ValidationPolicy(), None, "schema"),
    ],
)
def test_rejected_output_never_becomes_success(store, policy, text, kind):
    workflow, _ = completed(store, text)
    report = store.validate("a", workflow, policy)
    assert report["decision"] == "rejected"
    assert report["findings"][0]["kind"] == kind
    assert store.get("a", workflow)["state"] == "rejected"
    assert store.validate("a", workflow, policy) == report
    with pytest.raises(WorkflowConflict):
        store.claim("a", workflow, "worker")
    with pytest.raises(WorkflowConflict):
        store.complete("a", workflow, "worker", 1, {}, succeeded=True)


def schema_policy():
    return ValidationPolicy(
        output_schema=JSONSchemaConstraint(
            {
                "type": "object",
                "properties": {"count": {"type": "integer"}},
                "required": ["count"],
                "additionalProperties": False,
            }
        )
    )


@pytest.mark.parametrize(
    "text,accepted",
    [
        ('{"count": 2}', True),
        ('{"count": true}', False),
        ("{}", False),
        ('{"count": 2, "extra": 3}', False),
        ("not json", False),
        ('{"count": NaN}', False),
        ('{"count": 1e999}', False),
        ('{"count": 1, "count": 2}', False),
    ],
)
def test_schema_validation(store, text, accepted):
    workflow, _ = completed(store, text)
    report = store.validate("a", workflow, schema_policy())
    assert (report["decision"] == "accepted") is accepted


def test_validation_is_tenant_scoped_and_checks_artifact_integrity(store, tmp_path):
    workflow, _ = completed(store)
    with pytest.raises(WorkflowConflict):
        store.validate("b", workflow, ValidationPolicy())
    assert store.get("b", workflow) is None
    with sqlite3.connect(tmp_path / "validation.db") as db:
        db.execute("UPDATE workflow_artifacts SET content_json='{}'")
    with pytest.raises(ValueError, match="integrity"):
        store.validate("a", workflow, ValidationPolicy())
    assert store.events("a", workflow)[-1]["state"] == "awaiting_validation"


def test_validation_error_and_commit_failure_leave_result_unaccepted(
    store, monkeypatch
):
    workflow, _ = completed(store)
    import backend.workflows.store as module

    def fail(*args):
        raise RuntimeError("injected")

    for target in ("validator", "event"):
        with monkeypatch.context() as patch:
            if target == "validator":
                patch.setattr(module, "validate_artifact", fail)
            else:
                patch.setattr(store, "_event", fail)
            with pytest.raises(RuntimeError):
                store.validate("a", workflow, ValidationPolicy())
        saved = store.get("a", workflow)
        assert saved["state"] == "awaiting_validation"
        assert saved["validation"] is None
        assert len(store.events("a", workflow)) == 3
    assert store.validate("a", workflow, ValidationPolicy())["decision"] == "accepted"


def test_failed_and_cancelled_results_cannot_be_accepted(store):
    failed, _ = completed(store, key="failed", succeeded=False)
    cancelled, _ = completed(store, key="cancelled")
    assert store.cancel("a", cancelled)
    ready = store.create("a", "ready", packet())
    for workflow in (failed, cancelled, ready):
        with pytest.raises(WorkflowConflict):
            store.validate("a", workflow, ValidationPolicy())


def test_restart_and_concurrent_validation_commit_one_decision(tmp_path):
    path = tmp_path / "race.db"
    first = SQLiteWorkflowStore(path)
    workflow, _ = completed(first)
    first.close()
    first, second = SQLiteWorkflowStore(path), SQLiteWorkflowStore(path)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reports = list(
                pool.map(
                    lambda store: store.validate("a", workflow, ValidationPolicy()),
                    (first, second),
                )
            )
        assert reports[0] == reports[1]
        assert len(first.events("a", workflow)) == 4
    finally:
        first.close()
        second.close()
    reopened = SQLiteWorkflowStore(path)
    try:
        assert reopened.validate("a", workflow, ValidationPolicy()) == reports[0]
    finally:
        reopened.close()


def test_v2_success_is_migrated_to_unaccepted_and_migration_rolls_back(
    tmp_path, monkeypatch
):
    path = tmp_path / "migration.db"
    store = SQLiteWorkflowStore(path)
    workflow, ref = completed(store)
    store.close()
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE workflow_validations")
        db.execute("UPDATE workflow_schema SET version=2")
        db.execute("UPDATE workflows SET state='succeeded'")
    with monkeypatch.context() as patch:

        def fail(*args):
            raise RuntimeError("migration failure")

        patch.setattr(SQLiteWorkflowStore, "_event", fail)
        with pytest.raises(RuntimeError):
            SQLiteWorkflowStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version FROM workflow_schema").fetchone()[0] == 2
        assert db.execute("SELECT state FROM workflows").fetchone()[0] == "succeeded"
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name='workflow_validations'"
        ).fetchall()
    store = SQLiteWorkflowStore(path)
    try:
        row = store.get("a", workflow)
        assert row is not None
        assert row["state"] == "awaiting_validation"
        assert row["result_artifact_id"] == ref.artifact_id
        assert row["validation"] is None
        assert (
            store.validate("a", workflow, ValidationPolicy())["decision"] == "accepted"
        )
    finally:
        store.close()


def test_unsupported_policy_cannot_silently_accept(store):
    workflow, _ = completed(store)
    for policy in (
        ValidationPolicy(language="unknown"),
        ValidationPolicy(
            output_schema=JSONSchemaConstraint(
                {"type": "object", "properties": {}, "oneOf": []}
            )
        ),
    ):
        with pytest.raises(ValueError):
            store.validate("a", workflow, policy)
    assert store.get("a", workflow)["state"] == "awaiting_validation"
