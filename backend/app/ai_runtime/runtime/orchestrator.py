from dataclasses import dataclass, field
from typing import Iterator

from app.ai_runtime.config import get_ai_runtime_config
from app.ai_runtime.modes import list_mode_names, resolve_mode
from app.ai_runtime.providers.base import ChatCompletionResult, ChatProviderError, ChatStreamEvent, ProviderDescriptor
from app.ai_runtime.providers.factory import get_chat_provider, get_embedding_provider
from app.ai_runtime.runtime.context_builder import build_context_bundle
from app.ai_runtime.runtime.guards import (
    enforce_ask_request_constraints,
    enforce_mode_whitelist,
    enforce_tool_whitelist,
)
from app.ai_runtime.runtime.response_formatter import format_runtime_result
from app.ai_runtime.schemas.chat import ChatRequest
from app.ai_runtime.schemas.result import RuntimeResult
from app.ai_runtime.schemas.tool import ToolCall, ToolResult
from app.ai_runtime.tools.registry import ToolRegistry, build_default_registry
from app.core.config import get_settings


@dataclass(frozen=True)
class PreparedRuntimeContext:
    mode_name: str
    tool_calls: list[ToolCall]
    tool_results: list
    context_bundle: dict
    guard_snapshot: object
    provider_descriptor: ProviderDescriptor
    embedding_descriptor: ProviderDescriptor


@dataclass
class RuntimeStreamState:
    answer_fragments: list[str] = field(default_factory=list)
    thinking_fragments: list[str] = field(default_factory=list)
    runtime_result: RuntimeResult | None = None


@dataclass
class RuntimeStreamHandle:
    events: Iterator[ChatStreamEvent]
    state: RuntimeStreamState


REPORT_FILE_INTENT_KEYWORDS = (
    "生成报告",
    "导出报告",
    "下载报告",
    "创建报告",
    "新建报告",
    "报告文件",
    "可下载报告",
    "生成文件",
    "导出文件",
    "创建文件",
    "新建文件",
    "保存为",
    "整理成报告",
    "写成报告",
    "做成报告",
    "整理成文件",
    "写成文件",
    "做成文件",
    "下载链接",
    "文件链接",
    "可下载",
    "word文档",
    "word 文件",
    "docx 文件",
    "report file",
    "create report",
    "export report",
    "download report",
    "download link",
)

REPORT_FILE_WORDS = ("word", "docx", "pdf", "报告文件", "文件")
REPORT_FILE_ACTION_WORDS = (
    "生成",
    "创建",
    "新建",
    "导出",
    "下载",
    "保存",
    "整理",
    "做成",
    "写成",
    "给我",
    "来一份",
    "create",
    "export",
    "download",
    "save",
)

ASSISTANT_REPORT_OFFER_KEYWORDS = (
    "如果你愿意",
    "如果你要",
    "如果你需要",
    "我下一条",
    "下一条",
    "我可以",
    "可以直接输出",
    "可以马上",
    "可以立即",
    "建议下一步",
    "回复一个编号",
)
ASSISTANT_REPORT_ARTIFACT_KEYWORDS = (
    "正式文件",
    "报告正文",
    "正式版",
    "简版报告",
    "管理层摘要",
    "ppt汇报",
    "ppt 汇报",
    "word",
    "docx",
    "pdf",
    "下载链接",
    "可下载",
    "生成报告",
    "导出报告",
    "报告文件",
    "碳核算报告",
)


