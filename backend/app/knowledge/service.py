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
    from app.knowledge.policy_ingestion import CrawledDocument
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
                tenant_id=None,
                owner_user_id=None,
                visibility="demo",
                created_by=None,
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
            tenant_id=owner_user_id,
            owner_user_id=owner_user_id,
            visibility="private",
            created_by=owner_user_id,
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

    def create_policy_item_from_crawled_document(
        self,
        *,
        crawled_document: "CrawledDocument | dict",
        staging_dir: str | Path | None = None,
        requested_by_user_id: str | None = None,
    ) -> KnowledgeTask:
        from app.core.config import get_settings
        from app.knowledge.policy_ingestion import (
            CrawledDocument,
            build_policy_web_knowledge_item,
            stage_crawled_document,
        )

        document = crawled_document if isinstance(crawled_document, CrawledDocument) else CrawledDocument.model_validate(crawled_document)
        resolved_staging_dir = Path(staging_dir) if staging_dir is not None else Path(get_settings().public_data_dir) / "policy_staging"
        staged = stage_crawled_document(document, staging_dir=resolved_staging_dir)
        existing = self.store.get_item_by_source(
            owner_user_id=None,
            library_scope="shared",
            source_type="public_policy_web",
            source_ref=document.url,
        )
        now = self.store.utcnow()
        item = build_policy_web_knowledge_item(
            staged=staged,
            knowledge_item_id=existing.knowledge_item_id if existing else None,
            created_at=existing.created_at if existing else now,
        )
        if existing is not None:
            item = item.model_copy(
                update={
                    "is_enabled": existing.is_enabled,
                    "session_attachable": existing.session_attachable,
                    "index_status": "stale",
                    "updated_at": now,
                    "last_indexed_at": existing.last_indexed_at,
                }
            )
        self.store.upsert_item(item=item)
        task_summary = (
            "政策展示样例已进入知识库入库流程。"
            if item.visibility == "demo"
            else "官方政策采集结果已进入知识库入库流程。"
        )
        return self._enqueue_item_task(
            knowledge_item_id=item.knowledge_item_id,
            owner_user_id=None,
            requested_by_user_id=requested_by_user_id,
            task_type="crawl_ingest",
            summary=task_summary,
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
                tenant_id=str(file_row["owner_user_id"]) if file_row.get("owner_user_id") is not None else None,
                owner_user_id=str(file_row["owner_user_id"]) if file_row.get("owner_user_id") is not None else None,
                visibility="private",
                created_by=str(file_row["owner_user_id"]) if file_row.get("owner_user_id") is not None else None,
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
        if task.task_type in {"crawl_ingest", "crawl_refresh"} and item.source_type != "public_policy_web":
            self.store.finish_task(
                task_id=task_id,
                status="failed",
                summary="政策采集任务目标类型不正确。",
                error_detail=f"crawl task cannot process source_type={item.source_type}",
            )
            return
        if item.source_type == "public_policy_web":
            self._process_policy_task(task=task, item=item)
            return

        self.store.mark_item_stage(
            knowledge_item_id=item.knowledge_item_id,
            parse_status="running",
            ingest_status="running",
            index_status="running",
            last_error=None,
        )
        from app.rag.workflow import WorkflowRecorder, build_rag_ingest_workflow

        workflow = build_rag_ingest_workflow(
            knowledge_item_id=item.knowledge_item_id,
            owner_user_id=item.owner_user_id,
            tenant_id=item.tenant_id,
            visibility=item.visibility,
            created_by=task.requested_by_user_id or item.created_by,
            metadata={"task_id": task.task_id, "task_type": task.task_type},
        )
        recorder = WorkflowRecorder(workflow)
        recorder.start_run()
        recorder.start_node(
            "upload_received",
            input_ref=item.source_ref,
            state={"knowledge_item_id": item.knowledge_item_id, "storage_path": item.storage_path},
        )
        recorder.complete_node(
            "upload_received",
            output_ref=item.storage_path,
            state={"mime_type": item.mime_type, "source_type": item.source_type},
        )
        self.store.save_workflow_run(workflow)
        current_node = "parse_document"
        try:
            recorder.start_node("parse_document", input_ref=item.storage_path, state={"mime_type": item.mime_type})
            parsed = parse_document(path=Path(item.storage_path), mime_type=item.mime_type)
            recorder.complete_node(
                "parse_document",
                output_ref=item.storage_path,
                state={"text_length": len(parsed.text), "parser_name": "knowledge.parsers.parse_document"},
            )
            current_node = "build_blocks"
            recorder.start_node("build_blocks", input_ref=item.storage_path)
            recorder.complete_node(
                "build_blocks",
                output_ref=item.storage_path,
                state={"block_count": 1 if parsed.text else 0, "block_builder": "lightweight_text_block"},
            )
            current_node = "build_chunks"
            recorder.start_node("build_chunks", input_ref=item.storage_path)
            chunks = chunk_knowledge_text(item=item, text=parsed.text, created_at=self.store.utcnow())
            recorder.complete_node(
                "build_chunks",
                output_ref=item.knowledge_item_id,
                state={"chunk_count": len(chunks)},
            )
            current_node = "build_embeddings"
            recorder.start_node("build_embeddings", input_ref=item.knowledge_item_id)
            recorder.skip_node(
                "build_embeddings",
                reason="embedding_generation_not_enabled_in_current_ingest_flow",
                state={"chunk_count": len(chunks)},
            )
            current_node = "upsert_vector_index"
            recorder.start_node("upsert_vector_index", input_ref=item.knowledge_item_id)
            self.store.replace_chunks(knowledge_item_id=item.knowledge_item_id, chunks=chunks, indexed_at=self.store.utcnow())
            recorder.complete_node(
                "upsert_vector_index",
                output_ref=item.knowledge_item_id,
                state={"chunk_count": len(chunks), "vector_backend": "current_runtime_chunks"},
            )
            current_node = "build_graph_candidates"
            recorder.start_node("build_graph_candidates", input_ref=item.knowledge_item_id)
            recorder.skip_node(
                "build_graph_candidates",
                reason="graph_candidates_not_built_during_default_ingest",
                state={"optional": True},
            )
            current_node = "index_completed"
            recorder.start_node("index_completed", input_ref=item.knowledge_item_id)
            recorder.complete_node(
                "index_completed",
                output_ref=item.knowledge_item_id,
                state={"parse_status": "parsed", "ingest_status": "ingested", "index_status": "indexed"},
            )
            recorder.complete_run(state={"chunk_count": len(chunks), "completed_task_id": task_id})
            self.store.save_workflow_run(workflow)
            self.store.finish_task(
                task_id=task_id,
                status="succeeded",
                summary=f"知识条目已完成解析、入库和索引，共生成 {len(chunks)} 个片段。",
                error_detail=None,
            )
            self._clear_private_retrieval_caches()
        except KnowledgeParseError as exc:
            recorder.fail_node(current_node, error_message=str(exc), state={"error_type": type(exc).__name__})
            self.store.save_workflow_run(workflow)
            self.store.mark_item_stage(
                knowledge_item_id=item.knowledge_item_id,
                parse_status="parse_failed",
                ingest_status="ingest_failed",
                index_status="index_failed",
                last_error=str(exc),
            )
            self.store.finish_task(task_id=task_id, status="failed", summary="解析失败。", error_detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            recorder.fail_node(current_node, error_message=str(exc), state={"error_type": type(exc).__name__})
            self.store.save_workflow_run(workflow)
            self.store.mark_item_stage(
                knowledge_item_id=item.knowledge_item_id,
                parse_status="parse_failed",
                ingest_status="ingest_failed",
                index_status="index_failed",
                last_error=str(exc),
            )
            self.store.finish_task(task_id=task_id, status="failed", summary="知识任务执行失败。", error_detail=str(exc))

    def _process_policy_task(self, *, task: KnowledgeTask, item: KnowledgeItem) -> None:
        self.store.mark_item_stage(
            knowledge_item_id=item.knowledge_item_id,
            parse_status="running",
            ingest_status="running",
            index_status="running",
            last_error=None,
        )
        from app.knowledge.policy_ingestion import (
            PolicyDocumentParser,
            build_policy_chunks,
            normalize_policy_governance_metadata,
        )
        from app.rag.workflow import WorkflowRecorder, build_policy_ingest_workflow

        workflow = build_policy_ingest_workflow(
            knowledge_item_id=item.knowledge_item_id,
            owner_user_id=item.owner_user_id,
            tenant_id=item.tenant_id,
            visibility=item.visibility,
            created_by=task.requested_by_user_id or item.created_by,
            metadata={
                "task_id": task.task_id,
                "task_type": task.task_type,
                "source_url": item.source_url,
            },
        )
        recorder = WorkflowRecorder(workflow)
        recorder.start_run()
        current_node = "crawl_source"
        try:
            recorder.start_node(
                "crawl_source",
                input_ref=item.source_ref,
                state={"source_url": item.source_url, "source_hash": item.source_hash},
            )
            recorder.complete_node(
                "crawl_source",
                output_ref=item.source_url or item.source_ref,
                state={"source_type": item.source_type, "source": item.source},
            )
            current_node = "stage_crawled_document"
            recorder.start_node(
                "stage_crawled_document",
                input_ref=item.source_ref,
                state={"storage_path": item.storage_path},
            )
            storage_path = Path(item.storage_path)
            if not storage_path.exists():
                raise KnowledgeParseError(f"staged policy document not found: {storage_path}")
            recorder.complete_node(
                "stage_crawled_document",
                output_ref=item.storage_path,
                state={"mime_type": item.mime_type, "source_mtime": item.source_mtime},
            )
            current_node = "parse_document"
            recorder.start_node("parse_document", input_ref=item.storage_path, state={"mime_type": item.mime_type})
            parsed = PolicyDocumentParser().parse_staged_document(
                path=storage_path,
                content_type=item.mime_type,
                source_url=item.source_url,
                title=item.title,
            )
            if not parsed.text.strip():
                parse_error = parsed.metadata.get("parse_error") or "Policy document parsed to empty text."
                raise KnowledgeParseError(str(parse_error))
            recorder.complete_node(
                "parse_document",
                output_ref=item.storage_path,
                state={
                    "text_length": len(parsed.text),
                    "parser_name": parsed.parser_name,
                    "quality_score": parsed.quality_score,
                },
            )
            current_node = "normalize_policy_metadata"
            recorder.start_node("normalize_policy_metadata", input_ref=item.storage_path)
            policy_metadata = normalize_policy_governance_metadata(parsed=parsed, source_url=item.source_url)
            policy_metadata = policy_metadata.model_copy(
                update={
                    "content_hash": item.source_hash or policy_metadata.content_hash,
                    "metadata": {
                        **policy_metadata.metadata,
                        "knowledge_item_id": item.knowledge_item_id,
                        "storage_path": item.storage_path,
                        "source_hash": item.source_hash,
                        "source_mtime": item.source_mtime,
                    },
                }
            )
            recorder.complete_node(
                "normalize_policy_metadata",
                output_ref=item.knowledge_item_id,
                state={
                    "issuing_authority": policy_metadata.issuing_authority,
                    "region": policy_metadata.region,
                    "topic_tags": policy_metadata.topic_tags,
                    "clause_anchor_count": len(policy_metadata.clause_anchors),
                },
            )
            current_node = "build_chunks"
            recorder.start_node("build_chunks", input_ref=item.storage_path)
            chunks = build_policy_chunks(
                item=item,
                parsed=parsed,
                policy_metadata=policy_metadata,
                created_at=self.store.utcnow(),
            )
            recorder.complete_node(
                "build_chunks",
                output_ref=item.knowledge_item_id,
                state={"chunk_count": len(chunks), "chunk_source_type": "public_policy"},
            )
            current_node = "upsert_vector_index"
            recorder.start_node("upsert_vector_index", input_ref=item.knowledge_item_id)
            self.store.replace_chunks(knowledge_item_id=item.knowledge_item_id, chunks=chunks, indexed_at=self.store.utcnow())
            recorder.complete_node(
                "upsert_vector_index",
                output_ref=item.knowledge_item_id,
                state={"chunk_count": len(chunks), "vector_backend": "current_runtime_chunks"},
            )
            current_node = "index_completed"
            recorder.start_node("index_completed", input_ref=item.knowledge_item_id)
            recorder.complete_node(
                "index_completed",
                output_ref=item.knowledge_item_id,
                state={"parse_status": "parsed", "ingest_status": "ingested", "index_status": "indexed"},
            )
            recorder.complete_run(state={"chunk_count": len(chunks), "completed_task_id": task.task_id})
            self.store.save_workflow_run(workflow)
            self.store.finish_task(
                task_id=task.task_id,
                status="succeeded",
                summary=f"官方政策知识条目已完成解析、治理和索引，共生成 {len(chunks)} 个片段。",
                error_detail=None,
            )
            self._clear_private_retrieval_caches()
        except KnowledgeParseError as exc:
            recorder.fail_node(current_node, error_message=str(exc), state={"error_type": type(exc).__name__})
            self.store.save_workflow_run(workflow)
            self.store.mark_item_stage(
                knowledge_item_id=item.knowledge_item_id,
                parse_status="parse_failed",
                ingest_status="ingest_failed",
                index_status="index_failed",
                last_error=str(exc),
            )
            self.store.finish_task(task_id=task.task_id, status="failed", summary="政策文档解析失败。", error_detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            recorder.fail_node(current_node, error_message=str(exc), state={"error_type": type(exc).__name__})
            self.store.save_workflow_run(workflow)
            self.store.mark_item_stage(
                knowledge_item_id=item.knowledge_item_id,
                parse_status="parse_failed",
                ingest_status="ingest_failed",
                index_status="index_failed",
                last_error=str(exc),
            )
            self.store.finish_task(task_id=task.task_id, status="failed", summary="政策知识任务执行失败。", error_detail=str(exc))

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
        from app.rag.service import get_rag_engine_service
        from app.retrieval.mixed_retriever import get_mixed_scope_retriever
        from app.retrieval.private_retriever import get_private_sample_retriever
        from app.retrieval.public_retriever import get_public_policy_retriever

        get_private_sample_retriever.cache_clear()
        get_public_policy_retriever.cache_clear()
        get_mixed_scope_retriever.cache_clear()
        get_rag_engine_service.cache_clear()


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
