import inspect
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import get_settings
from app.ai_runtime.providers.base import BaseChatProvider
from app.private_samples.catalog import list_attachable_private_sample_catalog
from app.memory.service import get_memory_service
from app.schemas.ask import AskCitation, AskSourceSummary, KnowledgeScope, MessageStatus
from app.settings.schemas import LocalProviderOverride
from app.session.schemas import SessionDetail, SessionMessage, SessionSummary, UploadedFile
from app.session.store import SessionStore, get_session_store

DEFAULT_TITLE_PREFIX = "未命名会话"
LEGACY_TEMP_TITLE_PREFIXES = ("新对话", "新聊天", DEFAULT_TITLE_PREFIX)
DEFAULT_CONTEXT_TURNS = 6


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_default_knowledge_service():
    from app.knowledge.service import get_knowledge_service

    return get_knowledge_service()


def _get_knowledge_service():
    return _get_default_knowledge_service()


def _sanitize_auto_title(raw_title: str) -> str | None:
    normalized = " ".join(raw_title.replace("\n", " ").split()).strip()
    if not normalized:
        return None

    prefixes = ("标题：", "标题:", "会话标题：", "会话标题:", "总结标题：", "总结标题:")
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()

    normalized = normalized.strip("「」\"'“”‘’`，。.!！?？、：:")
    if not normalized:
        return None

    max_length = 28
    return normalized if len(normalized) <= max_length else f"{normalized[:max_length].rstrip()}..."


