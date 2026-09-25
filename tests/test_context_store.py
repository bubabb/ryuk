from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.context import (
    ContextAccessDenied,
    ContextBuilder,
    ContextConflict,
    ContextIntegrityError,
    ContextPolicyUnavailable,
    ContextPrincipal,
    ContextScope,
    ContextSegment,
    ContextSourceRef,
    ContextTrust,
    SQLiteContextStore,
)
from backend.inference.contracts import ChatRole


@pytest.fixture
def context_store(tmp_path: Path):
    store = SQLiteContextStore(tmp_path / "context.sqlite3")
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def actors():
    return {
        "owner": ContextPrincipal("tenant-a", "user-a", frozenset({"project-a"})),
        "member": ContextPrincipal("tenant-a", "user-b", frozenset({"project-a"})),
        "other_project": ContextPrincipal(
            "tenant-a", "user-c", frozenset({"project-b"})
        ),
        "both_projects": ContextPrincipal(
            "tenant-a", "user-a", frozenset({"project-a", "project-b"})
        ),
        "other_tenant": ContextPrincipal(
            "tenant-b", "user-a", frozenset({"project-a"})
        ),
    }


def test_project_and_user_scoped_conversations_enforce_owner_and_membership(
    context_store, actors
):
    project = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.PROJECT
    )
    private = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.USER
    )
    assert context_store.get_conversation(actors["member"], project.conversation_id)
    assert (
        context_store.get_conversation(actors["member"], private.conversation_id)
        is None
    )
    assert (
        context_store.get_conversation(actors["other_project"], project.conversation_id)
        is None
    )
    assert (
        context_store.get_conversation(actors["other_tenant"], project.conversation_id)
        is None
    )
    with pytest.raises(ContextAccessDenied):
        context_store.append_message(
            actors["other_project"], project.conversation_id, ChatRole.USER, "private"
        )


def test_source_revisions_are_immutable_and_owner_or_project_scoped(
    context_store, actors
):
    private_source = context_store.add_source(
        actors["owner"],
        project_id="project-a",
        source_id="private-source",
        revision="r1",
        role=ChatRole.USER,
        trust=ContextTrust.USER,
        content="owner-only source",
    )
    project_source = context_store.add_source(
        actors["owner"],
        project_id="project-a",
        source_id="project-source",
        revision="r1",
        role=ChatRole.USER,
        trust=ContextTrust.SOURCE,
        content="shared source",
        scope=ContextScope.PROJECT,
    )
    assert (
        context_store.add_source(
            actors["owner"],
            project_id="project-a",
            source_id="project-source",
            revision="r1",
            role=ChatRole.USER,
            trust=ContextTrust.SOURCE,
            content="shared source",
            scope=ContextScope.PROJECT,
        )
        == project_source
    )
    with pytest.raises(ContextConflict):
        context_store.add_source(
            actors["owner"],
            project_id="project-a",
            source_id="project-source",
            revision="r1",
            role=ChatRole.USER,
            trust=ContextTrust.SOURCE,
            content="altered bytes",
            scope=ContextScope.PROJECT,
        )
    conversation = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.PROJECT
    )
    with pytest.raises(ContextAccessDenied):
        context_store.attach_source(
            actors["owner"], conversation.conversation_id, private_source
        )
    context_store.attach_source(
        actors["member"], conversation.conversation_id, project_source
    )
    messages = context_store.recent_messages(
        actors["member"], conversation.conversation_id, limit=5, priority=10
    )
    assert [message.content for message in messages] == ["shared source"]


def test_resolution_authorizes_all_sources_before_returning_any_content(
    context_store, actors, monkeypatch
):
    conversation = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.PROJECT
    )
    source = context_store.add_source(
        actors["owner"],
        project_id="project-a",
        revision="r1",
        role=ChatRole.USER,
        trust=ContextTrust.SOURCE,
        content="allowed content",
        scope=ContextScope.PROJECT,
    )
    outside = context_store.add_source(
        actors["both_projects"],
        project_id="project-b",
        revision="r1",
        role=ChatRole.USER,
        trust=ContextTrust.SOURCE,
        content="must not be returned",
        scope=ContextScope.PROJECT,
        source_id="outside-project",
    )
    called = False

    def unexpected_content_read(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("source content was read before authorization completed")

    monkeypatch.setattr(
        SQLiteContextStore, "_as_segment", staticmethod(unexpected_content_read)
    )
    with pytest.raises(ContextAccessDenied):
        context_store.resolve_sources(
            actors["owner"], conversation.conversation_id, (source, outside)
        )
    assert not called


def test_context_builder_orders_policy_objective_recent_history_and_sources(
    context_store, actors
):
    conversation = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.PROJECT
    )
    objective = context_store.add_source(
        actors["owner"],
        project_id="project-a",
        source_id="objective",
        revision="r1",
        role=ChatRole.USER,
        trust=ContextTrust.USER,
        content="Complete the synthetic objective.",
        scope=ContextScope.PROJECT,
    )
    evidence = context_store.add_source(
        actors["owner"],
        project_id="project-a",
        source_id="evidence",
        revision="r3",
        role=ChatRole.USER,
        trust=ContextTrust.SOURCE,
        content="Public synthetic evidence.",
        scope=ContextScope.PROJECT,
    )
    context_store.append_message(
        actors["owner"], conversation.conversation_id, ChatRole.USER, "First turn"
    )
    context_store.append_message(
        actors["owner"], conversation.conversation_id, ChatRole.ASSISTANT, "Reply"
    )
    policy = ContextSegment(
        "trusted-policy",
        "policy-v2",
        ChatRole.SYSTEM,
        "Follow project safety rules.",
        ContextTrust.POLICY,
        required=True,
    )
    builder = ContextBuilder(context_store, {("tenant-a", "project-a"): (policy,)})
    built = builder.build(
        actors["member"],
        conversation.conversation_id,
        (
            ContextSourceRef(objective.source_id, objective.revision, required=True),
            ContextSourceRef(
                evidence.source_id, evidence.revision, required=False, priority=7
            ),
        ),
        recent_message_limit=2,
    )
    assert built.tenant_id == "tenant-a" and built.project_id == "project-a"
    assert [segment.content for segment in built.segments] == [
        "Follow project safety rules.",
        "Complete the synthetic objective.",
        "First turn",
        "Reply",
        "Public synthetic evidence.",
    ]
    assert built.segments[0].role is ChatRole.SYSTEM
    assert built.segments[1].required
    assert built.segments[-1].priority == 7


