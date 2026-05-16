from app.ai_runtime.providers.base import (
    BaseChatProvider,
    BaseEmbeddingProvider,
    ChatCompletionResult,
    ChatProviderError,
    ChatStreamEvent,
    EmbeddingResult,
    ProviderDescriptor,
)
from app.ai_runtime.providers.chat_openai_compatible import OpenAICompatibleChatProvider
from app.ai_runtime.runtime.orchestrator import AIRuntimeOrchestrator
from app.ai_runtime.schemas.chat import ChatRequest


class FakeChatProvider(BaseChatProvider):
    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name="fake-chat-provider",
            provider_type="chat",
            mode="openai_compatible",
            default_model="gpt-5.4",
        )

    def generate_response(self, *, system_prompt: str, user_input: str) -> ChatCompletionResult:
        assert "CarbonRag" in system_prompt
        return ChatCompletionResult(content=f"回答: {user_input}")

    def stream_response(self, *, system_prompt: str, user_input: str):
        del system_prompt
        yield ChatStreamEvent(kind="status", data={"status": "thinking"})
        yield ChatStreamEvent(kind="answer_delta", data={"delta": f"回答: {user_input}"})
        yield ChatStreamEvent(kind="done", data={"content": f"回答: {user_input}", "metadata": {"transport": "test"}})


class FailingChatProvider(BaseChatProvider):
    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name="failing-chat-provider",
            provider_type="chat",
            mode="openai_compatible",
            default_model="gpt-5.4",
        )

    def generate_response(self, *, system_prompt: str, user_input: str) -> ChatCompletionResult:
        raise ChatProviderError("boom", reason="network_error")

    def stream_response(self, *, system_prompt: str, user_input: str):
        del system_prompt, user_input
        raise ChatProviderError("boom", reason="network_error")


