import math
import re
from datetime import datetime, timezone
from functools import lru_cache

from app.ai_runtime.providers.base import BaseChatProvider, ChatProviderError
from app.ai_runtime.providers.factory import get_chat_provider
from app.core.config import get_settings
from app.memory.schemas import (
    CreateMemoryNoteRequest,
    MemoryNote,
    MemoryState,
    SessionMemoryBundle,
    SessionMemorySnapshot,
    UpdateMemoryNoteRequest,
)
from app.settings.schemas import LocalProviderOverride
from app.settings.service import get_settings_service
from app.memory.store import MemoryStore, get_memory_store


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryService:
    def __init__(self, *, store: MemoryStore | None = None, chat_provider: BaseChatProvider | None = None) -> None:
        self.store = store or get_memory_store()
        self._chat_provider_injected = chat_provider is not None
        self.chat_provider = chat_provider or get_chat_provider()
        self.settings = get_settings()

    def list_notes(self, *, owner_user_id: str, enabled_only: bool = False) -> list[MemoryNote]:
        notes = self.store.list_notes(owner_user_id=owner_user_id, enabled_only=enabled_only)
        return self._trim_notes(notes) if enabled_only else notes

    def create_note(self, *, owner_user_id: str, payload: CreateMemoryNoteRequest) -> MemoryNote:
        timestamp = utcnow().isoformat()
        return self.store.create_note(
            owner_user_id=owner_user_id,
            title=payload.title,
            content=payload.content,
            is_enabled=payload.is_enabled,
            created_at=timestamp,
        )

    def update_note(self, *, owner_user_id: str, memory_note_id: str, payload: UpdateMemoryNoteRequest) -> MemoryNote | None:
        return self.store.update_note(
            owner_user_id=owner_user_id,
            memory_note_id=memory_note_id,
            title=payload.title,
            content=payload.content,
            is_enabled=payload.is_enabled,
            updated_at=utcnow().isoformat(),
        )

    def delete_note(self, *, owner_user_id: str, memory_note_id: str) -> bool:
        return self.store.delete_note(owner_user_id=owner_user_id, memory_note_id=memory_note_id)

    def get_session_memory_state(self, *, owner_user_id: str, session_id: str) -> MemoryState | None:
        snapshot = self.store.get_session_memory_snapshot(owner_user_id=owner_user_id, session_id=session_id)
        if snapshot is None:
            return None
        return self._build_memory_state(snapshot=snapshot, upcoming_user_input="")

    def build_session_context(
        self,
        *,
        owner_user_id: str,
        session_id: str,
        upcoming_user_input: str,
        max_turns: int | None = None,
        provider_override: LocalProviderOverride | dict | None = None,
    ) -> SessionMemoryBundle:
        snapshot = self.store.get_session_memory_snapshot(owner_user_id=owner_user_id, session_id=session_id)
        if snapshot is None:
            raise KeyError(f"Unknown session: {session_id}")

        self._maybe_compact(
            snapshot=snapshot,
            owner_user_id=owner_user_id,
            session_id=session_id,
            upcoming_user_input=upcoming_user_input,
            max_turns=max_turns,
            provider_override=provider_override,
        )
        refreshed = self.store.get_session_memory_snapshot(owner_user_id=owner_user_id, session_id=session_id)
        if refreshed is None:
            raise KeyError(f"Unknown session: {session_id}")

        recent_messages = self._select_recent_messages(refreshed.messages, max_turns=max_turns)
        notes = self.list_notes(owner_user_id=owner_user_id, enabled_only=True)
        memory_state = self._build_memory_state(snapshot=refreshed, upcoming_user_input=upcoming_user_input, recent_messages=recent_messages, notes=notes)
        return SessionMemoryBundle(
            recent_messages=[{"role": message.role, "content": message.content} for message in recent_messages],
            session_summary=refreshed.session_summary,
            memory_notes=notes,
            context_usage_estimate=memory_state.context_usage_estimate,
            context_budget_estimate=memory_state.context_budget_estimate,
            compacted_message_count=memory_state.compacted_message_count,
            compaction_status=memory_state.compaction_status,
            summary_updated_at=memory_state.summary_updated_at,
            summary_present=memory_state.summary_present,
            summary_estimated_tokens=memory_state.summary_estimated_tokens,
        )

    def _maybe_compact(
        self,
        *,
        snapshot: SessionMemorySnapshot,
        owner_user_id: str,
        session_id: str,
        upcoming_user_input: str,
        max_turns: int | None,
        provider_override: LocalProviderOverride | dict | None,
    ) -> None:
        recent_keep_count = self._recent_keep_count(max_turns=max_turns)
        conversation_messages = [message for message in snapshot.messages if message.role in {"user", "assistant"}]
        unsummarized_messages = [
            message
            for message in conversation_messages
            if snapshot.summary_message_seq_upto is None or message.message_seq > snapshot.summary_message_seq_upto
        ]
        usage_estimate = self._estimate_usage(
            session_summary=snapshot.session_summary,
            messages=self._select_recent_messages(snapshot.messages, max_turns=max_turns),
            upcoming_user_input=upcoming_user_input,
            notes=self.list_notes(owner_user_id=owner_user_id, enabled_only=True),
        )
        should_compact = (
            len(unsummarized_messages) > recent_keep_count
            or usage_estimate > self.settings.memory_compaction_trigger_estimate
        )
        if not should_compact:
            if snapshot.compaction_status == "failed":
                return
            self.store.update_session_memory(
                owner_user_id=owner_user_id,
                session_id=session_id,
                session_summary=snapshot.session_summary,
                summary_message_seq_upto=snapshot.summary_message_seq_upto,
                summary_updated_at=snapshot.summary_updated_at.isoformat() if snapshot.summary_updated_at else None,
                summary_estimated_tokens=snapshot.summary_estimated_tokens,
                compaction_status="idle" if snapshot.session_summary is None else "compacted",
                last_compaction_error=None,
            )
            return

        if len(unsummarized_messages) > recent_keep_count:
            messages_to_compact = unsummarized_messages[:-recent_keep_count]
        else:
            minimum_recent = min(len(unsummarized_messages), self.settings.memory_min_recent_message_count)
            messages_to_compact = unsummarized_messages[:-minimum_recent] if minimum_recent else []

        if not messages_to_compact:
            return

        try:
            new_summary = self._generate_summary(
                owner_user_id=owner_user_id,
                existing_summary=snapshot.session_summary,
                messages=messages_to_compact,
                provider_override=provider_override,
            )
        except ChatProviderError as exc:
            if self._should_use_local_compaction_fallback(provider_override=provider_override):
                new_summary = self._generate_extractive_summary(
                    existing_summary=snapshot.session_summary,
                    messages=messages_to_compact,
                )
            else:
                self.store.update_session_memory(
                    owner_user_id=owner_user_id,
                    session_id=session_id,
                    session_summary=snapshot.session_summary,
                    summary_message_seq_upto=snapshot.summary_message_seq_upto,
                    summary_updated_at=snapshot.summary_updated_at.isoformat() if snapshot.summary_updated_at else None,
                    summary_estimated_tokens=snapshot.summary_estimated_tokens,
                    compaction_status="failed",
                    last_compaction_error=str(exc),
                )
                return

        summary_updated_at = utcnow()
        self.store.update_session_memory(
            owner_user_id=owner_user_id,
            session_id=session_id,
            session_summary=new_summary,
            summary_message_seq_upto=messages_to_compact[-1].message_seq,
            summary_updated_at=summary_updated_at.isoformat(),
            summary_estimated_tokens=self.estimate_text_tokens(new_summary),
            compaction_status="compacted",
            last_compaction_error=None,
        )

    def _generate_summary(
        self,
        *,
        owner_user_id: str,
        existing_summary: str | None,
        messages,
        provider_override: LocalProviderOverride | dict | None,
    ) -> str:
        transcript_lines = []
        if existing_summary:
            transcript_lines.extend(
                [
                    "已有会话摘要：",
                    existing_summary,
                    "",
                ]
            )
        transcript_lines.append("请在保留事实、结论、待办和关键依据线索的前提下，压缩下面这些较早的对话。")
        for index, message in enumerate(messages, start=1):
            role_label = "用户" if message.role == "user" else "助手"
            transcript_lines.append(f"[{index}] {role_label}：{message.content}")

        chat_provider = self.chat_provider
        if provider_override is not None or self.chat_provider is None:
            _, chat_provider = get_settings_service().build_chat_provider(
                owner_user_id=owner_user_id,
                provider_override=provider_override,
            )

        result = chat_provider.generate_response(
            system_prompt=(
                "你是 CarbonRag 的会话压缩器。"
                "你的任务是把较早的对话压缩为一段稳定、精炼的会话摘要，"
                "保留已确认的目标、关键事实、未解决问题、用户约束和重要依据线索。"
                "不要捏造新事实，不要使用项目符号以外的复杂格式，输出中文。"
            ),
            user_input="\n".join(transcript_lines),
        )
        return result.content.strip()

    def _generate_extractive_summary(self, *, existing_summary: str | None, messages) -> str:
        lines: list[str] = []
        if existing_summary:
            lines.append(existing_summary.strip())
        lines.append("以下为系统在模型不可用时生成的本地会话摘要：")
        for message in messages:
            role_label = "用户" if message.role == "user" else "助手"
            content = " ".join(str(message.content or "").split())
            if len(content) > 180:
                content = f"{content[:180].rstrip()}..."
            if content:
                lines.append(f"- {role_label}：{content}")
        return "\n".join(line for line in lines if line).strip()

    def _should_use_local_compaction_fallback(self, *, provider_override: LocalProviderOverride | dict | None) -> bool:
        if self._chat_provider_injected or provider_override is not None:
            return False
        return (
            self.settings.model_api_key == "replace-with-model-api-key"
            or self.settings.model_api_base_url.rstrip("/") == "https://api.example.com/v1"
        )

    def _build_memory_state(
        self,
        *,
        snapshot: SessionMemorySnapshot,
        upcoming_user_input: str,
        recent_messages=None,
        notes: list[MemoryNote] | None = None,
    ) -> MemoryState:
        effective_recent = recent_messages or self._select_recent_messages(snapshot.messages)
        effective_notes = notes if notes is not None else self.list_notes(owner_user_id=snapshot.owner_user_id, enabled_only=True)
        return MemoryState(
            context_usage_estimate=self._estimate_usage(
                session_summary=snapshot.session_summary,
                messages=effective_recent,
                upcoming_user_input=upcoming_user_input,
                notes=effective_notes,
            ),
            context_budget_estimate=self.settings.memory_context_budget_estimate,
            summary_present=bool(snapshot.session_summary),
            summary_updated_at=snapshot.summary_updated_at,
            compacted_message_count=self.store.count_compacted_messages(
                session_id=snapshot.session_id,
                summary_message_seq_upto=snapshot.summary_message_seq_upto,
            ),
            compaction_status=snapshot.compaction_status,
            summary_estimated_tokens=snapshot.summary_estimated_tokens,
        )

    def _estimate_usage(self, *, session_summary: str | None, messages, upcoming_user_input: str, notes: list[MemoryNote]) -> int:
        total = 0
        if session_summary:
            total += self.estimate_text_tokens(session_summary)
        total += sum(self.estimate_text_tokens(message.content) for message in messages)
        total += sum(self.estimate_text_tokens(note.content) for note in notes)
        if upcoming_user_input:
            total += self.estimate_text_tokens(upcoming_user_input)
        return total

    def _select_recent_messages(self, messages, *, max_turns: int | None = None):
        recent_keep_count = self._recent_keep_count(max_turns=max_turns)
        conversation_messages = [message for message in messages if message.role in {"user", "assistant"}]
        return conversation_messages[-recent_keep_count:]

    def _recent_keep_count(self, *, max_turns: int | None = None) -> int:
        turns = max_turns or self.settings.memory_recent_turn_window
        return max(2, turns * 2)

    def _trim_notes(self, notes: list[MemoryNote]) -> list[MemoryNote]:
        trimmed: list[MemoryNote] = []
        total_chars = 0
        for note in notes:
            if len(trimmed) >= self.settings.memory_note_read_limit:
                break
            remaining = self.settings.memory_note_max_chars - total_chars
            if remaining <= 0:
                break
            content = note.content if len(note.content) <= remaining else note.content[:remaining].rstrip()
            trimmed.append(note.model_copy(update={"content": content}))
            total_chars += len(content)
        return trimmed

    @staticmethod
    def estimate_text_tokens(text: str | None) -> int:
        if not text:
            return 0
        cjk_chars = sum(1 for character in text if "\u4e00" <= character <= "\u9fff")
        ascii_words = re.findall(r"[A-Za-z0-9_/-]+", text)
        remaining_chars = max(len(text) - cjk_chars, 0)
        return max(1, cjk_chars + len(ascii_words) * 2 + math.ceil(remaining_chars / 6))


@lru_cache(maxsize=1)
def get_memory_service() -> MemoryService:
    return MemoryService()
