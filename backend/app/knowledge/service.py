from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Iterable, TYPE_CHECKING
from uuid import uuid4

from app.files.schemas import UploadedFileResponse
from app.knowledge.chunker import chunk_knowledge_text
from app.knowledge.parsers import KnowledgeParseError, parse_document
from app.knowledge.schemas import (
    KnowledgeItem,
    KnowledgeItemDetailResponse,
    KnowledgeItemListFilters,
    KnowledgeTask,
    KnowledgeTaskListFilters,
    MyUploadEntry,
    RepoPrivateSampleMetadata,
    RepoPrivateSampleSource,
)
from app.knowledge.store import KnowledgeStore
from app.private_samples.overrides import load_private_sample_override_map, update_private_sample_override
from app.retrieval.private_corpus_loader import load_private_sample_manifest, resolve_private_corpus_dir

if TYPE_CHECKING:
    from app.session.service import SessionService


class KnowledgeAccessError(PermissionError):
    pass


class KnowledgeValidationError(ValueError):
    pass


class KnowledgeService:
    def __init__(
        self,
        *,
        store: KnowledgeStore | None = None,
        session_service: "SessionService" | None = None,
    ) -> None:
        self.store = store or KnowledgeStore()
        if session_service is None:
            from app.session.service import get_session_service

            session_service = get_session_service()
        self.session_service = session_service
        if getattr(self.session_service, "knowledge_service", None) is None:
            self.session_service.knowledge_service = self
        self.bootstrap_shared_library()

    def bootstrap_shared_library(self) -> list[KnowledgeTask]:
        tasks: list[KnowledgeTask] = []
        override_map = load_private_sample_override_map(
            database_url=self.store.database_url,
            sqlite_db_path=self.store.sqlite_db_path,
        )
        for source in self._iter_repo_private_sources():
            override = override_map.get(source.metadata.doc_id, {})
            existing = self.store.get_item(knowledge_item_id=source.metadata.doc_id)
            should_enqueue = existing is None or existing.source_hash != source.source_hash or existing.source_mtime != source.source_mtime
            item = KnowledgeItem(
                knowledge_item_id=source.metadata.doc_id,
                owner_user_id=None,
                library_scope="shared",
                source_type="private_sample_repo",
                source_ref=source.metadata.doc_id,
                file_id=None,
                source="管理员共享样例",
                source_url=source.metadata.source_url,
                sample_type=source.metadata.sample_type,
                business_topic=source.metadata.business_topic,
                title=source.metadata.title,
                mime_type=source.mime_type,
                storage_path=source.storage_path,
                parse_status="pending" if should_enqueue else existing.parse_status if existing else "pending",
                ingest_status="pending" if should_enqueue else existing.ingest_status if existing else "pending",
                index_status="stale" if should_enqueue and existing else "pending" if should_enqueue else existing.index_status if existing else "pending",
                is_enabled=override.get("is_enabled", existing.is_enabled if existing else True),
                session_attachable=override.get("session_attachable", existing.session_attachable if existing else source.metadata.session_attachable),
                source_hash=source.source_hash,
                source_mtime=source.source_mtime,
                last_error=None if should_enqueue else existing.last_error if existing else None,
                created_at=existing.created_at if existing else self.store.utcnow(),
                updated_at=self.store.utcnow(),
                last_indexed_at=existing.last_indexed_at if existing else None,
            )
            self.store.upsert_item(item=item)
            if should_enqueue:
                tasks.append(self._enqueue_item_task(knowledge_item_id=item.knowledge_item_id, owner_user_id=None, requested_by_user_id=None, task_type="rebuild", summary="检测到共享样例新增或变更，已加入重建队列。"))
        return tasks

    def sync_shared_private_samples(self) -> list[KnowledgeTask]:
        return self.bootstrap_shared_library()

    def create_personal_item_from_upload(
        self,
        *,
        owner_user_id: str,
        uploaded_file: UploadedFileResponse | dict,
        storage_path: str,
    ) -> KnowledgeTask:
        payload = uploaded_file if isinstance(uploaded_file, UploadedFileResponse) else UploadedFileResponse.model_validate(uploaded_file)
        item = KnowledgeItem(
            knowledge_item_id=payload.file_id,
            owner_user_id=owner_user_id,
            library_scope="personal",
            source_type="uploaded_file",
            source_ref=payload.file_id,
            file_id=payload.file_id,
            source="用户上传知识",
            source_url=None,
            sample_type=None,
            business_topic=None,
            title=payload.filename,
            mime_type=payload.mime_type,
            storage_path=storage_path,
            parse_status="pending",
            ingest_status="pending",
            index_status="pending",
            is_enabled=True,
            session_attachable=True,
            source_hash=self._compute_file_hash(Path(storage_path)),
            source_mtime=self._safe_mtime(Path(storage_path)),
            last_error=None,
            created_at=self.store.utcnow(),
            updated_at=self.store.utcnow(),
            last_indexed_at=None,
        )
        self.store.upsert_item(item=item)
        return self._enqueue_item_task(
            knowledge_item_id=item.knowledge_item_id,
            owner_user_id=owner_user_id,
            requested_by_user_id=owner_user_id,
            task_type="upload_ingest",
            summary="上传文件已进入知识库入队流程。",
        )

    def list_visible_items(
        self,
        *,
        owner_user_id: str | None,
        filters: KnowledgeItemListFilters | None = None,
        **kwargs,
    ) -> list[KnowledgeItem]:
        merged_filters = filters or KnowledgeItemListFilters.model_validate(kwargs)
        return self.store.list_visible_items(owner_user_id=owner_user_id, filters=merged_filters)

    def list_admin_items(self, *, filters: KnowledgeItemListFilters | None = None, **kwargs) -> list[KnowledgeItem]:
        merged_filters = filters or KnowledgeItemListFilters.model_validate(kwargs)
        return self.store.list_admin_items(filters=merged_filters)

    def list_shared_items(
        self,
        *,
        source_type: str | None = None,
        session_attachable: bool | None = None,
        is_enabled: bool | None = None,
    ) -> list[KnowledgeItem]:
        return self.list_admin_items(
            library_scope="shared",
            source_type=source_type,
            session_attachable=session_attachable,
            is_enabled=is_enabled,
        )

    def list_personal_items(self, *, owner_user_id: str, source_type: str | None = None) -> list[KnowledgeItem]:
        return self.list_visible_items(
            owner_user_id=owner_user_id,
            library_scope="personal",
            source_type=source_type,
        )

    def discover_pending_sources(self) -> list[KnowledgeTask]:
        discovered = self.bootstrap_shared_library()
        discovered.extend(self.sync_uploaded_files())
        return discovered

    def refresh_all_sources(self) -> list[KnowledgeTask]:
        return self.discover_pending_sources()

    def sync_uploaded_files(self, *, owner_user_id: str | None = None) -> list[KnowledgeTask]:
        tasks: list[KnowledgeTask] = []
        for file_row in self.store.list_uploaded_files(owner_user_id=owner_user_id):
            storage_path = Path(file_row["storage_path"])
            if not storage_path.exists():
                continue
            source_hash = self._compute_file_hash(storage_path)
            source_mtime = self._safe_mtime(storage_path)
            existing = self.store.get_item(knowledge_item_id=str(file_row["file_id"]))
            should_enqueue = existing is None or existing.source_hash != source_hash or existing.source_mtime != source_mtime
            item = KnowledgeItem(
                knowledge_item_id=str(file_row["file_id"]),
                owner_user_id=str(file_row["owner_user_id"]) if file_row.get("owner_user_id") is not None else None,
                library_scope="personal",
                source_type="uploaded_file",
                source_ref=str(file_row["file_id"]),
                file_id=str(file_row["file_id"]),
                source="用户上传知识",
                source_url=None,
                sample_type=None,
                business_topic=None,
                title=str(file_row["filename"]),
                mime_type=str(file_row["mime_type"]),
                storage_path=str(storage_path),
                parse_status="pending" if should_enqueue else existing.parse_status if existing else "pending",
                ingest_status="pending" if should_enqueue else existing.ingest_status if existing else "pending",
                index_status="stale" if should_enqueue and existing else "pending" if should_enqueue else existing.index_status if existing else "pending",
                is_enabled=True,
                session_attachable=True,
                source_hash=source_hash,
                source_mtime=source_mtime,
                last_error=None if should_enqueue else existing.last_error if existing else None,
                created_at=existing.created_at if existing else self.store.utcnow(),
                updated_at=self.store.utcnow(),
                last_indexed_at=existing.last_indexed_at if existing else None,
            )
            self.store.upsert_item(item=item)
            if should_enqueue:
                tasks.append(
                    self._enqueue_item_task(
                        knowledge_item_id=item.knowledge_item_id,
                        owner_user_id=item.owner_user_id,
                        requested_by_user_id=item.owner_user_id,
                        task_type="upload_ingest",
                        summary="上传文件已进入知识库入库流程。",
                    )
                )
        return tasks

    def get_visible_item_detail(self, *, owner_user_id: str, knowledge_item_id: str) -> KnowledgeItemDetailResponse | None:
        item = self.store.get_visible_item(owner_user_id=owner_user_id, knowledge_item_id=knowledge_item_id)
        if item is None:
            return None
        return self.store.get_item_detail(knowledge_item_id=knowledge_item_id)

    def update_shared_item_flags(
        self,
        *,
        knowledge_item_id: str,
        is_enabled: bool,
        session_attachable: bool,
        updated_by_user_id: str,
    ) -> KnowledgeItem:
        item = self.store.get_item(knowledge_item_id=knowledge_item_id)
        if item is None:
            raise KeyError(knowledge_item_id)
        if item.library_scope != "shared":
            raise KnowledgeValidationError("仅管理员共享知识条目允许后台修改。")
        updated = item.model_copy(
            update={
                "is_enabled": is_enabled,
                "session_attachable": session_attachable,
                "updated_at": self.store.utcnow(),
            }
        )
        self.store.upsert_item(item=updated)
        if item.source_type == "private_sample_repo":
            update_private_sample_override(
                doc_id=knowledge_item_id,
                is_enabled=is_enabled,
                session_attachable=session_attachable,
                updated_by_user_id=updated_by_user_id,
                database_url=self.store.database_url,
                sqlite_db_path=self.store.sqlite_db_path,
            )
        refreshed = self.store.get_item(knowledge_item_id=knowledge_item_id)
        if refreshed is None:
            raise RuntimeError("知识条目更新后无法重新读取。")
        return refreshed

    def list_user_tasks(self, *, owner_user_id: str, filters: KnowledgeTaskListFilters | None = None) -> list[KnowledgeTask]:
        return self.store.list_tasks_for_user(owner_user_id=owner_user_id, filters=filters)

    def list_admin_tasks(self, *, filters: KnowledgeTaskListFilters | None = None) -> list[KnowledgeTask]:
        return self.store.list_admin_tasks(filters=filters)

    def list_tasks(
        self,
        *,
        owner_user_id: str | None = None,
        include_shared: bool = True,
        status: str | None = None,
        task_type: str | None = None,
        knowledge_item_id: str | None = None,
        requested_by_user_id: str | None = None,
    ) -> list[KnowledgeTask]:
        return self.store.list_tasks(
            owner_user_id=owner_user_id,
            include_shared=include_shared,
            status=status,
            task_type=task_type,
            knowledge_item_id=knowledge_item_id,
            requested_by_user_id=requested_by_user_id,
        )

    def get_task(self, task_id: str) -> KnowledgeTask | None:
        return self.store.get_task(task_id)

    def retry_task(
        self,
        *,
        task_id: str,
        current_user_id: str | None = None,
        is_admin: bool | None = None,
        requested_by_user_id: str | None = None,
    ) -> KnowledgeTask | None:
        task = self.store.get_task(task_id=task_id)
        if task is None:
            raise KeyError(task_id)
        actor_user_id = current_user_id or requested_by_user_id
        admin_mode = bool(is_admin) if is_admin is not None else actor_user_id is None
        if not admin_mode and task.owner_user_id != actor_user_id:
            raise KnowledgeAccessError("当前任务不属于当前用户。")
        task = self.store.requeue_task(task_id=task_id)
        if task is not None:
            from app.knowledge.runner import get_knowledge_task_runner

            get_knowledge_task_runner().enqueue(task.task_id)
        return task

    def trigger_scan(self, *, requested_by_user_id: str | None) -> list[KnowledgeTask]:
        discovered = self.bootstrap_shared_library()
        scan_task = self.store.create_task(
            task_id=f"ktask-{uuid4().hex[:12]}",
            knowledge_item_id=None,
            owner_user_id=None,
            requested_by_user_id=requested_by_user_id,
            task_type="rescan",
            summary="共享知识目录扫描已开始。",
        )
        self.store.finish_task(
            task_id=scan_task.task_id,
            status="succeeded",
            summary=f"共享知识目录扫描完成，发现 {len(discovered)} 个待更新条目。",
            error_detail=None,
        )
        refreshed_scan_task = self.store.get_task(task_id=scan_task.task_id) or scan_task
        return [refreshed_scan_task, *discovered]

    def rebuild_items(self, *, knowledge_item_ids: list[str], requested_by_user_id: str | None) -> list[KnowledgeTask]:
        targets = knowledge_item_ids or [item.knowledge_item_id for item in self.store.list_admin_items(filters=KnowledgeItemListFilters(library_scope="shared", index_status="stale"))]
        results: list[KnowledgeTask] = []
        for knowledge_item_id in targets:
            item = self.store.get_item(knowledge_item_id=knowledge_item_id)
            if item is None:
                continue
            results.append(
                self._enqueue_item_task(
                    knowledge_item_id=knowledge_item_id,
                    owner_user_id=item.owner_user_id,
                    requested_by_user_id=requested_by_user_id,
                    task_type="rebuild",
                    summary="管理员触发知识条目重建。",
                )
            )
        return results

    def list_my_uploads(self, *, owner_user_id: str) -> list[MyUploadEntry]:
        return self.store.list_my_uploads(owner_user_id=owner_user_id)

    def run_queued_tasks(self) -> list[KnowledgeTask]:
        tasks: list[KnowledgeTask] = []
        while True:
            task = self.store.claim_next_task()
            if task is None:
                break
            self.process_task(task_id=task.task_id)
            refreshed = self.store.get_task(task_id=task.task_id)
            if refreshed is not None:
                tasks.append(refreshed)
        return tasks

    def process_task(self, *, task_id: str) -> None:
        task = self.store.get_task(task_id=task_id)
        if task is None or task.status != "running":
            return
        if task.knowledge_item_id is None:
            self.store.finish_task(task_id=task_id, status="succeeded", summary="共享样例扫描完成。", error_detail=None)
            return
        item = self.store.get_item(knowledge_item_id=task.knowledge_item_id)
        if item is None:
            self.store.finish_task(task_id=task_id, status="failed", summary="知识条目不存在。", error_detail="knowledge item missing")
            return

        self.store.mark_item_stage(
            knowledge_item_id=item.knowledge_item_id,
            parse_status="running",
            ingest_status="running",
            index_status="running",
            last_error=None,
        )
        try:
            parsed = parse_document(path=Path(item.storage_path), mime_type=item.mime_type)
            chunks = chunk_knowledge_text(item=item, text=parsed.text, created_at=self.store.utcnow())
            self.store.replace_chunks(knowledge_item_id=item.knowledge_item_id, chunks=chunks, indexed_at=self.store.utcnow())
            self.store.finish_task(
                task_id=task_id,
                status="succeeded",
                summary=f"知识条目已完成解析、入库和索引，共生成 {len(chunks)} 个片段。",
                error_detail=None,
            )
            self._clear_private_retrieval_caches()
        except KnowledgeParseError as exc:
            self.store.mark_item_stage(
                knowledge_item_id=item.knowledge_item_id,
                parse_status="parse_failed",
                ingest_status="ingest_failed",
                index_status="index_failed",
                last_error=str(exc),
            )
            self.store.finish_task(task_id=task_id, status="failed", summary="解析失败。", error_detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            self.store.mark_item_stage(
                knowledge_item_id=item.knowledge_item_id,
                parse_status="parse_failed",
                ingest_status="ingest_failed",
                index_status="index_failed",
                last_error=str(exc),
            )
            self.store.finish_task(task_id=task_id, status="failed", summary="知识任务执行失败。", error_detail=str(exc))

    def list_session_attachable_items(self, *, owner_user_id: str) -> list[KnowledgeItem]:
        return self.store.list_visible_items(
            owner_user_id=owner_user_id,
            filters=KnowledgeItemListFilters(session_attachable=True),
        )

    def list_chunks(
        self,
        *,
        knowledge_item_id: str | None = None,
        knowledge_item_ids: list[str] | None = None,
    ) -> list:
        return self.store.list_chunks(
            knowledge_item_id=knowledge_item_id,
            knowledge_item_ids=knowledge_item_ids,
        )

    def get_item_chunks_for_ids(self, *, knowledge_item_ids: list[str]) -> list:
        return self.store.list_chunks(knowledge_item_ids=knowledge_item_ids)

    def _enqueue_item_task(
        self,
        *,
        knowledge_item_id: str,
        owner_user_id: str | None,
        requested_by_user_id: str | None,
        task_type: str,
        summary: str,
    ) -> KnowledgeTask:
        task = self.store.create_task(
            task_id=f"ktask-{uuid4().hex[:12]}",
            knowledge_item_id=knowledge_item_id,
            owner_user_id=owner_user_id,
            requested_by_user_id=requested_by_user_id,
            task_type=task_type,
            summary=summary,
        )
        from app.knowledge.runner import get_knowledge_task_runner

        get_knowledge_task_runner().enqueue(task.task_id)
        return task

    @staticmethod
    def _compute_file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_mtime(path: Path) -> str:
        return str(path.stat().st_mtime)

    def _iter_repo_private_sources(self) -> Iterable[RepoPrivateSampleSource]:
        private_root = resolve_private_corpus_dir()
        manifest = load_private_sample_manifest()
        for item in manifest:
            path = private_root / item.filepath
            if not path.exists():
                continue
            yield RepoPrivateSampleSource(
                metadata=RepoPrivateSampleMetadata(
                    doc_id=item.doc_id,
                    title=item.title,
                    source_type=item.source_type,
                    sample_type=item.sample_type,
                    business_topic=item.business_topic,
                    filepath=item.filepath,
                    session_attachable=item.session_attachable,
                    source="管理员共享样例",
                    source_url=None,
                ),
                storage_path=str(path),
                mime_type=_guess_mime_type(path.suffix.lower()),
                source_hash=self._compute_file_hash(path),
                source_mtime=self._safe_mtime(path),
            )

    @staticmethod
    def _clear_private_retrieval_caches() -> None:
        from app.retrieval.mixed_retriever import get_mixed_scope_retriever
        from app.retrieval.private_retriever import get_private_sample_retriever

        get_private_sample_retriever.cache_clear()
        get_mixed_scope_retriever.cache_clear()


def _guess_mime_type(suffix: str) -> str:
    mapping = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
    }
    return mapping.get(suffix, "application/octet-stream")


@lru_cache(maxsize=1)
def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()
