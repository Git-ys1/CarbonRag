import json
import threading
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.ai_runtime.config import get_ai_runtime_config
from app.ai_runtime.providers.base import ChatProviderError
from app.ai_runtime.runtime.orchestrator import AIRuntimeOrchestrator
from app.ai_runtime.schemas.chat import ChatRequest
from app.auth.dependencies import require_authenticated_user
from app.auth.schemas import AuthenticatedUser
from app.schemas.ask import AskCitation, AskRequest, AskResponse, AskSourceSummary, MessageStatus
from app.settings.service import SettingsValidationError, get_settings_service
from app.session.schemas import CreateSessionRequest, SessionDetail, SessionSummary, UpdateSessionRequest
from app.session.service import get_session_service
from app.session.streaming import get_active_stream_registry, get_retry_delay, is_retryable_provider_error

router = APIRouter(prefix="/sessions")


def build_error_response(*, status_code: int, answer: str, trace_id: str, knowledge_scope: str) -> JSONResponse:
    payload = AskResponse(
        answer=answer,
        mode="ask",
        status="invalid_input" if status_code == 422 else "provider_error",
        citations=[],
        source_summary=AskSourceSummary(
            knowledge_scope=knowledge_scope,
            public_policy_count=0,
            public_policy_demo_count=0,
            private_sample_count=0,
            private_upload_count=0,
            total_citation_count=0,
        ),
        trace_id=trace_id,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def build_chat_request(
    *,
    session_id: str,
    payload: AskRequest,
    current_user: AuthenticatedUser,
) -> tuple[ChatRequest, list[str]]:
    session_service = get_session_service()
    attached_knowledge_item_ids = session_service.list_attached_knowledge_item_ids(
        owner_user_id=current_user.user_id,
        session_id=session_id,
    )
    attached_knowledge_item_set = set(attached_knowledge_item_ids)
    requested_ids = payload.attached_knowledge_item_ids or payload.attached_file_ids
    filtered_knowledge_item_ids = [item for item in requested_ids if item in attached_knowledge_item_set]
    effective_knowledge_item_ids = filtered_knowledge_item_ids if requested_ids else attached_knowledge_item_ids

    chat_request = ChatRequest(
        mode="ask",
        user_input=payload.question,
        payload={
            "session_id": session_id,
            **session_service.build_session_context(
                owner_user_id=current_user.user_id,
                session_id=session_id,
                max_turns=6,
                upcoming_user_input=payload.question,
                provider_override=payload.provider_override,
            ),
            "knowledge_scope_requested": payload.knowledge_scope,
            "knowledge_scope_effective": payload.knowledge_scope,
            "top_k": payload.top_k,
            "attached_file_ids": payload.attached_file_ids,
            "attached_knowledge_item_ids": effective_knowledge_item_ids,
            "request_group_id": payload.request_group_id,
        },
    )
    return chat_request, effective_knowledge_item_ids


def validate_chat_request(chat_request: ChatRequest, *, knowledge_scope: str) -> JSONResponse | None:
    config = get_ai_runtime_config()
    if not chat_request.user_input:
        return build_error_response(
            status_code=422,
            answer="问题不能为空。",
            trace_id=chat_request.trace_id,
            knowledge_scope=knowledge_scope,
        )
    if len(chat_request.user_input) > config.ask_max_question_length:
        return build_error_response(
            status_code=422,
            answer=f"问题长度不能超过 {config.ask_max_question_length} 个字符。",
            trace_id=chat_request.trace_id,
            knowledge_scope=knowledge_scope,
        )
    return None


def empty_source_summary(knowledge_scope: str) -> AskSourceSummary:
    return AskSourceSummary(
        knowledge_scope=knowledge_scope,
        public_policy_count=0,
        public_policy_demo_count=0,
        private_sample_count=0,
        private_upload_count=0,
        total_citation_count=0,
    )


def build_sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def resolve_final_message_status(result_status: str) -> MessageStatus:
    if result_status == "ok":
        return "done"
    if result_status == "invalid_input":
        return "invalid_input"
    return "provider_error"


def build_stream_status_payload(
    *,
    status: str,
    stream_session,
    attempt: int,
    max_attempts: int,
    recovered: bool = False,
) -> dict:
    return {
        "status": status,
        "trace_id": stream_session.trace_id,
        "user_message_id": stream_session.user_message_id,
        "assistant_message_id": stream_session.assistant_message_id,
        "request_group_id": stream_session.request_group_id,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "recovered": recovered,
        "resume_supported": True,
        "provider_ref": stream_session.provider_ref,
    }


def emit_terminal_stream_error(
    *,
    stream_session,
    session_service,
    owner_user_id: str,
    requested_scope: str,
    answer: str,
    attempt: int,
    max_attempts: int,
) -> None:
    source_summary = empty_source_summary(requested_scope)
    finalized_message = session_service.finalize_exchange(
        owner_user_id=owner_user_id,
        session_id=stream_session.session_id,
        assistant_message_id=stream_session.assistant_message_id,
        assistant_content=answer,
        assistant_status="provider_error",
        trace_id=stream_session.trace_id,
        citations=[],
        knowledge_scope=requested_scope,
        source_summary=source_summary,
        thinking_content=None,
    )
    refreshed_session = session_service.get_session(owner_user_id=owner_user_id, session_id=stream_session.session_id)
    memory_state = refreshed_session.memory_state.model_dump(mode="json") if refreshed_session and refreshed_session.memory_state else None
    metadata_payload = {
        "answer": answer,
        "status": "provider_error",
        "citations": [],
        "source_summary": source_summary.model_dump(),
        "trace_id": stream_session.trace_id,
        "user_message_id": stream_session.user_message_id,
        "assistant_message_id": stream_session.assistant_message_id,
        "message_id": finalized_message.message_id if finalized_message is not None else stream_session.assistant_message_id,
        "thinking_content": None,
        "memory_state": memory_state,
        "context_source": {
            "recent_message_count": 0,
            "summary_present": bool(memory_state.get("summary_present")) if isinstance(memory_state, dict) else False,
            "citation_count": 0,
        },
        "request_group_id": stream_session.request_group_id,
        "provider_ref": stream_session.provider_ref,
        "title_updated": False,
    }
    stream_session.append(event="metadata", data=metadata_payload)
    stream_session.append(
        event="status",
        data=build_stream_status_payload(
            status="failed",
            stream_session=stream_session,
            attempt=attempt,
            max_attempts=max_attempts,
        ),
    )
    stream_session.append(event="error", data={**metadata_payload, "message": answer})
    stream_session.complete()


def run_stream_worker(
    *,
    stream_session,
    chat_request: ChatRequest,
    current_user: AuthenticatedUser,
    requested_scope: str,
    provider_override,
) -> None:
    session_service = get_session_service()
    settings_service = get_settings_service()
    max_attempts = 5

    try:
        user_settings = settings_service.get_user_settings(owner_user_id=current_user.user_id)
        resolved_provider, chat_provider = settings_service.build_chat_provider(
            owner_user_id=current_user.user_id,
            provider_override=provider_override,
        )
        stream_session.provider_ref = resolved_provider.provider_ref
    except Exception:
        emit_terminal_stream_error(
            stream_session=stream_session,
            session_service=session_service,
            owner_user_id=current_user.user_id,
            requested_scope=requested_scope,
            answer="本次未能连接到模型，请稍后重试或检查模型设置。",
            attempt=1,
            max_attempts=max_attempts,
        )
        return

    stream_session.append(
        event="message_start",
        data={
            "trace_id": stream_session.trace_id,
            "user_message_id": stream_session.user_message_id,
            "assistant_message_id": stream_session.assistant_message_id,
            "request_group_id": stream_session.request_group_id,
        },
    )

    attempt = 1
    while attempt <= max_attempts:
        stream_session.attempt = attempt
        synthetic_thinking_emitted = False
        stream_session.append(
            event="status",
            data=build_stream_status_payload(
                status="connecting" if attempt == 1 else "reconnecting",
                stream_session=stream_session,
                attempt=attempt,
                max_attempts=max_attempts,
            ),
        )

        try:
            handle = AIRuntimeOrchestrator(chat_provider=chat_provider).run_stream(chat_request)
            streaming_announced = False
            for event in handle.events:
                if event.kind == "status":
                    status = event.data.get("status")
                    if status == "thinking":
                        stream_session.append(
                            event="status",
                            data=build_stream_status_payload(
                                status="thinking",
                                stream_session=stream_session,
                                attempt=attempt,
                                max_attempts=max_attempts,
                            ),
                        )
                        if not synthetic_thinking_emitted:
                            synthetic_thinking_emitted = True
                            stream_session.append(
                                event="thinking_delta",
                                data={
                                    "delta": "正在整理问题与依据…",
                                    "trace_id": stream_session.trace_id,
                                    "user_message_id": stream_session.user_message_id,
                                    "assistant_message_id": stream_session.assistant_message_id,
                                    "request_group_id": stream_session.request_group_id,
                                    "synthetic": True,
                                },
                            )
                    continue

                if event.kind == "thinking_delta":
                    stream_session.append(
                        event="thinking_delta",
                        data={
                            **event.data,
                            "trace_id": stream_session.trace_id,
                            "user_message_id": stream_session.user_message_id,
                            "assistant_message_id": stream_session.assistant_message_id,
                            "request_group_id": stream_session.request_group_id,
                        },
                    )
                    continue

                if event.kind == "answer_delta":
                    if not streaming_announced:
                        streaming_announced = True
                        stream_session.has_first_answer_token = True
                        stream_session.append(
                            event="status",
                            data=build_stream_status_payload(
                                status="streaming",
                                stream_session=stream_session,
                                attempt=attempt,
                                max_attempts=max_attempts,
                                recovered=attempt > 1,
                            ),
                        )
                    stream_session.append(
                        event="answer_delta",
                        data={
                            **event.data,
                            "trace_id": stream_session.trace_id,
                            "user_message_id": stream_session.user_message_id,
                            "assistant_message_id": stream_session.assistant_message_id,
                            "request_group_id": stream_session.request_group_id,
                        },
                    )
                    continue

                if event.kind == "error":
                    raise ChatProviderError(
                        event.data.get("message", "Chat provider stream failed."),
                        reason=str(event.data.get("reason", "network_error")),
                        status_code=event.data.get("status_code"),
                    )

            result = handle.state.runtime_result
            if result is None:
                raise ChatProviderError(
                    "Chat provider stream ended unexpectedly.",
                    reason="invalid_response",
                )

            if result.status != "ok":
                raise ChatProviderError(
                    result.response.answer or "Chat provider stream failed.",
                    reason=str(result.metadata.get("provider_metadata", {}).get("error_reason", "network_error")),
                    status_code=result.metadata.get("provider_metadata", {}).get("provider_status_code"),
                )

            citations = [AskCitation.model_validate(item) for item in result.citations]
            source_summary = AskSourceSummary.model_validate(result.source_summary)
            thinking_content = "".join(handle.state.thinking_fragments).strip() or None
            finalized_message = session_service.finalize_exchange(
                owner_user_id=current_user.user_id,
                session_id=stream_session.session_id,
                assistant_message_id=stream_session.assistant_message_id,
                assistant_content=result.response.answer,
                assistant_status=resolve_final_message_status(result.status),
                trace_id=stream_session.trace_id,
                citations=citations,
                knowledge_scope=source_summary.knowledge_scope,
                source_summary=source_summary,
                thinking_content=thinking_content,
            )
            previous_session = session_service.get_session(owner_user_id=current_user.user_id, session_id=stream_session.session_id)
            previous_title = previous_session.title if previous_session else ""
            updated_summary = session_service.maybe_promote_title_after_success(
                owner_user_id=current_user.user_id,
                session_id=stream_session.session_id,
                enabled=user_settings.chat.auto_generate_title_for_new_session,
            )
            title_updated = bool(updated_summary and updated_summary.title != previous_title)
            refreshed_session = session_service.get_session(owner_user_id=current_user.user_id, session_id=stream_session.session_id)
            memory_state = refreshed_session.memory_state.model_dump(mode="json") if refreshed_session and refreshed_session.memory_state else None
            context_source = {
                "recent_message_count": result.context_summary.get("session_message_count", 0),
                "summary_present": result.context_summary.get("summary_present", False),
                "citation_count": len(citations),
            }
            metadata_payload = {
                "answer": result.response.answer,
                "status": result.status,
                "citations": [citation.model_dump() for citation in citations],
                "source_summary": source_summary.model_dump(),
                "trace_id": stream_session.trace_id,
                "user_message_id": stream_session.user_message_id,
                "assistant_message_id": stream_session.assistant_message_id,
                "message_id": finalized_message.message_id if finalized_message is not None else stream_session.assistant_message_id,
                "thinking_content": thinking_content,
                "memory_state": memory_state,
                "context_source": context_source,
                "request_group_id": stream_session.request_group_id,
                "provider_ref": stream_session.provider_ref,
                "title_updated": title_updated,
            }
            stream_session.append(event="metadata", data=metadata_payload)
            stream_session.append(
                event="status",
                data=build_stream_status_payload(
                    status="done",
                    stream_session=stream_session,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    recovered=attempt > 1,
                ),
            )
            stream_session.append(event="done", data=metadata_payload)
            stream_session.complete()
            return
        except ChatProviderError as exc:
            if not stream_session.has_first_answer_token and attempt < max_attempts and is_retryable_provider_error(exc, first_token_received=False):
                time.sleep(get_retry_delay(attempt))
                attempt += 1
                continue

            emit_terminal_stream_error(
                stream_session=stream_session,
                session_service=session_service,
                owner_user_id=current_user.user_id,
                requested_scope=requested_scope,
                answer="本次未能连接到模型，请稍后重试或检查模型设置。",
                attempt=attempt,
                max_attempts=max_attempts,
            )
            return
        except Exception:
            if not stream_session.has_first_answer_token and attempt < max_attempts:
                time.sleep(get_retry_delay(attempt))
                attempt += 1
                continue

            emit_terminal_stream_error(
                stream_session=stream_session,
                session_service=session_service,
                owner_user_id=current_user.user_id,
                requested_scope=requested_scope,
                answer="本次未能连接到模型，请稍后重试或检查模型设置。",
                attempt=attempt,
                max_attempts=max_attempts,
            )
            return


@router.post("", response_model=SessionSummary)
def create_session(
    payload: CreateSessionRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> SessionSummary:
    return get_session_service().create_session(owner_user_id=current_user.user_id, title=payload.title)


@router.get("", response_model=list[SessionSummary])
def list_sessions(current_user: AuthenticatedUser = Depends(require_authenticated_user)) -> list[SessionSummary]:
    return get_session_service().list_sessions(owner_user_id=current_user.user_id)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> SessionDetail:
    session = get_session_service().get_session(owner_user_id=current_user.user_id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.patch("/{session_id}", response_model=SessionSummary)
def update_session_title(
    session_id: str,
    payload: UpdateSessionRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> SessionSummary:
    session = get_session_service().update_session_title(
        owner_user_id=current_user.user_id,
        session_id=session_id,
        title=payload.title,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


@router.post("/{session_id}/ask", response_model=AskResponse)
def ask_in_session(
    session_id: str,
    payload: AskRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AskResponse | JSONResponse:
    session_service = get_session_service()
    session = session_service.get_session(owner_user_id=current_user.user_id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    requested_scope = payload.knowledge_scope
    chat_request, _ = build_chat_request(session_id=session_id, payload=payload, current_user=current_user)
    validation_error = validate_chat_request(chat_request, knowledge_scope=requested_scope)
    if validation_error is not None:
        return validation_error

    try:
        settings_service = get_settings_service()
        user_settings = settings_service.get_user_settings(owner_user_id=current_user.user_id)
        _, chat_provider = settings_service.build_chat_provider(
            owner_user_id=current_user.user_id,
            provider_override=payload.provider_override,
        )
        result = AIRuntimeOrchestrator(chat_provider=chat_provider).run(chat_request)
    except SettingsValidationError as exc:
        return build_error_response(
            status_code=422,
            answer=str(exc),
            trace_id=chat_request.trace_id,
            knowledge_scope=requested_scope,
        )
    except Exception:
        source_summary = empty_source_summary(requested_scope)
        session_service.record_exchange(
            owner_user_id=current_user.user_id,
            session_id=session_id,
            user_content=chat_request.user_input,
            assistant_content="当前问答服务暂不可用，请稍后重试。",
            assistant_status="provider_error",
            trace_id=chat_request.trace_id,
            citations=[],
            knowledge_scope=requested_scope,
            source_summary=source_summary,
        )
        return build_error_response(
            status_code=502,
            answer="当前问答服务暂不可用，请稍后重试。",
            trace_id=chat_request.trace_id,
            knowledge_scope=requested_scope,
        )

    citations = [AskCitation.model_validate(citation) for citation in result.citations]
    source_summary = AskSourceSummary.model_validate(result.source_summary)
    session_service.record_exchange(
        owner_user_id=current_user.user_id,
        session_id=session_id,
        user_content=chat_request.user_input,
        assistant_content=result.response.answer,
        assistant_status=resolve_final_message_status(result.status),
        trace_id=result.trace_id,
        citations=citations,
        knowledge_scope=source_summary.knowledge_scope,
        source_summary=source_summary,
    )
    if result.status == "ok":
        session_service.maybe_promote_title_after_success(
            owner_user_id=current_user.user_id,
            session_id=session_id,
            enabled=user_settings.chat.auto_generate_title_for_new_session,
        )

    response = AskResponse(
        answer=result.response.answer,
        mode="ask",
        status=result.status,
        citations=citations,
        source_summary=source_summary,
        trace_id=result.trace_id,
    )
    if result.status == "provider_error":
        return JSONResponse(status_code=502, content=response.model_dump())
    if result.status == "invalid_input":
        return JSONResponse(status_code=422, content=response.model_dump())
    return response


@router.post("/{session_id}/ask/stream", response_model=None)
def ask_in_session_stream(
    session_id: str,
    payload: AskRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> StreamingResponse | JSONResponse:
    session_service = get_session_service()
    session = session_service.get_session(owner_user_id=current_user.user_id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    requested_scope = payload.knowledge_scope
    chat_request, _ = build_chat_request(session_id=session_id, payload=payload, current_user=current_user)
    validation_error = validate_chat_request(chat_request, knowledge_scope=requested_scope)
    if validation_error is not None:
        return validation_error

    request_group_id = payload.request_group_id or f"reqgrp-{uuid4().hex[:12]}"
    registry = get_active_stream_registry()
    stream_session = registry.get(request_group_id)

    if stream_session is not None:
        if stream_session.owner_user_id != current_user.user_id or stream_session.session_id != session_id:
            raise HTTPException(status_code=409, detail="request_group_id is already bound to another session.")
    else:
        user_message, assistant_placeholder = session_service.begin_exchange(
            owner_user_id=current_user.user_id,
            session_id=session_id,
            user_content=chat_request.user_input,
        )
        stream_session = registry.create(
            request_group_id=request_group_id,
            owner_user_id=current_user.user_id,
            session_id=session_id,
            user_message_id=user_message.message_id,
            assistant_message_id=assistant_placeholder.message_id,
            trace_id=chat_request.trace_id,
        )
        threading.Thread(
            target=run_stream_worker,
            kwargs={
                "stream_session": stream_session,
                "chat_request": chat_request,
                "current_user": current_user,
                "requested_scope": requested_scope,
                "provider_override": payload.provider_override,
            },
            daemon=True,
        ).start()

    resume_cursor = payload.resume_cursor or 0

    def event_stream():
        for buffered_event in stream_session.subscribe(after_cursor=resume_cursor):
            yield build_sse_event(
                buffered_event.event,
                {
                    **buffered_event.data,
                    "event_seq": buffered_event.seq,
                },
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
