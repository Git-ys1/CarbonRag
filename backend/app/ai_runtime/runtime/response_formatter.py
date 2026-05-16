from app.ai_runtime.providers.base import ChatCompletionResult, ProviderDescriptor
from app.ai_runtime.runtime.guards import GuardSnapshot
from app.ai_runtime.schemas.chat import ChatRequest, ChatResponse
from app.ai_runtime.schemas.result import RuntimeResult
from app.ai_runtime.schemas.tool import ToolCall, ToolResult


def _extract_citations(tool_results: list[ToolResult]) -> list[dict]:
    citations: list[dict] = []
    for tool_result in tool_results:
        hits = tool_result.output.get("hits", [])
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            citations.append(
                {
                    "doc_id": hit.get("doc_id") or hit.get("knowledge_item_id"),
                    "knowledge_item_id": hit.get("knowledge_item_id"),
                    "title": hit.get("title"),
                    "source_type": hit.get("source_type"),
                    "source": hit.get("source"),
                    "source_url": hit.get("source_url"),
                    "snippet": hit.get("snippet"),
                    "chunk_id": hit.get("chunk_id"),
                    "library_scope": hit.get("library_scope"),
                    "file_id": hit.get("file_id"),
                    "page_number": hit.get("page_number"),
                    "sheet_name": hit.get("sheet_name"),
                    "slide_number": hit.get("slide_number"),
                    "section_title": hit.get("section_title"),
                }
            )
    return citations


def _extract_retrieval_traces(tool_results: list[ToolResult]) -> list[dict]:
    traces: list[dict] = []
    for tool_result in tool_results:
        trace = tool_result.output.get("retrieval_trace") or tool_result.metadata.get("rag_metadata")
        if isinstance(trace, dict):
            traces.append(trace)
    return traces


def _extract_generated_reports(tool_results: list[ToolResult]) -> list[dict]:
    reports: list[dict] = []
    for tool_result in tool_results:
        if tool_result.name != "report_file_generate":
            continue
        output = tool_result.output
        if not isinstance(output, dict):
            continue
        reports.append(
            {
                "status": tool_result.status,
                "report_id": output.get("report_id"),
                "report_type": output.get("report_type"),
                "title": output.get("title"),
                "files": output.get("files") or [],
                "download_urls": output.get("download_urls") or [],
                "error_stage": output.get("error_stage"),
                "error_message": output.get("error_message"),
            }
        )
    return reports


def _append_generated_report_downloads(answer: str, generated_reports: list[dict]) -> str:
    download_lines: list[str] = []
    error_lines: list[str] = []
    for report in generated_reports:
        if report.get("status") != "success":
            error_message = report.get("error_message")
            if error_message:
                error_lines.append(f"- 报告文件生成失败：{error_message}")
            continue

        title = str(report.get("title") or "生成的报告")
        files = report.get("files") if isinstance(report.get("files"), list) else []
        for file in files:
            if not isinstance(file, dict):
                continue
            download_url = str(file.get("download_url") or "").strip()
            filename = str(file.get("filename") or "报告文件").strip()
            file_format = str(file.get("format") or "").upper() or "文件"
            if not download_url:
                continue
            if download_url in answer:
                continue
            download_lines.append(f"- [{file_format} 下载：{filename}]({download_url})（{title}）")

    if not download_lines and not error_lines:
        return answer

    blocks: list[str] = []
    if download_lines:
        blocks.append("**已生成文件**\n" + "\n".join(download_lines))
    if error_lines:
        blocks.append("**文件生成提示**\n" + "\n".join(error_lines))
    separator = "\n\n" if answer.strip() else ""
    rendered_blocks = "\n\n".join(blocks)
    return f"{answer.rstrip()}{separator}{rendered_blocks}"


def _build_source_summary(*, knowledge_scope: str, citations: list[dict]) -> dict:
    public_policy_count = sum(1 for citation in citations if citation.get("source_type") == "public_policy")
    public_policy_demo_count = sum(1 for citation in citations if citation.get("source_type") == "public_policy_demo")
    private_sample_count = sum(1 for citation in citations if citation.get("source_type") == "private_sample")
    private_upload_count = sum(1 for citation in citations if citation.get("source_type") == "private_upload")
    carbon_factor_count = sum(1 for citation in citations if citation.get("source_type") == "carbon_factor")
    return {
        "knowledge_scope": knowledge_scope,
        "public_policy_count": public_policy_count,
        "public_policy_demo_count": public_policy_demo_count,
        "private_sample_count": private_sample_count,
        "private_upload_count": private_upload_count,
        "carbon_factor_count": carbon_factor_count,
        "total_citation_count": len(citations),
    }


