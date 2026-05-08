from app.ai_runtime.modes import ModeSpec
from app.ai_runtime.schemas.chat import ChatRequest
from app.ai_runtime.schemas.tool import ToolResult


def _extract_hits(tool_results: list[ToolResult] | None) -> list[dict]:
    if not tool_results:
        return []

    hits: list[dict] = []
    for tool_result in tool_results:
        tool_hits = tool_result.output.get("hits", [])
        if isinstance(tool_hits, list):
            hits.extend(hit for hit in tool_hits if isinstance(hit, dict))
    return hits


def build_context_bundle(
    request: ChatRequest,
    mode: ModeSpec,
    *,
    tool_results: list[ToolResult] | None = None,
) -> dict:
    if mode.name == "ask":
        knowledge_scope_requested = request.payload.get("knowledge_scope_requested", "public")
        knowledge_scope_effective = request.payload.get("knowledge_scope_effective", "public")
        recent_messages = request.payload.get("recent_messages", request.payload.get("session_context", []))
        session_summary = request.payload.get("session_summary")
        memory_notes = request.payload.get("memory_notes", [])
        context_usage_estimate = request.payload.get("context_usage_estimate", 0)
        context_budget_estimate = request.payload.get("context_budget_estimate", 258_000)
        compacted_message_count = request.payload.get("compacted_message_count", 0)
        compaction_status = request.payload.get("compaction_status", "idle")
        summary_updated_at = request.payload.get("summary_updated_at")
        attached_knowledge_item_ids = request.payload.get("attached_knowledge_item_ids", [])
        retrieval_hits = _extract_hits(tool_results)
        public_hits = [hit for hit in retrieval_hits if hit.get("source_type") == "public_policy"]
        demo_policy_hits = [hit for hit in retrieval_hits if hit.get("source_type") == "public_policy_demo"]
        private_hits = [
            hit for hit in retrieval_hits if hit.get("source_type") in {"private_sample", "private_upload"}
        ]

        limitations = [
            "不得伪造引用，也不得声称访问了未检索到的外部证据。",
            "private sample 当前只是脱敏演示样例，不代表真实客户审计结果。",
            "用户上传文件进入知识任务流后，只有在当前 session 已挂接且索引完成时，才可作为私有依据参与回答。",
        ]

        if session_summary:
            summary_lines = [
                "以下是当前会话的自动摘要，请优先据此理解较早上下文：",
                session_summary,
            ]
        else:
            summary_lines = ["当前会话尚未生成自动摘要。"]

        if recent_messages:
            session_context_lines = ["最近单会话历史如下，请仅用于延续当前会话上下文："]
            for index, message in enumerate(recent_messages, start=1):
                if not isinstance(message, dict):
                    continue
                role = message.get("role", "unknown")
                content = message.get("content", "")
                session_context_lines.append(f"[history-{index}] {role}: {content}")
        else:
            session_context_lines = ["当前会话历史为空，这是本轮对话的起点。"]
        if attached_knowledge_item_ids:
            session_context_lines.append(
                "当前 session 已挂接知识条目："
                + ", ".join(str(item_id) for item_id in attached_knowledge_item_ids)
            )
        else:
            session_context_lines.append("当前 session 尚未挂接可检索知识条目。")

        if memory_notes:
            memory_note_lines = ["以下是用户级长期记忆预留条目，只用于补充稳定偏好或长期上下文："]
            for index, note in enumerate(memory_notes, start=1):
                if not isinstance(note, dict):
                    continue
                memory_note_lines.extend(
                    [
                        f"[memory-{index}] 标题：{note.get('title', '未命名记忆')}",
                        f"内容：{note.get('content', '')}",
                    ]
                )
        else:
            memory_note_lines = ["当前没有启用的长期记忆条目。"]

        evidence_lines: list[str] = []
        if public_hits:
            evidence_lines.append("当前已检索到以下公共政策片段：")
            for index, hit in enumerate(public_hits, start=1):
                evidence_lines.extend(
                    [
                        f"[policy-{index}] 标题：{hit['title']}",
                        f"发布机构：{hit['source']}",
                        f"片段标识：{hit['chunk_id']}",
                        f"片段内容：{hit['snippet']}",
                    ]
                )
        if demo_policy_hits:
            evidence_lines.append("当前已检索到以下内置演示样例片段（非官方政策依据）：")
            for index, hit in enumerate(demo_policy_hits, start=1):
                evidence_lines.extend(
                    [
                        f"[policy-demo-{index}] 标题：{hit['title']}",
                        f"来源：{hit['source']}（演示样例，不代表真实官方政策）",
                        f"片段标识：{hit['chunk_id']}",
                        f"片段内容：{hit['snippet']}",
                    ]
                )
        if private_hits:
            evidence_lines.append("当前已检索到以下脱敏企业样例片段：")
            for index, hit in enumerate(private_hits, start=1):
                evidence_lines.extend(
                    [
                        f"[private-{index}] 标题：{hit['title']}",
                        f"来源类型：{hit['source_type']}",
                        f"来源：{hit['source']}",
                        f"片段标识：{hit['chunk_id']}",
                        f"片段内容：{hit['snippet']}",
                    ]
                )
        if not evidence_lines:
            evidence_lines = [
                "当前未检索到足够依据。",
                "不得伪造引用，只能明确说明当前 scope 下未命中足够证据，并给出受限说明。",
            ]

        if knowledge_scope_effective == "public":
            scope_strategy_lines = [
                "当前策略：仅检索本地公共政策样本，再基于命中的政策片段回答。",
                "不得声称使用了企业样例或上传附件。",
            ]
        elif knowledge_scope_effective == "private_sample":
            scope_strategy_lines = [
                "当前策略：仅检索当前 session 已关联的脱敏企业知识条目。",
                "必须明确这些样例仅用于演示，不代表真实企业审计结果。",
            ]
        else:
            scope_strategy_lines = [
                "当前策略：同时参考公共政策依据和当前 session 已关联的脱敏企业知识条目。",
                "回答时必须区分政策要求与样例现状，不能把企业知识条目当成政策依据。",
            ]

        return {
            "system_role": "CarbonRag 是一个面向中小企业的双碳问答 MVP。",
            "mode_name": "ask",
            "system_prompt": "\n".join(
                [
                    "你是 CarbonRag 的 ask mode 问答助手。",
                    "当前产品定位：面向中小企业的双碳问答 MVP。",
                    *summary_lines,
                    *session_context_lines,
                    *memory_note_lines,
                    *scope_strategy_lines,
                    "当前限制：未接入完整知识库、不得伪造引用。",
                    f"当前知识范围请求：{knowledge_scope_requested}。",
                    f"当前知识范围实际生效：{knowledge_scope_effective}。",
                    f"当前上下文占用估算：{context_usage_estimate} / {context_budget_estimate}。",
                    f"当前压缩状态：{compaction_status}，已摘要覆盖 {compacted_message_count} 条较早消息。",
                    *evidence_lines,
                    "如果存在政策和样例两类依据，请分层表达“政策要求”与“样例现状”；如果片段不足，只能给出受限说明。",
                ]
            ),
            "user_question": request.user_input,
            "knowledge_scope_requested": knowledge_scope_requested,
            "knowledge_scope_effective": knowledge_scope_effective,
            "recent_messages": recent_messages,
            "session_summary": session_summary,
            "memory_notes": memory_notes,
            "policy_context": {
                "ready": True,
                "source": "local_public_policy_corpus",
                "hit_count": len(public_hits),
                "hits": public_hits,
            },
            "policy_demo_context": {
                "ready": bool(demo_policy_hits),
                "source": "built_in_showcase_fixture",
                "hit_count": len(demo_policy_hits),
                "hits": demo_policy_hits,
            },
            "enterprise_context": {
                "ready": True,
                "source": "local_private_sample_corpus",
                "hit_count": len(private_hits),
                "hits": private_hits,
            },
            "limitations": limitations,
            "session_state": {
                "trace_id": request.trace_id,
                "mode": mode.name,
                "attached_knowledge_item_ids": attached_knowledge_item_ids,
                "compaction_status": compaction_status,
                "context_usage_estimate": context_usage_estimate,
                "context_budget_estimate": context_budget_estimate,
                "compacted_message_count": compacted_message_count,
                "summary_updated_at": summary_updated_at,
            },
            "memory_slot": {
                "status": "implemented",
                "implemented": True,
            },
            "payload_keys": sorted(request.payload.keys()),
        }

    return {
        "policy_context": {
            "ready": mode.name in {"ask", "report"},
            "source": "policy_stub",
        },
        "enterprise_context": {
            "ready": mode.name in {"ask", "carbon", "report"},
            "source": "enterprise_stub",
        },
        "carbon_context": {
            "ready": mode.name == "carbon",
            "source": "carbon_stub",
        },
        "report_context": {
            "ready": mode.name == "report",
            "source": "report_stub",
        },
        "session_state": {
            "trace_id": request.trace_id,
            "mode": mode.name,
        },
        "memory_slot": {
            "status": "reserved",
            "implemented": False,
        },
        "payload_keys": sorted(request.payload.keys()),
    }