class AIRuntimeOrchestrator:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        chat_provider=None,
        embedding_provider=None,
    ) -> None:
        self.config = get_ai_runtime_config()
        self.registry = registry or build_default_registry()
        self.chat_provider = chat_provider or get_chat_provider()
        self.embedding_provider = embedding_provider or get_embedding_provider()

    def supported_modes(self) -> list[str]:
        return list_mode_names()

    @staticmethod
    def _looks_like_report_file_intent(text: str) -> bool:
        normalized = text.lower()
        if any(keyword in normalized for keyword in REPORT_FILE_INTENT_KEYWORDS):
            return True
        return any(word in normalized for word in REPORT_FILE_WORDS) and any(
            word in normalized for word in REPORT_FILE_ACTION_WORDS
        )

    @staticmethod
    def _looks_like_assistant_report_offer(text: str) -> bool:
        normalized = text.lower()
        compact = normalized.replace(" ", "")
        has_offer = any(keyword in normalized for keyword in ASSISTANT_REPORT_OFFER_KEYWORDS) or any(
            keyword.replace(" ", "") in compact for keyword in ASSISTANT_REPORT_OFFER_KEYWORDS
        )
        has_artifact = any(keyword in normalized for keyword in ASSISTANT_REPORT_ARTIFACT_KEYWORDS) or any(
            keyword.replace(" ", "") in compact for keyword in ASSISTANT_REPORT_ARTIFACT_KEYWORDS
        )
        return has_offer and has_artifact

    @staticmethod
    def _build_tool_arguments(request: ChatRequest, tool_name: str, *, question_override: str | None = None) -> dict:
        requested_top_k = int(request.payload.get("top_k", 5) or 5)
        # Carbon factor rows are compact and often span multiple activity
        # types. Keep RAG top_k unchanged, but expose enough factors for
        # carbon accounting questions instead of truncating at AskPage's 5.
        effective_top_k = 10 if tool_name == "carbon_factor_lookup" else requested_top_k
        question = question_override or request.user_input
        return {
            "mode": request.mode,
            "question": question,
            "user_input": question,
            "top_k": effective_top_k,
            "knowledge_scope": request.payload.get("knowledge_scope_effective", "mixed"),
            "allowed_knowledge_item_ids": request.payload.get("attached_knowledge_item_ids", []),
            "kb_id": request.payload.get("kb_id"),
            "rag_mode": request.payload.get("rag_mode", "hybrid_rerank"),
            "payload": request.payload,
        }

    def _append_post_response_report_generation(
        self,
        *,
        request: ChatRequest,
        answer: str,
        tool_calls: list[ToolCall],
        tool_results: list[ToolResult],
    ) -> tuple[list[ToolCall], list[ToolResult]]:
        if request.mode != "ask":
            return tool_calls, tool_results
        if any(call.name == "report_file_generate" for call in tool_calls):
            return tool_calls, tool_results
        if not request.payload.get("owner_user_id") or not request.payload.get("session_id"):
            return tool_calls, tool_results
        if not self._looks_like_assistant_report_offer(answer):
            return tool_calls, tool_results

        synthetic_question = (
            "生成 DOCX 报告文件，并在本轮回答下方提供下载链接。\n"
            f"用户原始请求：{request.user_input}\n\n"
            f"AI 已经建议生成的内容：{answer[:1200]}"
        )
        call = ToolCall(
            name="report_file_generate",
            arguments=self._build_tool_arguments(
                request,
                "report_file_generate",
                question_override=synthetic_question,
            ),
        )
        try:
            result = self.registry.invoke(
                call.name,
                arguments=call.arguments,
                context={
                    "mode": request.mode,
                    "trace_id": request.trace_id,
                    "payload_keys": sorted(request.payload.keys()),
                    "trigger_source": "assistant_report_offer",
                },
                trace_id=request.trace_id,
            )
        except Exception as exc:  # pragma: no cover - defensive tool boundary
            result = ToolResult(
                name="report_file_generate",
                status="error",
                output={
                    "skill": {
                        "name": "report-file-generation",
                        "triggered": True,
                    },
                    "intent_detected": True,
                    "report_generated": False,
                    "error_stage": "post_response_tool",
                    "error_message": str(exc),
                    "files": [],
                    "warnings": ["AI 已识别报告生成意图，但本轮文件生成工具调用失败。"],
                },
                metadata={"trace_id": request.trace_id, "trigger_source": "assistant_report_offer"},
            )
        return [*tool_calls, call], [*tool_results, result]

    @staticmethod
    def _resolve_ask_tool_sequence(request: ChatRequest) -> tuple[str, ...]:
        carbon_factor_keywords = (
            "碳因子",
            "排放因子",
            "碳核算",
            "核算",
            "碳排",
            "排放量",
            "外购电力",
            "用电",
            "电量",
            "天然气",
            "柴油",
            "汽油",
            "lpg",
            "煤",
            "蒸汽",
            "emission factor",
            "carbon factor",
            "emission",
            "carbon accounting",
        )

        def should_lookup_carbon_factors() -> bool:
            question = request.user_input.lower()
            return any(keyword in question for keyword in carbon_factor_keywords)

        def should_extract_report_carbon() -> bool:
            if not request.payload.get("attached_file_knowledge_item_ids"):
                return False
            question = request.user_input.lower()
            keywords = carbon_factor_keywords + (
                "报告",
                "账单",
            )
            return any(keyword in question for keyword in keywords)

        def should_generate_report_file() -> bool:
            return AIRuntimeOrchestrator._looks_like_report_file_intent(request.user_input)

        if get_settings().rag_langchain_enabled:
            tool_sequence = ["rag_pro_search"]
            if request.payload.get("attached_file_knowledge_item_ids"):
                # Session uploads are not necessarily part of the selected KB yet.
                # Keep the explicit per-turn file retriever so parsed attachment chunks
                # still reach the grounded prompt after the RAG-Pro spine became primary.
                tool_sequence.append("session_file_search")
            if should_lookup_carbon_factors():
                tool_sequence.append("carbon_factor_lookup")
            if should_extract_report_carbon():
                tool_sequence.append("report_carbon_extract_calc")
            if should_generate_report_file():
                tool_sequence.append("report_file_generate")
            return tuple(tool_sequence)
        effective_scope = request.payload.get("knowledge_scope_effective", "mixed")
        tool_sequence: list[str]
        if effective_scope == "private_sample":
            tool_sequence = ["enterprise_retrieve"]
        elif effective_scope == "mixed":
            tool_sequence = ["mixed_retrieve"]
        else:
            tool_sequence = ["policy_retrieve"]
        if request.payload.get("attached_file_knowledge_item_ids"):
            tool_sequence.append("session_file_search")
        if should_lookup_carbon_factors():
            tool_sequence.append("carbon_factor_lookup")
        if should_extract_report_carbon():
            tool_sequence.append("report_carbon_extract_calc")
        if should_generate_report_file():
            tool_sequence.append("report_file_generate")
        return tuple(tool_sequence)

    def _prepare_runtime(self, request: ChatRequest) -> PreparedRuntimeContext:
        mode = resolve_mode(request.mode)
        enforce_mode_whitelist(mode.name, self.config.allowed_modes)
        if request.mode == "ask":
            enforce_ask_request_constraints(request)
            tool_sequence = self._resolve_ask_tool_sequence(request)
        else:
            tool_sequence = mode.default_stub_tool_sequence

        guard_snapshot = enforce_tool_whitelist(
            mode,
            self.registry,
            tool_sequence,
        )

        tool_calls = [
            ToolCall(
                name=tool_name,
                arguments=self._build_tool_arguments(request, tool_name),
            )
            for tool_name in tool_sequence
        ]
        tool_context = {
            "mode": request.mode,
            "trace_id": request.trace_id,
            "payload_keys": sorted(request.payload.keys()),
        }
        tool_results = [
            self.registry.invoke(
                call.name,
                arguments=call.arguments,
                context=tool_context,
                trace_id=request.trace_id,
            )
            for call in tool_calls
        ]
        context_bundle = build_context_bundle(request, mode, tool_results=tool_results)

        provider_descriptor = self.chat_provider.describe()
        embedding_descriptor = self.embedding_provider.describe()
        return PreparedRuntimeContext(
            mode_name=mode.name,
            tool_calls=tool_calls,
            tool_results=tool_results,
            context_bundle=context_bundle,
            guard_snapshot=guard_snapshot,
            provider_descriptor=provider_descriptor,
            embedding_descriptor=embedding_descriptor,
        )

    def _format_provider_error_result(
        self,
        *,
        request: ChatRequest,
        prepared: PreparedRuntimeContext,
        exc: ChatProviderError,
    ) -> RuntimeResult:
        return format_runtime_result(
            request=request,
            provider_descriptor=prepared.provider_descriptor,
            embedding_descriptor=prepared.embedding_descriptor,
            guard_snapshot=prepared.guard_snapshot,
            context_bundle=prepared.context_bundle,
            provider_result=ChatCompletionResult(
                content="",
                metadata={
                    "error_reason": exc.reason,
                    "error_message": str(exc),
                    "provider_status_code": exc.status_code,
                },
            ),
            tool_calls=prepared.tool_calls,
            tool_results=prepared.tool_results,
            status="provider_error",
            answer="当前问答服务暂不可用，请稍后重试。",
        )

    def run(self, request: ChatRequest) -> RuntimeResult:
        prepared = self._prepare_runtime(request)

        if prepared.mode_name != "ask":
            return format_runtime_result(
                request=request,
                provider_descriptor=prepared.provider_descriptor,
                embedding_descriptor=prepared.embedding_descriptor,
                guard_snapshot=prepared.guard_snapshot,
                context_bundle=prepared.context_bundle,
                provider_result=ChatCompletionResult(
                    content=f"[{prepared.mode_name}] mode skeleton is reserved for future implementation.",
                    metadata={"stub": True},
                ),
                tool_calls=prepared.tool_calls,
                tool_results=prepared.tool_results,
                status="stub_ready",
                answer=f"[{prepared.mode_name}] mode skeleton is reserved for future implementation.",
            )

        try:
            provider_result = self.chat_provider.generate_response(
                system_prompt=prepared.context_bundle["system_prompt"],
                user_input=request.user_input,
            )
            tool_calls, tool_results = self._append_post_response_report_generation(
                request=request,
                answer=provider_result.content,
                tool_calls=prepared.tool_calls,
                tool_results=prepared.tool_results,
            )
            return format_runtime_result(
                request=request,
                provider_descriptor=prepared.provider_descriptor,
                embedding_descriptor=prepared.embedding_descriptor,
                guard_snapshot=prepared.guard_snapshot,
                context_bundle=prepared.context_bundle,
                provider_result=provider_result,
                tool_calls=tool_calls,
                tool_results=tool_results,
                status="ok",
                answer=provider_result.content,
            )
        except ChatProviderError as exc:
            return self._format_provider_error_result(request=request, prepared=prepared, exc=exc)

    def run_stream(self, request: ChatRequest) -> RuntimeStreamHandle:
        prepared = self._prepare_runtime(request)
        state = RuntimeStreamState()

        def iterator() -> Iterator[ChatStreamEvent]:
            if prepared.mode_name != "ask":
                state.runtime_result = format_runtime_result(
                    request=request,
                    provider_descriptor=prepared.provider_descriptor,
                    embedding_descriptor=prepared.embedding_descriptor,
                    guard_snapshot=prepared.guard_snapshot,
                    context_bundle=prepared.context_bundle,
                    provider_result=ChatCompletionResult(
                        content=f"[{prepared.mode_name}] mode skeleton is reserved for future implementation.",
                        metadata={"stub": True},
                    ),
                    tool_calls=prepared.tool_calls,
                    tool_results=prepared.tool_results,
                    status="stub_ready",
                    answer=f"[{prepared.mode_name}] mode skeleton is reserved for future implementation.",
                )
                return

            try:
                for event in self.chat_provider.stream_response(
                    system_prompt=prepared.context_bundle["system_prompt"],
                    user_input=request.user_input,
                ):
                    if event.kind == "thinking_delta":
                        delta = event.data.get("delta")
                        if isinstance(delta, str) and delta:
                            state.thinking_fragments.append(delta)
                        yield event
                        continue

                    if event.kind == "answer_delta":
                        delta = event.data.get("delta")
                        if isinstance(delta, str) and delta:
                            state.answer_fragments.append(delta)
                        yield event
                        continue

                    if event.kind == "status":
                        yield event
                        continue

                    if event.kind == "error":
                        exc = ChatProviderError(
                            event.data.get("message", "Chat provider stream failed."),
                            reason=str(event.data.get("reason", "network_error")),
                            status_code=event.data.get("status_code"),
                        )
                        state.runtime_result = self._format_provider_error_result(
                            request=request,
                            prepared=prepared,
                            exc=exc,
                        )
                        yield event
                        return

                    if event.kind == "done":
                        final_answer = event.data.get("answer") or event.data.get("content") or "".join(state.answer_fragments)
                        metadata = event.data.get("metadata")
                        provider_metadata = metadata if isinstance(metadata, dict) else {}
                        provider_result = ChatCompletionResult(
                            content=final_answer,
                            metadata=provider_metadata,
                        )
                        tool_calls, tool_results = self._append_post_response_report_generation(
                            request=request,
                            answer=final_answer,
                            tool_calls=prepared.tool_calls,
                            tool_results=prepared.tool_results,
                        )
                        state.runtime_result = format_runtime_result(
                            request=request,
                            provider_descriptor=prepared.provider_descriptor,
                            embedding_descriptor=prepared.embedding_descriptor,
                            guard_snapshot=prepared.guard_snapshot,
                            context_bundle=prepared.context_bundle,
                            provider_result=provider_result,
                            tool_calls=tool_calls,
                            tool_results=tool_results,
                            status="ok",
                            answer=final_answer,
                        )
                        yield ChatStreamEvent(
                            kind="done",
                            data={
                                "answer": final_answer,
                                "content": final_answer,
                                "metadata": provider_metadata,
                                "trace_id": request.trace_id,
                            },
                        )
                        return
            except ChatProviderError as exc:
                state.runtime_result = self._format_provider_error_result(
                    request=request,
                    prepared=prepared,
                    exc=exc,
                )
                yield ChatStreamEvent(
                    kind="error",
                    data={
                        "message": str(exc),
                        "reason": exc.reason,
                        "status_code": exc.status_code,
                    },
                )
                return

            if state.runtime_result is None:
                exc = ChatProviderError(
                    "Chat provider stream ended unexpectedly.",
                    reason="invalid_response",
                )
                state.runtime_result = self._format_provider_error_result(
                    request=request,
                    prepared=prepared,
                    exc=exc,
                )
                yield ChatStreamEvent(
                    kind="error",
                    data={
                        "message": str(exc),
                        "reason": exc.reason,
                        "status_code": exc.status_code,
                    },
                )

        return RuntimeStreamHandle(events=iterator(), state=state)
