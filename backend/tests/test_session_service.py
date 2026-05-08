from app.ai_runtime.providers.base import ChatCompletionResult
from app.memory.service import MemoryService
from app.memory.store import build_memory_store
from app.schemas.ask import AskCitation
from app.session.adapters.sqlite_store import SQLiteSessionStore
from app.session.service import SessionService
from tests.test_helpers import create_test_user_id


class FakeMemoryChatProvider:
    def generate_response(self, *, system_prompt: str, user_input: str) -> ChatCompletionResult:
        return ChatCompletionResult(
            content="用户询问双碳目标及其对企业低碳转型的影响。",
            metadata={"fake": True, "system_prompt_length": len(system_prompt), "user_input_length": len(user_input)},
        )


def build_session_service(tmp_path) -> SessionService:
    db_path = tmp_path / "carbonrag.sqlite3"
    store = SQLiteSessionStore(db_path)
    memory_service = MemoryService(
        store=build_memory_store(sqlite_db_path=db_path, memory_backend="sqlite"),
        chat_provider=FakeMemoryChatProvider(),  # type: ignore[arg-type]
    )
    return SessionService(store=store, memory_service=memory_service)


def test_session_service_creates_default_title_and_builds_context(tmp_path) -> None:
    service = build_session_service(tmp_path)
    owner_user_id = create_test_user_id(tmp_path / "carbonrag.sqlite3", prefix="session-service")
    session = service.create_session(owner_user_id=owner_user_id)

    assert session.title.startswith("新对话")

    service.record_exchange(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        user_content="What is the dual-carbon target?",
        assistant_content="The dual-carbon target refers to carbon peaking and carbon neutrality.",
        assistant_status="ok",
        trace_id="trace-001",
        citations=[],
    )
    service.record_exchange(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        user_content="What does it mean for enterprises?",
        assistant_content="Enterprises need to understand low-carbon transformation within the policy framework.",
        assistant_status="ok",
        trace_id="trace-002",
        citations=[],
    )

    session_context = service.build_session_context(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        max_turns=1,
        upcoming_user_input="How should I proceed next?",
    )

    assert len(session_context["recent_messages"]) == 2
    assert session_context["recent_messages"][0]["role"] == "user"
    assert session_context["recent_messages"][1]["role"] == "assistant"
    assert session_context["context_budget_estimate"] == 258_000
    assert session_context["compaction_status"] in {"idle", "compacted"}


def test_session_service_promotes_first_question_to_title(tmp_path) -> None:
    service = build_session_service(tmp_path)
    owner_user_id = create_test_user_id(tmp_path / "carbonrag.sqlite3", prefix="session-title")
    session = service.create_session(owner_user_id=owner_user_id)

    service.record_exchange(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        user_content="What is the dual-carbon target and what does it mean for enterprises?",
        assistant_content="Answer body",
        assistant_status="ok",
        trace_id="trace-001",
        citations=[
            AskCitation(
                doc_id="policy_001",
                title="Policy title",
                source_type="public_policy",
                source="State Council",
                source_url="https://example.com",
                snippet="Policy snippet",
                chunk_id="policy_001_chunk_01",
            )
        ],
    )
    updated = service.maybe_promote_title_from_first_question(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        question="What is the dual-carbon target and what does it mean for enterprises?",
    )

    assert updated is not None
    assert updated.title.startswith("What is the dual-carbon")
    assert updated.title != session.title


def test_session_service_begin_and_finalize_exchange_updates_placeholder(tmp_path) -> None:
    service = build_session_service(tmp_path)
    owner_user_id = create_test_user_id(tmp_path / "carbonrag.sqlite3", prefix="session-stream")
    session = service.create_session(owner_user_id=owner_user_id)

    user_message, assistant_placeholder = service.begin_exchange(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        user_content="What is the dual-carbon target?",
    )

    assert user_message.role == "user"
    assert assistant_placeholder.role == "assistant"
    assert assistant_placeholder.status == "pending"
    assert assistant_placeholder.content == ""

    finalized_message = service.finalize_exchange(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        assistant_message_id=assistant_placeholder.message_id,
        assistant_content="The dual-carbon target means carbon peaking and carbon neutrality.",
        assistant_status="done",
        trace_id="trace-003",
        citations=[
            AskCitation(
                doc_id="policy_001",
                title="Policy title",
                source_type="public_policy",
                source="State Council",
                source_url="https://example.com",
                snippet="Policy snippet",
                chunk_id="policy_001_chunk_01",
            )
        ],
        thinking_content="先梳理当前会话上下文，再生成最终回答。",
    )

    assert finalized_message is not None
    assert finalized_message.status == "done"
    assert finalized_message.trace_id == "trace-003"
    assert finalized_message.thinking_content == "先梳理当前会话上下文，再生成最终回答。"

    refreshed = service.get_session(owner_user_id=owner_user_id, session_id=session.session_id)
    assert refreshed is not None
    assert refreshed.messages[-1].status == "done"
    assert refreshed.messages[-1].thinking_content == "先梳理当前会话上下文，再生成最终回答。"
    assert refreshed.source_summary is not None
    assert refreshed.source_summary.total_citation_count == 1


def test_session_source_summary_counts_policy_demo_separately(tmp_path) -> None:
    service = build_session_service(tmp_path)
    owner_user_id = create_test_user_id(tmp_path / "carbonrag.sqlite3", prefix="session-demo-summary")
    session = service.create_session(owner_user_id=owner_user_id)

    service.record_exchange(
        owner_user_id=owner_user_id,
        session_id=session.session_id,
        user_content="验证演示样例来源",
        assistant_content="仅使用演示样例回答。",
        assistant_status="ok",
        trace_id="trace-demo-001",
        citations=[
            AskCitation(
                doc_id="policy-web-demo",
                title="CarbonRag 低碳韧性校园建设演示样例",
                source_type="public_policy_demo",
                source="CarbonRag 内置演示样例",
                source_url="carbonrag://showcase/policy/low-carbon-campus-action",
                snippet="演示样例片段",
                chunk_id="policy-web-demo_chunk_01",
            )
        ],
    )

    refreshed = service.get_session(owner_user_id=owner_user_id, session_id=session.session_id)
    assert refreshed is not None
    assert refreshed.source_summary is not None
    assert refreshed.source_summary.public_policy_count == 0
    assert refreshed.source_summary.public_policy_demo_count == 1
    assert refreshed.source_summary.total_citation_count == 1