class FakeEmbeddingProvider(BaseEmbeddingProvider):
    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name="fake-embedding-provider",
            provider_type="embedding",
            mode="openai_compatible",
            default_model="text-embedding-3-small",
        )

    def embed_stub(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(vectors=[[1.0, 2.0, 3.0] for _ in texts])


class FakeStreamingResponse:
    def __init__(self, *, status_code: int, lines: list[str]) -> None:
        self.status_code = status_code
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def iter_lines(self):
        for line in self._lines:
            yield line


def test_orchestrator_returns_runtime_result_for_ok_request() -> None:
    orchestrator = AIRuntimeOrchestrator(
        chat_provider=FakeChatProvider(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    request = ChatRequest(
        mode="ask",
        user_input="什么是双碳目标？",
        payload={
            "session_id": "session-demo",
            "recent_messages": [
                {"role": "user", "content": "先解释什么是碳达峰。"},
                {"role": "assistant", "content": "碳达峰是排放到峰值后进入下降。"},
            ],
            "session_summary": "用户已经了解碳达峰的基础定义，正在继续询问双碳目标。",
            "memory_notes": [],
            "context_usage_estimate": 1200,
            "context_budget_estimate": 258000,
            "compaction_status": "compacted",
            "compacted_message_count": 8,
            "knowledge_scope_requested": "public",
            "knowledge_scope_effective": "public",
            "top_k": 5,
        },
    )

    result = orchestrator.run(request)

    assert result.status == "ok"
    assert result.mode == "ask"
    assert result.trace_id == request.trace_id
    assert result.context_summary["knowledge_scope_requested"] == "public"
    assert result.context_summary["knowledge_scope_effective"] == "public"
    assert result.context_summary["memory_reserved"] is False
    assert result.context_summary["tool_count"] == 1
    assert result.context_summary["session_message_count"] == 2
    assert result.context_summary["summary_present"] is True
    assert result.context_summary["compaction_status"] == "compacted"
    assert "grounded_by_policy" in result.context_summary
    assert result.context_summary["retrieval_hit_count"] >= 0
    assert result.tool_calls[0].name == "rag_pro_search"
    assert result.tool_results[0].name == "rag_pro_search"
    assert "retrieval_trace" in result.context_summary
    assert result.response.mode == "ask"
    assert result.response.status == "ok"
    assert result.response.provider_mode == "openai_compatible"
    assert "forbidden_capabilities" in result.metadata


def test_orchestrator_expands_carbon_factor_lookup_top_k() -> None:
    orchestrator = AIRuntimeOrchestrator(
        chat_provider=FakeChatProvider(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    request = ChatRequest(
        mode="ask",
        user_input="外购电力、天然气、柴油、汽油、外购蒸汽分别用什么碳因子？",
        payload={
            "session_id": "session-demo",
            "knowledge_scope_requested": "public",
            "knowledge_scope_effective": "public",
            "top_k": 5,
        },
    )

    result = orchestrator.run(request)

    factor_call = next(call for call in result.tool_calls if call.name == "carbon_factor_lookup")
    assert factor_call.arguments["top_k"] == 10


def test_orchestrator_adds_report_file_generation_tool_for_export_intent() -> None:
    request = ChatRequest(
        mode="ask",
        user_input="请把刚才的分析导出成 DOCX 和 PDF 报告文件",
        payload={
            "session_id": "session-demo",
            "knowledge_scope_requested": "public",
            "knowledge_scope_effective": "public",
            "top_k": 5,
        },
    )

    tool_sequence = AIRuntimeOrchestrator._resolve_ask_tool_sequence(request)

    assert "report_file_generate" in tool_sequence
    assert tool_sequence[-1] == "report_file_generate"


def test_orchestrator_adds_report_file_generation_tool_for_download_link_intent() -> None:
    request = ChatRequest(
        mode="ask",
        user_input="给我一份 Word 文档下载链接",
        payload={
            "session_id": "session-demo",
            "knowledge_scope_requested": "mixed",
            "knowledge_scope_effective": "mixed",
            "top_k": 5,
        },
    )

    tool_sequence = AIRuntimeOrchestrator._resolve_ask_tool_sequence(request)

    assert tool_sequence[-1] == "report_file_generate"


def test_orchestrator_does_not_treat_plain_pdf_question_as_file_export_intent() -> None:
    request = ChatRequest(
        mode="ask",
        user_input="这个 PDF 文件里写了什么？",
        payload={
            "session_id": "session-demo",
            "knowledge_scope_requested": "public",
            "knowledge_scope_effective": "public",
            "top_k": 5,
        },
    )

    tool_sequence = AIRuntimeOrchestrator._resolve_ask_tool_sequence(request)

    assert "report_file_generate" not in tool_sequence


def test_orchestrator_returns_provider_error_when_chat_provider_fails() -> None:
    orchestrator = AIRuntimeOrchestrator(
        chat_provider=FailingChatProvider(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    request = ChatRequest(
        mode="ask",
        user_input="什么是碳中和？",
        payload={
            "session_id": "session-demo",
            "recent_messages": [
                {"role": "user", "content": "先解释什么是碳达峰。"},
                {"role": "assistant", "content": "碳达峰是排放到峰值后进入下降。"},
            ],
            "session_summary": "用户已经了解碳达峰的基础定义。",
            "memory_notes": [],
            "context_usage_estimate": 900,
            "context_budget_estimate": 258000,
            "compaction_status": "compacted",
            "compacted_message_count": 6,
            "knowledge_scope_requested": "public",
            "knowledge_scope_effective": "public",
            "top_k": 5,
        },
    )

    result = orchestrator.run(request)

    assert result.status == "provider_error"
    assert result.tool_calls[0].name == "rag_pro_search"
    assert isinstance(result.citations, list)
    assert result.response.status == "provider_error"
    assert result.response.answer == "当前问答服务暂不可用，请稍后重试。"


def test_orchestrator_run_stream_emits_status_thinking_answer_and_done(monkeypatch) -> None:
    def fake_stream(method: str, url: str, *, headers: dict, json: dict, timeout: float):
        del method, url, headers, json, timeout
        return FakeStreamingResponse(
            status_code=200,
            lines=[
                'event: reasoning',
                'data: {"id":"chatcmpl-stream","choices":[{"delta":{"reasoning_content":"先梳理上下文。"}}]}',
                "",
                'event: message',
                'data: {"id":"chatcmpl-stream","choices":[{"delta":{"content":"双碳目标是碳达峰和碳中和。"}}],"usage":{"prompt_tokens":12,"completion_tokens":18}}',
                "",
                "data: [DONE]",
            ],
        )

    monkeypatch.setattr("app.ai_runtime.providers.chat_openai_compatible.httpx.stream", fake_stream)

    provider = OpenAICompatibleChatProvider(
        base_url="https://example.com/v1",
        api_key="demo-key",
        model_name="gpt-5.4",
        temperature=0.2,
        max_tokens=4096,
        timeout_seconds=30.0,
    )
    orchestrator = AIRuntimeOrchestrator(
        chat_provider=provider,
        embedding_provider=FakeEmbeddingProvider(),
    )
    request = ChatRequest(
        mode="ask",
        user_input="什么是双碳目标？",
        payload={
            "session_id": "session-demo",
            "recent_messages": [],
            "session_summary": None,
            "memory_notes": [],
            "context_usage_estimate": 0,
            "context_budget_estimate": 258000,
            "compaction_status": "idle",
            "compacted_message_count": 0,
            "knowledge_scope_requested": "public",
            "knowledge_scope_effective": "public",
            "top_k": 5,
        },
    )

    handle = orchestrator.run_stream(request)
    events = list(handle.events)

    assert [event.kind for event in events[:4]] == ["status", "thinking_delta", "status", "answer_delta"]
    assert events[0].data["status"] == "thinking"
    assert events[1].data["delta"] == "先梳理上下文。"
    assert events[2].data["status"] == "streaming"
    assert events[3].data["delta"] == "双碳目标是碳达峰和碳中和。"
    assert events[-1].kind == "done"
    assert handle.state.runtime_result is not None
    assert handle.state.runtime_result.status == "ok"
    assert handle.state.runtime_result.response.answer == "双碳目标是碳达峰和碳中和。"
    assert handle.state.runtime_result.response.status == "ok"
    assert handle.state.runtime_result.source_summary["total_citation_count"] >= 0