def test_builder_fails_closed_for_missing_policy_or_foreign_source(
    context_store, actors
):
    conversation = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.PROJECT
    )
    source = context_store.add_source(
        actors["owner"],
        project_id="project-a",
        revision="r1",
        role=ChatRole.USER,
        trust=ContextTrust.SOURCE,
        content="scoped content",
        scope=ContextScope.PROJECT,
        source_id="scoped",
    )
    selection = (ContextSourceRef(source.source_id, source.revision, required=True),)
    with pytest.raises(ContextPolicyUnavailable):
        ContextBuilder(context_store, {}).build(
            actors["owner"], conversation.conversation_id, selection
        )
    policy = ContextSegment(
        "policy",
        "r1",
        ChatRole.SYSTEM,
        "Policy",
        ContextTrust.POLICY,
        required=True,
    )
    builder = ContextBuilder(context_store, {("tenant-a", "project-a"): (policy,)})
    with pytest.raises(ContextAccessDenied, match="not accessible"):
        builder.build(actors["other_project"], conversation.conversation_id, selection)


def test_private_conversation_does_not_bypass_revoked_project_membership(
    context_store, actors
):
    conversation = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.USER
    )
    source = context_store.add_source(
        actors["owner"],
        project_id="project-a",
        source_id="owner-objective",
        revision="r1",
        role=ChatRole.USER,
        trust=ContextTrust.USER,
        content="owner's private objective",
    )
    policy = ContextSegment(
        "policy",
        "r1",
        ChatRole.SYSTEM,
        "Project policy",
        ContextTrust.POLICY,
        required=True,
    )
    builder = ContextBuilder(context_store, {("tenant-a", "project-a"): (policy,)})
    revoked_actor = ContextPrincipal("tenant-a", "user-a", frozenset())
    # The private conversation itself remains owner-readable, but project
    # membership is required to build a project-policy context from it.
    assert (
        context_store.get_conversation(revoked_actor, conversation.conversation_id)
        is not None
    )
    with pytest.raises(ContextAccessDenied):
        builder.build(
            revoked_actor,
            conversation.conversation_id,
            (ContextSourceRef(source.source_id, source.revision, required=True),),
        )


def test_restart_preserves_messages_and_source_linkage(tmp_path: Path, actors):
    path = tmp_path / "context-restart.sqlite3"
    first = SQLiteContextStore(path)
    conversation = first.create_conversation(
        actors["owner"], "project-a", ContextScope.USER
    )
    first.append_message(
        actors["owner"], conversation.conversation_id, ChatRole.USER, "one"
    )
    first.append_message(
        actors["owner"], conversation.conversation_id, ChatRole.ASSISTANT, "two"
    )
    first.append_message(
        actors["owner"], conversation.conversation_id, ChatRole.USER, "three"
    )
    first.close()

    reopened = SQLiteContextStore(path)
    try:
        record = reopened.get_conversation(
            actors["owner"], conversation.conversation_id
        )
        recent = reopened.recent_messages(
            actors["owner"], conversation.conversation_id, limit=2, priority=4
        )
    finally:
        reopened.close()
    assert record is not None
    assert [segment.content for segment in recent] == ["two", "three"]
    assert all(segment.source_revision == "1" for segment in recent)


def test_cross_connection_message_appends_receive_unique_order(tmp_path: Path, actors):
    path = tmp_path / "context-concurrent.sqlite3"
    first = SQLiteContextStore(path)
    second = SQLiteContextStore(path)
    conversation = first.create_conversation(
        actors["owner"], "project-a", ContextScope.USER
    )

    def append(index: int) -> None:
        (first if index % 2 else second).append_message(
            actors["owner"],
            conversation.conversation_id,
            ChatRole.USER,
            f"turn-{index}",
        )

    try:
        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(append, range(16)))
        recent = first.recent_messages(
            actors["owner"], conversation.conversation_id, limit=20, priority=0
        )
    finally:
        first.close()
        second.close()
    assert len(recent) == 16
    assert {segment.content for segment in recent} == {f"turn-{i}" for i in range(16)}


def test_source_checksum_is_verified_before_context_content_is_returned(
    context_store, actors
):
    conversation = context_store.create_conversation(
        actors["owner"], "project-a", ContextScope.USER
    )
    source = context_store.append_message(
        actors["owner"], conversation.conversation_id, ChatRole.USER, "original"
    )
    with context_store._transaction():
        context_store._db.execute(
            "UPDATE context_sources SET content='corrupted' WHERE tenant_id=? "
            "AND source_id=? AND revision=?",
            (actors["owner"].tenant_id, source.source_id, source.revision),
        )
    with pytest.raises(ContextIntegrityError):
        context_store.recent_messages(
            actors["owner"], conversation.conversation_id, limit=1, priority=0
        )
