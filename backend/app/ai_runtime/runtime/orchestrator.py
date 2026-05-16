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
from app.ai_runtime.schemas.tool import ToolCall
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
            question = request.user_input.lower()
            keywords = (
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
            if any(keyword in question for keyword in keywords):
                return True
            file_words = ("word", "docx", "pdf", "报告文件", "文件")
            action_words = ("生成", "创建", "新建", "导出", "下载", "保存", "整理", "做成", "写成", "给我", "来一份", "create", "export", "download", "save")
            return any(word in question for word in file_words) and any(word in question for word in action_words)

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
        effective_scope = request.payload.get("knowledge_scope_effective", "public")
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

        def build_tool_arguments(tool_name: str) -> dict:
            requested_top_k = int(request.payload.get("top_k", 5) or 5)
            # Carbon factor rows are compact and often span multiple activity
            # types. Keep RAG top_k unchanged, but expose enough factors for
            # carbon accounting questions instead of truncating at AskPage's 5.
            effective_top_k = 10 if tool_name == "carbon_factor_lookup" else requested_top_k
            return {
                "mode": request.mode,
                "question": request.user_input,
                "user_input": request.user_input,
                "top_k": effective_top_k,
                "knowledge_scope": request.payload.get("knowledge_scope_effective", "public"),
                "allowed_knowledge_item_ids": request.payload.get("attached_knowledge_item_ids", []),
                "kb_id": request.payload.get("kb_id"),
                "rag_mode": request.payload.get("rag_mode", "hybrid_rerank"),
                "payload": request.payload,
            }

        tool_calls = [
            ToolCall(
                name=tool_name,
                arguments=build_tool_arguments(tool_name),
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
            return format_runtime_result(
                request=request,
                provider_descriptor=prepared.provider_descriptor,
                embedding_descriptor=prepared.embedding_descriptor,
                guard_snapshot=prepared.guard_snapshot,
                context_bundle=prepared.context_bundle,
                provider_result=provider_result,
                tool_calls=prepared.tool_calls,
                tool_results=prepared.tool_results,
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
                        state.runtime_result = format_runtime_result(
                            request=request,
                            provider_descriptor=prepared.provider_descriptor,
                            embedding_descriptor=prepared.embedding_descriptor,
                            guard_snapshot=prepared.guard_snapshot,
                            context_bundle=prepared.context_bundle,
                            provider_result=provider_result,
                            tool_calls=prepared.tool_calls,
                            tool_results=prepared.tool_results,
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