def format_runtime_result(
    *,
    request: ChatRequest,
    provider_descriptor: ProviderDescriptor,
    embedding_descriptor: ProviderDescriptor,
    guard_snapshot: GuardSnapshot,
    context_bundle: dict,
    provider_result: ChatCompletionResult,
    tool_calls: list[ToolCall],
    tool_results: list[ToolResult],
    status: str,
    answer: str,
) -> RuntimeResult:
    citations = _extract_citations(tool_results)
    knowledge_scope = context_bundle.get("knowledge_scope_effective") or request.payload.get(
        "knowledge_scope_effective",
        "mixed",
    )
    source_summary = _build_source_summary(knowledge_scope=knowledge_scope, citations=citations)
    retrieval_traces = _extract_retrieval_traces(tool_results)
    generated_reports = _extract_generated_reports(tool_results)
    answer = _append_generated_report_downloads(answer, generated_reports)
    latest_retrieval_trace = dict(retrieval_traces[-1]) if retrieval_traces else None
    if latest_retrieval_trace is None and generated_reports:
        latest_retrieval_trace = {"tool": "report_file_generate"}
    if latest_retrieval_trace is not None:
        latest_retrieval_trace.update(
            {
                "generation_provider": provider_descriptor.name,
                "generation_model": provider_descriptor.default_model,
                "provider_ref": request.payload.get("provider_ref"),
                "thinking_content": provider_result.metadata.get("thinking_content"),
            }
        )
        if generated_reports:
            latest_retrieval_trace["generated_reports"] = generated_reports
    context_summary = {
        "payload_keys": context_bundle.get("payload_keys", []),
        "memory_reserved": not context_bundle.get("memory_slot", {}).get("implemented", False),
        "tool_count": len(tool_calls),
    }
    if request.mode == "ask":
        context_summary.update(
            {
                "knowledge_scope_requested": context_bundle.get("knowledge_scope_requested"),
                "knowledge_scope_effective": context_bundle.get("knowledge_scope_effective"),
                "single_turn_only": False,
                "session_message_count": len(context_bundle.get("recent_messages", context_bundle.get("session_context", []))),
                "summary_present": bool(context_bundle.get("session_summary")),
                "compaction_status": context_bundle.get("session_state", {}).get("compaction_status"),
                "context_usage_estimate": context_bundle.get("session_state", {}).get("context_usage_estimate"),
                "context_budget_estimate": context_bundle.get("session_state", {}).get("context_budget_estimate"),
                "compacted_message_count": context_bundle.get("session_state", {}).get("compacted_message_count"),
                "summary_updated_at": context_bundle.get("session_state", {}).get("summary_updated_at"),
                "grounded_by_policy": source_summary["public_policy_count"] > 0,
                "grounded_by_demo_showcase": source_summary["public_policy_demo_count"] > 0,
                "grounded_by_private_sample": source_summary["private_sample_count"] > 0,
                "retrieval_hit_count": len(citations),
                "retrieval_trace": latest_retrieval_trace,
                "citation_count": len(citations),
                "source_summary": source_summary,
                "kb_id": context_bundle.get("session_state", {}).get("kb_id"),
                "rag_mode": context_bundle.get("session_state", {}).get("rag_mode"),
                "generated_reports": generated_reports,
                "generated_report_count": len(generated_reports),
            }
        )
    else:
        context_summary.update(
            {
                "policy_ready": context_bundle.get("policy_context", {}).get("ready"),
                "enterprise_ready": context_bundle.get("enterprise_context", {}).get("ready"),
                "carbon_ready": context_bundle.get("carbon_context", {}).get("ready"),
                "report_ready": context_bundle.get("report_context", {}).get("ready"),
            }
        )

    response = ChatResponse(
        mode=request.mode,
        status=status,
        answer=answer,
        trace_id=request.trace_id,
        provider_name=provider_descriptor.name,
        provider_mode=provider_descriptor.mode,
        model_name=provider_descriptor.default_model,
    )

    return RuntimeResult(
        mode=request.mode,
        status=status,
        trace_id=request.trace_id,
        context_summary=context_summary,
        tool_calls=tool_calls,
        tool_results=tool_results,
        citations=citations,
        source_summary=source_summary,
        response=response,
        metadata={
            "chat_provider": provider_descriptor.name,
            "embedding_provider": embedding_descriptor.name,
            "forbidden_capabilities": list(guard_snapshot.forbidden_capabilities),
            "provider_metadata": provider_result.metadata,
            "retrieval_traces": retrieval_traces,
            "generated_reports": generated_reports,
        },
    )