class SessionService:
    def __init__(self, store: SessionStore | None = None, knowledge_service=None, memory_service=None) -> None:
        self.store = store or get_session_store()
        self.knowledge_service = knowledge_service
        self.memory_service = memory_service
        self._derived_memory_service = None

    def create_session(self, *, owner_user_id: str, title: str | None = None) -> SessionSummary:
        created_at = utcnow()
        session_id = f"session-{uuid4().hex[:12]}"
        session_title = title or DEFAULT_TITLE_PREFIX
        return self.store.create_session(
            session_id=session_id,
            owner_user_id=owner_user_id,
            title=session_title,
            created_at=created_at.isoformat(),
        )

    def list_sessions(self, *, owner_user_id: str) -> list[SessionSummary]:
        sessions = self.store.list_sessions(owner_user_id=owner_user_id)
        return [
            self._normalize_summary_title(owner_user_id=owner_user_id, summary=session)
            for session in sessions
        ]

    def get_session(self, *, owner_user_id: str, session_id: str) -> SessionDetail | None:
        session = self.store.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if session is None:
            return None
        session = self._normalize_detail_title(owner_user_id=owner_user_id, session=session)
        memory_state = self._get_memory_service().get_session_memory_state(owner_user_id=owner_user_id, session_id=session_id)
        return session.model_copy(update={"memory_state": memory_state})

    def require_session(self, *, owner_user_id: str, session_id: str) -> SessionDetail:
        session = self.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        return session

    def update_session_title(self, *, owner_user_id: str, session_id: str, title: str) -> SessionSummary | None:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        return self.store.update_session_title(
            session_id=session_id,
            title=title,
            updated_at=utcnow().isoformat(),
        )

    def update_session(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        title: str | None = None,
        is_pinned: bool | None = None,
    ) -> SessionSummary | None:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        updated: SessionSummary | None = self.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if title is not None:
            updated = self.store.update_session_title(
                session_id=session_id,
                title=title,
                updated_at=utcnow().isoformat(),
            )
        if is_pinned is not None:
            updated = self.store.update_session_pin(
                session_id=session_id,
                is_pinned=is_pinned,
                pinned_at=utcnow().isoformat() if is_pinned else None,
                updated_at=utcnow().isoformat(),
            )
        return updated

    def delete_session(self, *, owner_user_id: str, session_id: str) -> bool:
        if self.get_session(owner_user_id=owner_user_id, session_id=session_id) is None:
            return False
        return self.store.delete_session(owner_user_id=owner_user_id, session_id=session_id)

    def build_session_context(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        max_turns: int = DEFAULT_CONTEXT_TURNS,
        upcoming_user_input: str = "",
        provider_override: LocalProviderOverride | dict | None = None,
    ) -> dict:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        memory_service = self._get_memory_service()
        build_method = memory_service.build_session_context
        kwargs = {
            "owner_user_id": owner_user_id,
            "session_id": session_id,
            "max_turns": max_turns,
            "upcoming_user_input": upcoming_user_input,
        }
        if "provider_override" in inspect.signature(build_method).parameters:
            kwargs["provider_override"] = provider_override
        return build_method(
            **kwargs,
        ).model_dump(mode="json")

    def record_exchange(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        user_content: str,
        assistant_content: str,
        assistant_status: MessageStatus,
        trace_id: str,
        citations: list[AskCitation],
        knowledge_scope: KnowledgeScope = "mixed",
        source_summary: AskSourceSummary | None = None,
    ) -> tuple[SessionMessage, SessionMessage | None]:
        user_message, assistant_placeholder = self.begin_exchange(
            owner_user_id=owner_user_id,
            session_id=session_id,
            user_content=user_content,
        )
        assistant_message = self.finalize_exchange(
            owner_user_id=owner_user_id,
            session_id=session_id,
            assistant_message_id=assistant_placeholder.message_id,
            assistant_content=assistant_content,
            assistant_status=assistant_status,
            trace_id=trace_id,
            citations=citations,
            knowledge_scope=knowledge_scope,
            source_summary=source_summary,
        )
        return user_message, assistant_message

    def begin_exchange(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        user_content: str,
    ) -> tuple[SessionMessage, SessionMessage]:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        timestamp = utcnow()
        user_message = self.store.append_message(
            session_id=session_id,
            message_id=f"msg-{uuid4().hex[:12]}",
            role="user",
            content=user_content,
            created_at=timestamp.isoformat(),
        )
        assistant_message = self.store.append_message(
            session_id=session_id,
            message_id=f"msg-{uuid4().hex[:12]}",
            role="assistant",
            content="",
            created_at=utcnow().isoformat(),
            status="pending",
        )
        return user_message, assistant_message

    def finalize_exchange(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        assistant_message_id: str,
        assistant_content: str,
        assistant_status: MessageStatus,
        trace_id: str,
        citations: list[AskCitation],
        knowledge_scope: KnowledgeScope = "mixed",
        source_summary: AskSourceSummary | None = None,
        thinking_content: str | None = None,
    ) -> SessionMessage | None:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        updated_message = self.store.update_message(
            session_id=session_id,
            message_id=assistant_message_id,
            content=assistant_content,
            updated_at=utcnow().isoformat(),
            status=assistant_status,
            trace_id=trace_id,
            citations=citations,
            thinking_content=thinking_content,
        )
        effective_source_summary = source_summary or AskSourceSummary(
            knowledge_scope=knowledge_scope,
            public_policy_count=sum(1 for citation in citations if citation.source_type == "public_policy"),
            public_policy_demo_count=sum(1 for citation in citations if citation.source_type == "public_policy_demo"),
            private_sample_count=sum(1 for citation in citations if citation.source_type == "private_sample"),
            private_upload_count=sum(1 for citation in citations if citation.source_type == "private_upload"),
            total_citation_count=len(citations),
        )
        self.store.update_session_runtime_state(
            session_id=session_id,
            updated_at=utcnow().isoformat(),
            knowledge_scope_last_used=knowledge_scope,
            source_summary=effective_source_summary,
        )
        return updated_message

    def maybe_promote_title_after_success(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        enabled: bool = True,
        chat_provider: BaseChatProvider | None = None,
    ) -> SessionSummary | None:
        if not enabled:
            return self.get_session(owner_user_id=owner_user_id, session_id=session_id)

        session = self.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if session is None:
            return None

        valid_exchanges = self._collect_valid_title_exchanges(session.messages)
        if len(valid_exchanges) < 2:
            return session

        if len(valid_exchanges) > 2 and not session.title.startswith(DEFAULT_TITLE_PREFIX):
            return session

        promoted = self._build_auto_title_from_valid_exchanges(valid_exchanges[:2], chat_provider=chat_provider)
        if not promoted or promoted == session.title:
            return session
        return self.update_session_title(owner_user_id=owner_user_id, session_id=session_id, title=promoted)

    def maybe_generate_title_on_user_turn(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        enabled: bool = True,
        chat_provider: BaseChatProvider | None = None,
    ) -> SessionSummary | None:
        if not enabled:
            return self.get_session(owner_user_id=owner_user_id, session_id=session_id)

        session = self.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if session is None:
            return None

        user_messages = [
            message.content.strip()
            for message in session.messages
            if message.role == "user" and message.content.strip()
        ]
        user_turn_count = len(user_messages)
        if user_turn_count == 0 or user_turn_count > 2:
            return session

        if user_turn_count == 1:
            title_context = f"第 1 次用户发送：{user_messages[0]}"
            promoted = self._build_auto_title_from_context(
                title_context,
                fallback_user_messages=user_messages,
                chat_provider=chat_provider,
                phase="first_user_turn",
            )
        else:
            valid_exchanges = self._collect_valid_title_exchanges(session.messages)
            context_lines: list[str] = []
            if valid_exchanges:
                first_question, first_answer = valid_exchanges[0]
                context_lines.append(f"第 1 轮用户：{first_question}")
                context_lines.append(f"第 1 轮助手：{first_answer}")
            else:
                context_lines.append(f"第 1 次用户发送：{user_messages[0]}")
            context_lines.append(f"第 2 次用户发送：{user_messages[1]}")
            promoted = self._build_auto_title_from_context(
                "\n".join(context_lines),
                fallback_user_messages=user_messages[:2],
                chat_provider=chat_provider,
                phase="second_user_turn_refine",
            )

        if not promoted or promoted == session.title:
            return session
        return self.update_session_title(owner_user_id=owner_user_id, session_id=session_id, title=promoted)

    def maybe_promote_title_from_first_question(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        question: str | None = None,
    ) -> SessionSummary | None:
        session = self.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if session is None:
            return None

        valid_exchanges = self._collect_valid_title_exchanges(session.messages)
        if len(valid_exchanges) < 2:
            return session
        promoted = self._build_auto_title_from_valid_exchanges(valid_exchanges[:2], chat_provider=None)
        if not promoted or promoted == session.title:
            return session
        return self.update_session_title(owner_user_id=owner_user_id, session_id=session_id, title=promoted)

    @staticmethod
    def _build_auto_title_from_user_messages(user_messages: list[str]) -> str:
        merged = " ".join(fragment.replace("\n", " ").strip() for fragment in user_messages if fragment.strip())
        normalized = " ".join(merged.split())
        if not normalized:
            return DEFAULT_TITLE_PREFIX

        normalized = normalized.replace("？", "?").replace("。", " ").replace("，", " ")
        if "?" in normalized:
            normalized = normalized.split("?", 1)[0]
        max_length = 26
        return normalized if len(normalized) <= max_length else f"{normalized[:max_length].rstrip()}..."

    @staticmethod
    def _is_temporary_title(title: str | None) -> bool:
        normalized = (title or "").strip()
        if not normalized:
            return True
        return any(normalized.startswith(prefix) for prefix in LEGACY_TEMP_TITLE_PREFIXES)

    @classmethod
    def _build_auto_title_from_messages(cls, messages: list[SessionMessage]) -> str:
        user_messages = [
            message.content.strip()
            for message in messages
            if message.role == "user" and message.content.strip()
        ]
        return cls._build_auto_title_from_user_messages(user_messages[:3])

    def _normalize_summary_title(self, *, owner_user_id: str, summary: SessionSummary) -> SessionSummary:
        if not self._is_temporary_title(summary.title):
            return summary

        detail = self.store.get_session(owner_user_id=owner_user_id, session_id=summary.session_id)
        if detail is None:
            return summary
        normalized_title = self._build_auto_title_from_messages(detail.messages)
        if normalized_title == summary.title:
            return summary
        updated = self.store.update_session_title(
            session_id=summary.session_id,
            title=normalized_title,
            updated_at=summary.updated_at,
        )
        return updated or summary.model_copy(update={"title": normalized_title})

    def _normalize_detail_title(self, *, owner_user_id: str, session: SessionDetail) -> SessionDetail:
        if not self._is_temporary_title(session.title):
            return session

        normalized_title = self._build_auto_title_from_messages(session.messages)
        if normalized_title == session.title:
            return session
        self.store.update_session_title(
            session_id=session.session_id,
            title=normalized_title,
            updated_at=session.updated_at,
        )
        return session.model_copy(update={"title": normalized_title})

    @staticmethod
    def _collect_valid_title_exchanges(messages: list[SessionMessage]) -> list[tuple[str, str]]:
        valid_exchanges: list[tuple[str, str]] = []
        pending_user: str | None = None
        for message in messages:
            content = message.content.strip()
            if message.role == "user":
                pending_user = content or None
                continue
            if message.role != "assistant":
                continue
            if pending_user is None:
                continue
            if message.status not in {"ok", "done"} or not content:
                pending_user = None
                continue
            valid_exchanges.append((pending_user, content))
            pending_user = None
        return valid_exchanges

    @classmethod
    def _build_auto_title_from_valid_exchanges(
        cls,
        exchanges: list[tuple[str, str]],
        *,
        chat_provider: BaseChatProvider | None,
    ) -> str:
        if not exchanges:
            return DEFAULT_TITLE_PREFIX

        if chat_provider is not None:
            title = cls._generate_auto_title_with_provider(exchanges, chat_provider=chat_provider)
            if title:
                return title

        user_messages = [question for question, _ in exchanges]
        return cls._build_auto_title_from_user_messages(user_messages)

    @classmethod
    def _build_auto_title_from_context(
        cls,
        title_context: str,
        *,
        fallback_user_messages: list[str],
        chat_provider: BaseChatProvider | None,
        phase: str,
    ) -> str:
        if chat_provider is not None:
            title = cls._generate_auto_title_from_context(
                title_context,
                chat_provider=chat_provider,
                phase=phase,
            )
            if title:
                return title
        return cls._build_auto_title_from_user_messages(fallback_user_messages)

    @staticmethod
    def _generate_auto_title_from_context(
        title_context: str,
        *,
        chat_provider: BaseChatProvider,
        phase: str,
    ) -> str | None:
        if phase == "first_user_turn":
            instruction = "请根据新会话的第一次用户发送，先生成一个临时中文短标题。"
        else:
            instruction = "请根据第一轮有效问答和第二次用户发送，修正为更准确的中文短标题。"
        try:
            result = chat_provider.generate_response(
                system_prompt=(
                    "你是 CarbonRag 的会话标题生成器。"
                    f"{instruction}"
                    "只输出标题本身，不要解释，不要加引号，不要超过 18 个汉字或 24 个英文字符。"
                ),
                user_input=title_context,
            )
        except Exception:
            return None

        return _sanitize_auto_title(result.content)

    @staticmethod
    def _generate_auto_title_with_provider(
        exchanges: list[tuple[str, str]],
        *,
        chat_provider: BaseChatProvider,
    ) -> str | None:
        conversation_lines: list[str] = []
        for index, (question, answer) in enumerate(exchanges[:2], start=1):
            conversation_lines.append(f"第 {index} 轮用户：{question}")
            conversation_lines.append(f"第 {index} 轮助手：{answer}")

        try:
            result = chat_provider.generate_response(
                system_prompt=(
                    "你是 CarbonRag 的会话标题生成器。"
                    "请根据前两轮有效问答生成一个中文短标题。"
                    "只输出标题本身，不要解释，不要加引号，不要超过 18 个汉字或 24 个英文字符。"
                ),
                user_input="\n".join(conversation_lines),
            )
        except Exception:
            return None

        return _sanitize_auto_title(result.content)

    def record_system_message(self, *, owner_user_id: str, session_id: str, content: str) -> SessionMessage:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        return self.store.append_message(
            session_id=session_id,
            message_id=f"msg-{uuid4().hex[:12]}",
            role="system",
            content=content,
            created_at=utcnow().isoformat(),
        )

    def record_uploaded_file(
        self,
        *,
        owner_user_id: str,
        file_id: str | None = None,
        session_id: str,
        filename: str,
        size: int,
        mime_type: str,
        storage_path: str,
        stored_filename: str | None = None,
        file_ext: str | None = None,
        sha256: str | None = None,
    ) -> UploadedFile:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        stored_at = utcnow().isoformat()
        return self.store.create_uploaded_file(
            file_id=file_id or f"file-{uuid4().hex[:12]}",
            session_id=session_id,
            filename=filename,
            size=size,
            mime_type=mime_type,
            stored_at=stored_at,
            storage_path=storage_path,
            stored_filename=stored_filename,
            file_ext=file_ext,
            sha256=sha256,
        )

    def list_private_sample_catalog(self):
        return list_attachable_private_sample_catalog(
            database_url=getattr(self.store, "database_url", None),
            sqlite_db_path=getattr(self.store, "db_path", None),
        )

    def replace_attached_private_samples(self, *, owner_user_id: str, session_id: str, doc_ids: list[str]) -> None:
        knowledge_item_ids = self._resolve_knowledge_item_ids(owner_user_id=owner_user_id, identifiers=doc_ids)
        self.replace_attached_knowledge_items(
            owner_user_id=owner_user_id,
            session_id=session_id,
            knowledge_item_ids=knowledge_item_ids,
        )

    def replace_attached_knowledge_items(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        knowledge_item_ids: list[str],
    ) -> None:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        knowledge_service = self._get_knowledge_service()
        allowed_items = {
            item.knowledge_item_id
            for item in knowledge_service.store.list_items(
                owner_user_id=owner_user_id,
                knowledge_item_ids=knowledge_item_ids,
            )
        }
        missing_ids = [item_id for item_id in knowledge_item_ids if item_id not in allowed_items]
        if missing_ids:
            raise ValueError(f"Unknown knowledge item: {missing_ids[0]}")
        deduplicated = list(dict.fromkeys(item_id for item_id in knowledge_item_ids if item_id.strip()))
        self.store.replace_attached_knowledge_items(
            session_id=session_id,
            knowledge_item_ids=deduplicated,
            attached_at=utcnow().isoformat(),
        )

    def list_attached_private_sample_ids(self, *, owner_user_id: str, session_id: str) -> list[str]:
        return self.list_attached_knowledge_item_ids(owner_user_id=owner_user_id, session_id=session_id)

    def list_attached_knowledge_item_ids(self, *, owner_user_id: str, session_id: str) -> list[str]:
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        return self.store.list_attached_knowledge_item_ids(session_id=session_id)

    def list_session_knowledge_items(self, *, owner_user_id: str, session_id: str):
        self.require_session(owner_user_id=owner_user_id, session_id=session_id)
        knowledge_service = self._get_knowledge_service()
        item_ids = self.list_attached_knowledge_item_ids(owner_user_id=owner_user_id, session_id=session_id)
        if not item_ids:
            return []
        return knowledge_service.list_visible_items(owner_user_id=owner_user_id, knowledge_item_ids=item_ids)

    def _resolve_knowledge_item_ids(self, *, owner_user_id: str, identifiers: list[str]) -> list[str]:
        normalized: list[str] = []
        knowledge_service = self._get_knowledge_service()
        catalog = {item.knowledge_item_id: item for item in knowledge_service.list_visible_items(owner_user_id=owner_user_id)}
        for raw_identifier in identifiers:
            candidate = raw_identifier.strip()
            if not candidate:
                continue
            if candidate in catalog:
                normalized.append(candidate)
                continue

            legacy_item = knowledge_service.store.get_item_by_source(
                owner_user_id=None,
                library_scope="shared",
                source_type="private_sample_repo",
                source_ref=candidate,
            )
            if legacy_item is not None and (
                legacy_item.owner_user_id is None or legacy_item.owner_user_id == owner_user_id
            ):
                normalized.append(legacy_item.knowledge_item_id)
                continue

            personal_upload = knowledge_service.store.get_item_by_source(
                owner_user_id=owner_user_id,
                library_scope="personal",
                source_type="uploaded_file",
                source_ref=candidate,
            )
            if personal_upload is not None:
                normalized.append(personal_upload.knowledge_item_id)
                continue

        return list(dict.fromkeys(normalized))

    def _get_knowledge_service(self):
        return self.knowledge_service or _get_knowledge_service()

    def _get_memory_service(self):
        if self.memory_service is not None:
            return self.memory_service
        if self._derived_memory_service is None:
            from app.memory.service import MemoryService
            from app.memory.store import build_memory_store

            settings = get_settings()
            self._derived_memory_service = MemoryService(
                store=build_memory_store(
                    database_url=getattr(self.store, "database_url", None),
                    sqlite_db_path=getattr(self.store, "db_path", None),
                    memory_backend=settings.memory_backend,
                )
            )
        return self._derived_memory_service or get_memory_service()


def get_session_service() -> SessionService:
    return SessionService()
