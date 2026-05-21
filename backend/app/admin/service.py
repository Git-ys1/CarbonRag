import json
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.admin.schemas import (
    AdminFeedbackOverview,
    AdminFeedbackRecentEntry,
    AdminPrivateSampleItem,
    AdminSystemStatus,
    AdminUserSummary,
    CreateAdminUserRequest,
    KnowledgeRefreshTask,
    KnowledgeRefreshStatus,
    KnowledgeRefreshScope,
    PolicyCrawlerAutoRagKbStatus,
    PolicyCrawlerActiveMaintenanceRequest,
    PolicyCrawlerActiveMaintenanceResponse,
    PolicyCrawlerBatchPublishItem,
    PolicyCrawlerBatchPublishResponse,
    PolicyCrawlerCandidateStatus,
    PolicyCrawlerCandidateArtifactsSummary,
    PolicyCrawlerCandidatePage,
    PolicyCrawlerCandidateSummary,
    PolicyCrawlerMaintenanceRunPage,
    PolicyCrawlerMaintenanceRunSummary,
    PolicyCrawlerMaintenanceStatus,
    PolicyCrawlerDryRunSummary,
    PolicyCrawlerRecommendedImportSummary,
    PolicyCrawlerRunPage,
    PolicyCrawlerRunRequest,
    PolicyCrawlerRunSummary,
    PolicyCrawlerSourceSummary,
    PolicyCrawlerSourceUpsertRequest,
    PolicyCrawlerStatusSummary,
    PolicyShowcaseChunkSummary,
    PolicyShowcaseRetrievalHit,
    PolicyShowcaseRetrievalPreview,
    PolicyShowcaseSourceSummary,
    PolicyShowcaseStatus,
    PolicyShowcaseWorkflowNodeSummary,
    PolicyShowcaseWorkflowSummary,
)
from app.ai_runtime.providers.factory import get_chat_provider
from app.auth.schemas import RegisterRequest, UserRole
from app.auth.service import AuthService, get_auth_service
from app.core.config import get_settings
from app.knowledge import get_knowledge_service
from app.knowledge.policy_showcase import (
    ShowcasePolicySource,
    get_showcase_policy_source,
    list_showcase_policy_sources,
)
from app.knowledge.policy_live_crawler import get_policy_crawler_scheduler
from app.private_samples.catalog import (
    list_admin_private_sample_catalog,
    refresh_private_sample_catalog,
)
from app.rag.kb.crawler_bridge import publish_crawled_candidate_to_rag_kb
from app.knowledge.schemas import KnowledgeItemSummary, KnowledgeTaskSummary
from app.retrieval.mixed_retriever import get_mixed_scope_retriever
from app.retrieval.private_retriever import get_private_sample_retriever
from app.retrieval.private_corpus_loader import load_private_sample_documents
from app.retrieval.public_corpus_loader import load_public_policy_documents
from app.retrieval.public_retriever import get_public_policy_retriever
from app.runtime_db.compat import connect_postgres
from app.runtime_db.bootstrap import bootstrap_runtime_database, get_runtime_backend_kind
from app.session.store import DEFAULT_SESSION_DB_PATH


class AdminService:
    def __init__(
        self,
        *,
        auth_service: AuthService | None = None,
        database_url: str | None = None,
        sqlite_db_path: Path | str | None = None,
    ) -> None:
        self.auth_service = auth_service or get_auth_service()
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self.sqlite_db_path = Path(sqlite_db_path or DEFAULT_SESSION_DB_PATH)
        self.backend_kind = get_runtime_backend_kind(self.database_url)
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_runtime_database(
            database_url=self.database_url,
            sqlite_db_path=self.sqlite_db_path,
        )

    def _connect(self):
        if self.backend_kind == "postgresql":
            return connect_postgres(self.database_url)

        connection = sqlite3.connect(self.sqlite_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _format_query(self, query: str) -> str:
        return query.replace("{p}", "%s" if self.backend_kind == "postgresql" else "?")

    def _select_rows(self, query: str, params: list[object] | None = None) -> list[dict[str, Any]]:
        sql = self._format_query(query)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(sql, params or [])
                    return [dict(row) for row in cursor.fetchall()]
            rows = connection.execute(sql, params or []).fetchall()
            return [dict(row) for row in rows]

    def _execute_statement(self, query: str, params: list[object] | None = None) -> None:
        sql = self._format_query(query)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(sql, params or [])
                connection.commit()
                return
            connection.execute(sql, params or [])
            connection.commit()

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    def list_users(self) -> list[AdminUserSummary]:
        users = {user.user_id: user for user in self.auth_service.list_users()}
        session_counts = self._count_grouped_rows("sessions", "owner_user_id")
        report_counts = self._count_grouped_rows("reports", "owner_user_id")
        feedback_counts = self._count_grouped_rows("feedback_entries", "owner_user_id")

        items: list[AdminUserSummary] = []
        for user in users.values():
            items.append(
                AdminUserSummary(
                    user_id=user.user_id,
                    username=user.username,
                    display_name=user.display_name,
                    role=user.role,
                    is_active=user.is_active,
                    password_must_change=user.password_must_change,
                    created_at=user.created_at,
                    last_login_at=user.last_login_at,
                    session_count=session_counts.get(user.user_id, 0),
                    report_count=report_counts.get(user.user_id, 0),
                    feedback_count=feedback_counts.get(user.user_id, 0),
                )
            )
        return items

    def create_user(self, *, payload: CreateAdminUserRequest, actor_role: str) -> AdminUserSummary:
        if payload.role in {"admin", "super_admin"} and actor_role != "super_admin":
            raise PermissionError("Only super_admin can create admin accounts.")
        user = self.auth_service.register(
            RegisterRequest(
                username=payload.username,
                display_name=payload.display_name,
                password=payload.password,
            )
        )
        if payload.role == "admin":
            user = self.auth_service.update_user(user_id=user.user_id, role="admin", is_active=True)
        if payload.role == "super_admin":
            user = self.auth_service.promote_temporary_super_admin(user.user_id)
        return AdminUserSummary(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
            password_must_change=user.password_must_change,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            session_count=0,
            report_count=0,
            feedback_count=0,
        )

    def update_user(self, *, user_id: str, role: UserRole, is_active: bool, actor_role: str = "admin"):
        current = next((user for user in self.auth_service.list_users() if user.user_id == user_id), None)
        if current is None:
            raise KeyError(user_id)
        if actor_role != "super_admin" and (role == "admin" or current.role == "admin"):
            raise PermissionError("Only super_admin can create or modify admin accounts.")
        return self.auth_service.update_user(user_id=user_id, role=role, is_active=is_active)

    def reset_password(self, *, user_id: str) -> str:
        return self.auth_service.reset_password(user_id=user_id)

    def delete_users(
        self,
        *,
        actor_user_id: str,
        actor_role: str,
        current_password: str,
        user_ids: list[str],
    ) -> list[str]:
        return self.auth_service.delete_non_admin_users(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            current_password=current_password,
            target_user_ids=user_ids,
        )

    def get_feedback_overview(self) -> AdminFeedbackOverview:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) AS total_count,
                            COUNT(*) FILTER (WHERE target_type = 'ask' AND rating = 'up') AS ask_up_count,
                            COUNT(*) FILTER (WHERE target_type = 'ask' AND rating = 'down') AS ask_down_count,
                            COUNT(*) FILTER (WHERE target_type = 'calc_carbon' AND rating = 'up') AS calc_up_count,
                            COUNT(*) FILTER (WHERE target_type = 'calc_carbon' AND rating = 'down') AS calc_down_count
                        FROM feedback_entries
                        """
                    )
                    aggregate = cursor.fetchone()
                    cursor.execute(
                        """
                        SELECT feedback_id, target_type, rating, session_id, owner_user_id, created_at
                        FROM feedback_entries
                        ORDER BY created_at DESC
                        LIMIT 20
                        """
                    )
                    recent_rows = cursor.fetchall()
            else:
                aggregate = connection.execute(
                    """
                    SELECT
                        COUNT(*) AS total_count,
                        SUM(CASE WHEN target_type = 'ask' AND rating = 'up' THEN 1 ELSE 0 END) AS ask_up_count,
                        SUM(CASE WHEN target_type = 'ask' AND rating = 'down' THEN 1 ELSE 0 END) AS ask_down_count,
                        SUM(CASE WHEN target_type = 'calc_carbon' AND rating = 'up' THEN 1 ELSE 0 END) AS calc_up_count,
                        SUM(CASE WHEN target_type = 'calc_carbon' AND rating = 'down' THEN 1 ELSE 0 END) AS calc_down_count
                    FROM feedback_entries
                    """
                ).fetchone()
                recent_rows = connection.execute(
                    """
                    SELECT feedback_id, target_type, rating, session_id, owner_user_id, created_at
                    FROM feedback_entries
                    ORDER BY created_at DESC
                    LIMIT 20
                    """
                ).fetchall()

        aggregate = dict(aggregate or {})
        return AdminFeedbackOverview(
            total_count=int(aggregate.get("total_count") or 0),
            ask_up_count=int(aggregate.get("ask_up_count") or 0),
            ask_down_count=int(aggregate.get("ask_down_count") or 0),
            calc_up_count=int(aggregate.get("calc_up_count") or 0),
            calc_down_count=int(aggregate.get("calc_down_count") or 0),
            recent_entries=[AdminFeedbackRecentEntry.model_validate(dict(row)) for row in recent_rows],
        )

    def list_private_samples(self) -> list[AdminPrivateSampleItem]:
        knowledge_service = get_knowledge_service()
        refresh_private_sample_catalog()
        try:
            knowledge_service.run_queued_tasks()
        except Exception:
            pass
        return [
            AdminPrivateSampleItem.model_validate(item)
            for item in list_admin_private_sample_catalog(
                database_url=self.database_url,
                sqlite_db_path=self.sqlite_db_path,
            )
        ]

    def list_policy_showcase_sources(self) -> list[PolicyShowcaseSourceSummary]:
        return [self._policy_showcase_source_summary(source) for source in list_showcase_policy_sources()]

    def run_policy_showcase_source(
        self,
        *,
        source_id: str,
        requested_by_user_id: str | None,
    ) -> PolicyShowcaseStatus:
        source = get_showcase_policy_source(source_id)
        knowledge_service = get_knowledge_service()
        knowledge_service.create_policy_item_from_crawled_document(
            crawled_document=source.to_crawled_document(),
            requested_by_user_id=requested_by_user_id,
        )
        # The admin request thread only processes the small built-in showcase fixture.
        # Live crawling or large policy refreshes must use the queued task runner path.
        knowledge_service.run_queued_tasks()
        self._clear_retrieval_caches("public_policy")
        return self.get_policy_showcase_status(source_id=source_id)

    def get_policy_showcase_status(self, *, source_id: str) -> PolicyShowcaseStatus:
        source = get_showcase_policy_source(source_id)
        item = self._get_policy_showcase_item(source)
        chunks: list[PolicyShowcaseChunkSummary] = []
        latest_task = None
        workflow = None
        retrieval_preview = None

        if item is not None:
            knowledge_service = get_knowledge_service()
            chunks = [
                PolicyShowcaseChunkSummary.model_validate(chunk.model_dump(mode="python"))
                for chunk in knowledge_service.list_chunks(knowledge_item_id=item.knowledge_item_id)
            ]
            tasks = knowledge_service.list_tasks(
                knowledge_item_id=item.knowledge_item_id,
                include_shared=True,
            )
            if tasks:
                latest_task = KnowledgeTaskSummary.model_validate(tasks[0].model_dump())
            latest_workflow = knowledge_service.store.get_latest_workflow_run(
                knowledge_item_id=item.knowledge_item_id,
            )
            if latest_workflow is not None:
                workflow = PolicyShowcaseWorkflowSummary(
                    workflow_id=latest_workflow.workflow_id,
                    workflow_type=latest_workflow.workflow_type,
                    status=latest_workflow.status,
                    current_node=latest_workflow.current_node,
                    error_message=latest_workflow.error_message,
                    created_at=latest_workflow.created_at,
                    updated_at=latest_workflow.updated_at,
                    nodes=[
                        PolicyShowcaseWorkflowNodeSummary(
                            node_id=node.node_id,
                            node_type=node.node_type,
                            status=node.status,
                            input_ref=node.input_ref,
                            output_ref=node.output_ref,
                            started_at=node.started_at,
                            finished_at=node.finished_at,
                            error_message=node.error_message,
                            retry_count=node.retry_count,
                            metadata=node.metadata,
                        )
                        for node in latest_workflow.nodes
                    ],
                )
            retrieval_preview = self.get_policy_showcase_retrieval_preview(
                source_id=source_id,
                query=source.default_query,
                top_k=5,
            )

        return PolicyShowcaseStatus(
            source=self._policy_showcase_source_summary(source),
            item=KnowledgeItemSummary.model_validate(item.model_dump()) if item is not None else None,
            latest_task=latest_task,
            workflow=workflow,
            chunks=chunks,
            retrieval_preview=retrieval_preview,
            indexed=item is not None and item.index_status == "indexed" and bool(chunks),
        )

    def list_policy_showcase_chunks(self, *, source_id: str) -> list[PolicyShowcaseChunkSummary]:
        source = get_showcase_policy_source(source_id)
        item = self._get_policy_showcase_item(source)
        if item is None:
            return []
        knowledge_service = get_knowledge_service()
        return [
            PolicyShowcaseChunkSummary.model_validate(chunk.model_dump(mode="python"))
            for chunk in knowledge_service.list_chunks(knowledge_item_id=item.knowledge_item_id)
        ]

    def get_policy_showcase_retrieval_preview(
        self,
        *,
        source_id: str,
        query: str | None = None,
        top_k: int = 5,
    ) -> PolicyShowcaseRetrievalPreview:
        source = get_showcase_policy_source(source_id)
        item = self._get_policy_showcase_item(source)
        resolved_query = (query or source.default_query).strip() or source.default_query
        resolved_top_k = max(1, min(int(top_k), 10))
        self._clear_retrieval_caches("public_policy")
        result = get_public_policy_retriever().search(question=resolved_query, top_k=resolved_top_k)
        hits = [
            PolicyShowcaseRetrievalHit(
                chunk_id=hit.chunk_id,
                knowledge_item_id=hit.knowledge_item_id,
                title=hit.title,
                source_type=hit.source_type,
                source=hit.source,
                source_url=hit.source_url,
                issued_at=hit.issued_at,
                region=hit.region,
                doc_type=hit.doc_type,
                snippet=hit.snippet,
                score=hit.score,
                matched_source=item is not None
                and (hit.knowledge_item_id == item.knowledge_item_id or hit.source_url == source.source_url),
            )
            for hit in result.hits
        ]
        return PolicyShowcaseRetrievalPreview(
            source_id=source.source_id,
            query=resolved_query,
            top_k=resolved_top_k,
            total_hits=result.total_hits,
            hits=hits,
        )

    def get_policy_crawler_status(self) -> PolicyCrawlerStatusSummary:
        scheduler = get_policy_crawler_scheduler()
        return PolicyCrawlerStatusSummary.model_validate(scheduler.status().model_dump(mode="python"))

    def list_policy_crawler_sources(self) -> list[PolicyCrawlerSourceSummary]:
        scheduler = get_policy_crawler_scheduler()
        return [
            PolicyCrawlerSourceSummary.model_validate(source.model_dump(mode="python"))
            for source in scheduler.list_sources()
        ]

    def create_policy_crawler_source(self, payload: PolicyCrawlerSourceUpsertRequest) -> PolicyCrawlerSourceSummary:
        scheduler = get_policy_crawler_scheduler()
        source = scheduler.upsert_source(self._policy_crawler_source_payload(payload, force_disabled=True))
        return PolicyCrawlerSourceSummary.model_validate(source.model_dump(mode="python"))

    def update_policy_crawler_source(
        self,
        *,
        source_id: str,
        payload: PolicyCrawlerSourceUpsertRequest,
    ) -> PolicyCrawlerSourceSummary:
        scheduler = get_policy_crawler_scheduler()
        existing = scheduler.store.get_source(source_id)
        if existing is None:
            raise KeyError(source_id)
        source = scheduler.upsert_source(self._policy_crawler_source_payload(payload, source_id=source_id))
        return PolicyCrawlerSourceSummary.model_validate(source.model_dump(mode="python"))

    def delete_policy_crawler_source(self, *, source_id: str) -> dict[str, str]:
        scheduler = get_policy_crawler_scheduler()
        if not scheduler.delete_source(source_id):
            raise KeyError(source_id)
        return {"status": "deleted", "source_id": source_id}

    def import_recommended_policy_crawler_sources(self) -> PolicyCrawlerRecommendedImportSummary:
        scheduler = get_policy_crawler_scheduler()
        sources = scheduler.import_recommended_sources()
        summaries = [PolicyCrawlerSourceSummary.model_validate(source.model_dump(mode="python")) for source in sources]
        return PolicyCrawlerRecommendedImportSummary(
            imported_count=len(summaries),
            enabled_count=sum(1 for source in summaries if source.is_enabled),
            sources=summaries,
        )

    def dry_run_policy_crawler_source(self, *, source_id: str) -> PolicyCrawlerDryRunSummary:
        scheduler = get_policy_crawler_scheduler()
        result = scheduler.dry_run_source(source_id=source_id)
        return PolicyCrawlerDryRunSummary.model_validate(result.model_dump(mode="python"))

    def run_policy_crawler_source(
        self,
        *,
        source_id: str,
        requested_by_user_id: str | None,
        payload: PolicyCrawlerRunRequest | None = None,
    ) -> PolicyCrawlerRunSummary:
        scheduler = get_policy_crawler_scheduler()
        run = scheduler.run_source_now(
            source_id=source_id,
            triggered_by_user_id=requested_by_user_id,
        )
        if payload and payload.auto_rag_ingest_enabled:
            run = self._auto_ingest_policy_crawler_run(
                run_id=run.run_id,
                reviewed_by_user_id=requested_by_user_id,
                payload=payload,
            )
        return PolicyCrawlerRunSummary.model_validate(run.model_dump(mode="python"))

    def list_policy_crawler_runs(
        self,
        *,
        source_id: str | None = None,
        limit: int = 20,
    ) -> list[PolicyCrawlerRunSummary]:
        scheduler = get_policy_crawler_scheduler()
        return [
            PolicyCrawlerRunSummary.model_validate(run.model_dump(mode="python"))
            for run in scheduler.list_runs(source_id=source_id, limit=limit)
        ]

    def list_policy_crawler_runs_page(
        self,
        *,
        source_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "started_at",
        sort_order: str = "desc",
    ) -> PolicyCrawlerRunPage:
        scheduler = get_policy_crawler_scheduler()
        runs, total = scheduler.store.list_runs_page(
            source_id=source_id,
            status=status,  # type: ignore[arg-type]
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        safe_page_size = max(1, min(page_size, 100))
        return PolicyCrawlerRunPage(
            items=[PolicyCrawlerRunSummary.model_validate(run.model_dump(mode="python")) for run in runs],
            total=total,
            page=max(1, page),
            page_size=safe_page_size,
        )

    def list_policy_crawler_candidates(
        self,
        *,
        status: PolicyCrawlerCandidateStatus | None = None,
        source_id: str | None = None,
        run_id: str | None = None,
        limit: int = 50,
    ) -> list[PolicyCrawlerCandidateSummary]:
        scheduler = get_policy_crawler_scheduler()
        return [
            PolicyCrawlerCandidateSummary.model_validate(candidate.model_dump(mode="python"))
            for candidate in scheduler.list_candidates(status=status, source_id=source_id, run_id=run_id, limit=limit)
        ]

    def list_policy_crawler_candidates_page(
        self,
        *,
        status: PolicyCrawlerCandidateStatus | None = None,
        source_id: str | None = None,
        run_id: str | None = None,
        rag_pipeline_status: str | None = None,
        topic_class: str | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> PolicyCrawlerCandidatePage:
        scheduler = get_policy_crawler_scheduler()
        candidates, total = scheduler.store.list_candidates_page(
            status=status,
            source_id=source_id,
            run_id=run_id,
            rag_pipeline_status=rag_pipeline_status,
            topic_class=topic_class,
            query=query,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        safe_page_size = max(1, min(page_size, 100))
        return PolicyCrawlerCandidatePage(
            items=[PolicyCrawlerCandidateSummary.model_validate(candidate.model_dump(mode="python")) for candidate in candidates],
            total=total,
            page=max(1, page),
            page_size=safe_page_size,
        )

    def get_policy_crawler_candidate_artifacts(self, *, candidate_id: str) -> PolicyCrawlerCandidateArtifactsSummary:
        scheduler = get_policy_crawler_scheduler()
        candidate = scheduler.store.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        metadata = dict(candidate.metadata)
        raw_path = self._safe_artifact_path(metadata.get("raw_storage_path") or candidate.storage_path)
        cleaned_path = self._safe_artifact_path(metadata.get("cleaned_storage_path"))
        markdown_path = self._safe_artifact_path(metadata.get("markdown_storage_path"))
        raw_text = self._read_text_excerpt(raw_path, limit=4000)
        cleaned_text = self._read_text_excerpt(cleaned_path, limit=12000)
        markdown_text = self._read_text_excerpt(markdown_path, limit=12000)
        return PolicyCrawlerCandidateArtifactsSummary(
            candidate_id=candidate_id,
            raw_exists=bool(raw_path and raw_path.exists()),
            cleaned_exists=bool(cleaned_path and cleaned_path.exists()),
            markdown_exists=bool(markdown_path and markdown_path.exists()),
            raw_size=self._file_size(raw_path),
            cleaned_size=self._file_size(cleaned_path),
            markdown_size=self._file_size(markdown_path),
            markdown_preview=markdown_text,
            cleaned_text_preview=cleaned_text,
            raw_excerpt=raw_text,
            estimated_chunk_count=int(metadata.get("estimated_chunk_count") or 0),
            artifact_errors=metadata.get("artifact_errors") if isinstance(metadata.get("artifact_errors"), list) else [],
            extraction_quality_score=metadata.get("extraction_quality_score"),
            topic_relevance_score=metadata.get("topic_relevance_score"),
            topic_class=metadata.get("topic_class"),
            metadata=metadata,
        )

    def publish_policy_crawler_candidate(
        self,
        *,
        candidate_id: str,
        reviewed_by_user_id: str | None,
    ) -> PolicyCrawlerCandidateSummary:
        scheduler = get_policy_crawler_scheduler()
        candidate = scheduler.publish_candidate(
            candidate_id=candidate_id,
            reviewed_by_user_id=reviewed_by_user_id,
        )
        self._clear_retrieval_caches("public_policy")
        return PolicyCrawlerCandidateSummary.model_validate(candidate.model_dump(mode="python"))

    @staticmethod
    def _safe_artifact_path(value: object) -> Path | None:
        if not isinstance(value, str) or not value:
            return None
        return Path(value)

    @staticmethod
    def _file_size(path: Path | None) -> int:
        try:
            return path.stat().st_size if path and path.exists() and path.is_file() else 0
        except OSError:
            return 0

    @staticmethod
    def _read_text_excerpt(path: Path | None, *, limit: int) -> str:
        if path is None or not path.exists() or not path.is_file():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[:limit]

    @staticmethod
    def _policy_crawler_source_payload(
        payload: PolicyCrawlerSourceUpsertRequest,
        *,
        source_id: str | None = None,
        force_disabled: bool = False,
    ) -> dict:
        metadata = {
            **payload.metadata,
            "source_category": payload.source_category,
            "region": payload.region,
            "priority": payload.priority,
            "topic_tags": payload.topic_tags,
            "start_urls": payload.start_urls,
            "extra_start_urls": payload.extra_start_urls,
            "include_patterns": payload.include_patterns,
            "exclude_patterns": payload.exclude_patterns,
            "required_keywords": payload.required_keywords,
            "optional_keywords": payload.optional_keywords,
            "crawl_mode": payload.crawl_mode,
            "parser_profile": payload.parser_profile,
            "max_depth": payload.max_depth,
            "max_pages": payload.max_pages,
            "download_delay_seconds": payload.download_delay_seconds,
            "schedule_enabled": payload.schedule_enabled,
            "review_required": payload.review_required,
            "target_rag_kb_id": payload.target_rag_kb_id,
            "custom_source": True,
        }
        return {
            "source_id": source_id or payload.source_id,
            "title": payload.title,
            "source_url": payload.source_url,
            "source_label": payload.source_label,
            "allowed_domain": payload.allowed_domain,
            "is_enabled": False if force_disabled else payload.is_enabled,
            "schedule_interval_seconds": payload.schedule_interval_seconds,
            "metadata": {key: value for key, value in metadata.items() if value not in (None, [], {})},
        }

    def publish_policy_crawler_candidate_to_rag(
        self,
        *,
        candidate_id: str,
        reviewed_by_user_id: str | None,
    ) -> PolicyCrawlerCandidateSummary:
        publish_crawled_candidate_to_rag_kb(
            candidate_id=candidate_id,
            reviewed_by_user_id=reviewed_by_user_id,
        )
        scheduler = get_policy_crawler_scheduler()
        candidate = scheduler.store.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        self._clear_retrieval_caches("public_policy")
        return PolicyCrawlerCandidateSummary.model_validate(candidate.model_dump(mode="python"))

    def batch_publish_policy_crawler_candidates_to_rag(
        self,
        *,
        candidate_ids: list[str],
        reviewed_by_user_id: str | None,
        skip_duplicates: bool = True,
    ) -> PolicyCrawlerBatchPublishResponse:
        items: list[PolicyCrawlerBatchPublishItem] = []
        for candidate_id in candidate_ids:
            item = self._publish_candidate_to_rag_item(
                candidate_id=candidate_id,
                reviewed_by_user_id=reviewed_by_user_id,
                skip_duplicates=skip_duplicates,
            )
            items.append(item)
        return PolicyCrawlerBatchPublishResponse(
            total=len(items),
            published=sum(1 for item in items if item.status == "published"),
            skipped=sum(1 for item in items if item.status == "skipped"),
            failed=sum(1 for item in items if item.status == "failed"),
            items=items,
        )

    def run_policy_crawler_active_maintenance(
        self,
        *,
        reviewed_by_user_id: str | None,
        payload: PolicyCrawlerActiveMaintenanceRequest,
    ) -> PolicyCrawlerActiveMaintenanceResponse:
        """Retry crawler-to-RAG ingestion while an admin/super_admin relay is active.

        This is intentionally separate from global auto_publish: it only runs after
        an authenticated management session calls it, and it still uses the V1.7.3
        artifact/quality gates before touching the shared RAG KB.
        """

        if payload.trigger_source != "manual" and payload.cooldown_minutes > 0:
            cooldown_until = self._active_maintenance_cooldown_until()
            if cooldown_until and cooldown_until > self._utcnow():
                return PolicyCrawlerActiveMaintenanceResponse(
                    status="skipped",
                    current_stage="cooldown_active",
                    cooldown_until=cooldown_until,
                    target_kb_id=self._auto_crawler_target_kb_id(),
                    target_kb_name="自动爬虫知识库",
                    warnings=["cooldown_active"],
                )

        running = self._latest_maintenance_run(status="running")
        if running is not None:
            return PolicyCrawlerActiveMaintenanceResponse(
                status="skipped",
                maintenance_run_id=running.maintenance_run_id,
                current_stage=running.current_stage or "running",
                target_kb_id=running.target_kb_id,
                target_kb_name=running.target_kb_name or "自动爬虫知识库",
                warnings=["maintenance_already_running"],
            )

        scheduler = get_policy_crawler_scheduler()
        run_payload = self._maintenance_run_payload(payload)
        items: list[PolicyCrawlerBatchPublishItem] = []
        warnings: list[str] = []
        maintenance_run_id = f"pcrawl-maint-{uuid4().hex[:12]}"
        cooldown_until = self._utcnow() + timedelta(minutes=payload.cooldown_minutes)
        triggered_role = self._user_role(reviewed_by_user_id)
        target_kb_id = self._auto_crawler_target_kb_id()
        self._create_maintenance_run(
            maintenance_run_id=maintenance_run_id,
            trigger_type=payload.trigger_source,
            triggered_by_user_id=reviewed_by_user_id,
            triggered_by_role=triggered_role,
            target_kb_id=target_kb_id,
            target_kb_name="自动爬虫知识库",
            cooldown_until=cooldown_until,
        )

        try:
            if payload.retry_failed_ingestion:
                self._update_maintenance_stage(maintenance_run_id, "retry_pending_candidates")
                candidates, _ = scheduler.store.list_candidates_page(
                    status="pending_review",
                    page=1,
                    page_size=payload.max_candidates,
                    sort_by="updated_at",
                    sort_order="asc",
                )
                for candidate in candidates:
                    if not self._candidate_needs_rag_ingestion_retry(candidate):
                        continue
                    skip_reason = self._auto_rag_skip_reason(candidate, payload=run_payload)
                    if skip_reason:
                        items.append(
                            PolicyCrawlerBatchPublishItem(
                                candidate_id=candidate.candidate_id,
                                status="skipped",
                                reason=skip_reason,
                            )
                        )
                        continue
                    items.append(
                        self._publish_candidate_to_rag_item(
                            candidate_id=candidate.candidate_id,
                            reviewed_by_user_id=reviewed_by_user_id,
                            skip_duplicates=payload.auto_rag_ingest_skip_duplicate,
                        )
                    )

            crawled_runs: list[PolicyCrawlerRunSummary] = []
            if payload.crawl_enabled_sources and payload.max_sources > 0:
                self._update_maintenance_stage(maintenance_run_id, "crawl_enabled_sources")
                selected_sources = self._select_sources_for_active_maintenance(payload)
                for source in selected_sources[: payload.max_sources]:
                    try:
                        run = self.run_policy_crawler_source(
                            source_id=source.source_id,
                            requested_by_user_id=reviewed_by_user_id,
                            payload=run_payload,
                        )
                        crawled_runs.append(run)
                    except Exception as exc:  # noqa: BLE001
                        warnings.append(f"{source.source_id}: {exc}")

            published = sum(1 for item in items if item.status == "published")
            failed = sum(1 for item in items if item.status == "failed")
            status = "partial" if failed or warnings else "succeeded"
            if not items and not crawled_runs and not warnings:
                status = "skipped"
            summary = {
                "retried_count": len(items),
                "retry_published_count": published,
                "retry_skipped_count": sum(1 for item in items if item.status == "skipped"),
                "retry_failed_count": failed,
                "crawled_run_ids": [run.run_id for run in crawled_runs],
                "crawled_source_count": len(crawled_runs),
            }
            self._finish_maintenance_run(
                maintenance_run_id=maintenance_run_id,
                status=status,
                current_stage="finished",
                source_count=len(crawled_runs),
                candidate_count=len(items) + sum(run.candidate_count for run in crawled_runs),
                published_count=published,
                skipped_count=sum(1 for item in items if item.status == "skipped"),
                failed_count=failed,
                summary=summary,
                warnings=warnings,
            )
            return PolicyCrawlerActiveMaintenanceResponse(
                status=status,
                maintenance_run_id=maintenance_run_id,
                current_stage="finished",
                cooldown_until=cooldown_until,
                retried_count=len(items),
                retry_published_count=published,
                retry_skipped_count=sum(1 for item in items if item.status == "skipped"),
                retry_failed_count=failed,
                crawled_source_count=len(crawled_runs),
                crawled_runs=crawled_runs,
                items=items,
                target_kb_id=target_kb_id,
                target_kb_name="自动爬虫知识库",
                warnings=warnings,
            )
        except Exception as exc:
            self._finish_maintenance_run(
                maintenance_run_id=maintenance_run_id,
                status="failed",
                current_stage="failed",
                source_count=0,
                candidate_count=len(items),
                published_count=sum(1 for item in items if item.status == "published"),
                skipped_count=sum(1 for item in items if item.status == "skipped"),
                failed_count=max(1, sum(1 for item in items if item.status == "failed")),
                summary={"error": str(exc)},
                warnings=warnings,
                error_stage="maintenance_failed",
                error_detail=str(exc),
            )
            raise

    def get_policy_crawler_active_maintenance_status(self) -> PolicyCrawlerMaintenanceStatus:
        auto_kb = self.get_policy_crawler_auto_rag_kb_status()
        last_run = self._latest_maintenance_run()
        running = self._latest_maintenance_run(status="running")
        last_success = self._latest_maintenance_run(status="succeeded")
        last_failure = self._latest_maintenance_run(status="partial") or self._latest_maintenance_run(status="failed")
        cooldown_until = None
        if last_run and last_run.cooldown_until and last_run.cooldown_until > self._utcnow():
            cooldown_until = last_run.cooldown_until
        return PolicyCrawlerMaintenanceStatus(
            is_running=running is not None,
            current_stage=(running.current_stage if running else None),
            last_run=last_run,
            last_success=last_success,
            last_failure=last_failure,
            cooldown_until=cooldown_until,
            target_kb_id=auto_kb.kb_id,
            target_kb_name=auto_kb.kb_name,
            summary=last_run.summary if last_run else {},
            warnings=last_run.warnings if last_run else [],
        )

    def list_policy_crawler_maintenance_runs_page(self, *, page: int = 1, page_size: int = 20, status: str | None = None) -> PolicyCrawlerMaintenanceRunPage:
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 100))
        where = []
        params: list[object] = []
        if status:
            where.append("status = {p}")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        total_rows = self._select_rows(
            f"SELECT COUNT(*) AS count FROM policy_crawler_maintenance_runs {where_sql}",
            params,
        )
        rows = self._select_rows(
            f"""
            SELECT * FROM policy_crawler_maintenance_runs
            {where_sql}
            ORDER BY started_at DESC
            LIMIT {safe_page_size} OFFSET {(safe_page - 1) * safe_page_size}
            """,
            params,
        )
        return PolicyCrawlerMaintenanceRunPage(
            items=[self._row_to_maintenance_run(row) for row in rows],
            total=int(total_rows[0]["count"]) if total_rows else 0,
            page=safe_page,
            page_size=safe_page_size,
        )

    def get_policy_crawler_maintenance_run(self, *, maintenance_run_id: str) -> PolicyCrawlerMaintenanceRunSummary:
        rows = self._select_rows(
            "SELECT * FROM policy_crawler_maintenance_runs WHERE maintenance_run_id = {p}",
            [maintenance_run_id],
        )
        if not rows:
            raise KeyError(maintenance_run_id)
        return self._row_to_maintenance_run(rows[0])

    def _create_maintenance_run(
        self,
        *,
        maintenance_run_id: str,
        trigger_type: str,
        triggered_by_user_id: str | None,
        triggered_by_role: str | None,
        target_kb_id: str | None,
        target_kb_name: str,
        cooldown_until: datetime,
    ) -> None:
        now = self._utcnow().isoformat()
        self._execute_statement(
            """
            INSERT INTO policy_crawler_maintenance_runs (
                maintenance_run_id, trigger_type, triggered_by_user_id, triggered_by_role,
                status, current_stage, target_kb_id, target_kb_name, started_at,
                cooldown_until, summary_json, warnings_json, metadata_json
            )
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            [
                maintenance_run_id,
                trigger_type,
                triggered_by_user_id,
                triggered_by_role,
                "running",
                "starting",
                target_kb_id,
                target_kb_name,
                now,
                cooldown_until.isoformat(),
                "{}",
                "[]",
                "{}",
            ],
        )

    def _update_maintenance_stage(self, maintenance_run_id: str, current_stage: str) -> None:
        self._execute_statement(
            "UPDATE policy_crawler_maintenance_runs SET current_stage = {p} WHERE maintenance_run_id = {p}",
            [current_stage, maintenance_run_id],
        )

    def _finish_maintenance_run(
        self,
        *,
        maintenance_run_id: str,
        status: str,
        current_stage: str,
        source_count: int,
        candidate_count: int,
        published_count: int,
        skipped_count: int,
        failed_count: int,
        summary: dict[str, Any],
        warnings: list[str],
        error_stage: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        self._execute_statement(
            """
            UPDATE policy_crawler_maintenance_runs
            SET status = {p}, current_stage = {p}, source_count = {p}, candidate_count = {p},
                published_count = {p}, skipped_count = {p}, failed_count = {p},
                finished_at = {p}, error_stage = {p}, error_detail = {p},
                summary_json = {p}, warnings_json = {p}
            WHERE maintenance_run_id = {p}
            """,
            [
                status,
                current_stage,
                source_count,
                candidate_count,
                published_count,
                skipped_count,
                failed_count,
                self._utcnow().isoformat(),
                error_stage,
                error_detail,
                json.dumps(summary, ensure_ascii=False),
                json.dumps(warnings, ensure_ascii=False),
                maintenance_run_id,
            ],
        )

    def _latest_maintenance_run(self, *, status: str | None = None) -> PolicyCrawlerMaintenanceRunSummary | None:
        where = "WHERE status = {p}" if status else ""
        params: list[object] = [status] if status else []
        rows = self._select_rows(
            f"""
            SELECT * FROM policy_crawler_maintenance_runs
            {where}
            ORDER BY started_at DESC
            LIMIT 1
            """,
            params,
        )
        return self._row_to_maintenance_run(rows[0]) if rows else None

    def _active_maintenance_cooldown_until(self) -> datetime | None:
        latest = self._latest_maintenance_run()
        if latest and latest.cooldown_until:
            return latest.cooldown_until
        return None

    def _row_to_maintenance_run(self, row: dict[str, Any]) -> PolicyCrawlerMaintenanceRunSummary:
        payload = dict(row)
        payload["summary"] = _json_object(payload.pop("summary_json", None))
        warnings = _json_value(payload.pop("warnings_json", None), default=[])
        payload["warnings"] = warnings if isinstance(warnings, list) else []
        payload["metadata"] = _json_object(payload.pop("metadata_json", None))
        return PolicyCrawlerMaintenanceRunSummary.model_validate(payload)

    def _user_role(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        user = next((item for item in self.auth_service.list_users() if item.user_id == user_id), None)
        return str(user.role) if user else None

    def get_policy_crawler_auto_rag_kb_status(self) -> PolicyCrawlerAutoRagKbStatus:
        from app.rag.kb.crawler_bridge import AUTO_CRAWLER_RAG_KB_NAME, OFFICIAL_POLICY_RAG_KB_NAME, SYSTEM_POLICY_CRAWLER_USER_ID
        from app.rag.spine import get_rag_spine_service

        service = get_rag_spine_service()
        kbs = service.list_kbs(owner_user_id=SYSTEM_POLICY_CRAWLER_USER_ID)
        kb = next((item for item in kbs if item.name in {AUTO_CRAWLER_RAG_KB_NAME, OFFICIAL_POLICY_RAG_KB_NAME}), None)
        scheduler = get_policy_crawler_scheduler()
        recent_candidates = scheduler.list_candidates(limit=20)
        recent_results = [
            PolicyCrawlerCandidateSummary.model_validate(candidate.model_dump(mode="python"))
            for candidate in recent_candidates
            if candidate.metadata.get("rag_kb_id") and candidate.metadata.get("publish_target") == "rag_pro_kb"
        ][:8]
        latest_run = scheduler.list_runs(limit=1)
        if kb is None:
            return PolicyCrawlerAutoRagKbStatus(
                found=False,
                latest_run_id=latest_run[0].run_id if latest_run else None,
                latest_run_status=latest_run[0].status if latest_run else None,
                recent_results=recent_results,
            )
        documents = service.list_documents(owner_user_id=SYSTEM_POLICY_CRAWLER_USER_ID, kb_id=kb.kb_id)
        indexed_chunk_count = sum(doc.indexed_chunk_count for doc in documents)
        latest_ingest = next((candidate for candidate in recent_results if candidate.rag_pipeline_status), None)
        return PolicyCrawlerAutoRagKbStatus(
            kb_id=kb.kb_id,
            kb_name=AUTO_CRAWLER_RAG_KB_NAME,
            found=True,
            visibility=kb.visibility,
            document_count=len(documents),
            indexed_chunk_count=indexed_chunk_count,
            latest_run_id=latest_run[0].run_id if latest_run else None,
            latest_run_status=latest_run[0].status if latest_run else None,
            latest_ingest_status=latest_ingest.rag_pipeline_status if latest_ingest else None,
            latest_ingest_at=latest_ingest.updated_at if latest_ingest else None,
            recent_results=recent_results,
        )

    def _auto_ingest_policy_crawler_run(
        self,
        *,
        run_id: str,
        reviewed_by_user_id: str | None,
        payload: PolicyCrawlerRunRequest,
    ):
        scheduler = get_policy_crawler_scheduler()
        candidates = scheduler.list_candidates(run_id=run_id, limit=200)
        items: list[PolicyCrawlerBatchPublishItem] = []
        for candidate in candidates:
            skip_reason = self._auto_rag_skip_reason(candidate, payload=payload)
            if skip_reason:
                items.append(
                    PolicyCrawlerBatchPublishItem(
                        candidate_id=candidate.candidate_id,
                        status="skipped",
                        reason=skip_reason,
                    )
                )
                continue
            items.append(
                self._publish_candidate_to_rag_item(
                    candidate_id=candidate.candidate_id,
                    reviewed_by_user_id=reviewed_by_user_id,
                    skip_duplicates=payload.auto_rag_ingest_skip_duplicate,
                )
            )
        metadata = {
            "auto_rag_ingest_enabled": True,
            "auto_rag_attempted_count": sum(1 for item in items if item.status != "skipped"),
            "auto_rag_indexed_count": sum(1 for item in items if item.status == "published"),
            "auto_rag_failed_count": sum(1 for item in items if item.status == "failed"),
            "auto_rag_skipped_count": sum(1 for item in items if item.status == "skipped"),
            "auto_rag_items": [item.model_dump(mode="python") for item in items],
            "target_kb_id": self._auto_crawler_target_kb_id(),
            "target_kb_name": "自动爬虫知识库",
            "auto_rag_thresholds": payload.model_dump(mode="python"),
        }
        return scheduler.store.update_run_metadata(run_id=run_id, metadata=metadata)

    def _auto_rag_skip_reason(self, candidate, *, payload: PolicyCrawlerRunRequest) -> str | None:
        metadata = candidate.metadata
        if candidate.status == "rejected":
            return "rejected_candidate"
        if metadata.get("rag_doc_id") and metadata.get("rag_pipeline_status") == "indexed" and int(metadata.get("rag_indexed_chunk_count") or 0) > 0:
            return "already_indexed"
        if payload.auto_rag_ingest_skip_duplicate and metadata.get("skip_reason") == "duplicate_content_hash":
            if metadata.get("rag_doc_id") and int(metadata.get("rag_indexed_chunk_count") or metadata.get("indexed_chunk_count") or 0) > 0:
                return "already_indexed"
            # A duplicated crawler artifact can still be missing its RAG document
            # when earlier vector indexing failed or Milvus was offline. Let active
            # maintenance / per-run auto ingest repair that gap instead of
            # permanently skipping the candidate.
        if int(metadata.get("candidate_quality_score") or 0) < payload.auto_rag_ingest_min_quality:
            return "low_quality"
        if int(metadata.get("extraction_quality_score") or 0) < payload.auto_rag_ingest_min_extraction:
            return "low_extraction_score"
        if int(metadata.get("markdown_size") or 0) < payload.auto_rag_ingest_min_markdown_size:
            return "small_markdown"
        if int(metadata.get("estimated_chunk_count") or 0) <= 0:
            return "zero_estimated_chunks"
        return None

    def _publish_candidate_to_rag_item(
        self,
        *,
        candidate_id: str,
        reviewed_by_user_id: str | None,
        skip_duplicates: bool,
    ) -> PolicyCrawlerBatchPublishItem:
        scheduler = get_policy_crawler_scheduler()
        candidate = scheduler.store.get_candidate(candidate_id)
        if candidate is None:
            return PolicyCrawlerBatchPublishItem(candidate_id=candidate_id, status="failed", reason="not_found")
        if (
            skip_duplicates
            and candidate.metadata.get("skip_reason") == "duplicate_content_hash"
            and candidate.metadata.get("rag_doc_id")
            and int(candidate.metadata.get("rag_indexed_chunk_count") or candidate.metadata.get("indexed_chunk_count") or 0) > 0
        ):
            return PolicyCrawlerBatchPublishItem(
                candidate_id=candidate_id,
                status="skipped",
                rag_doc_id=str(candidate.metadata.get("rag_doc_id")),
                indexed_chunk_count=int(candidate.metadata.get("rag_indexed_chunk_count") or 0),
                reason="already_indexed",
            )
        try:
            publish_crawled_candidate_to_rag_kb(
                candidate_id=candidate_id,
                reviewed_by_user_id=reviewed_by_user_id,
            )
            refreshed = scheduler.store.get_candidate(candidate_id)
            metadata = refreshed.metadata if refreshed is not None else {}
            self._clear_retrieval_caches("public_policy")
            return PolicyCrawlerBatchPublishItem(
                candidate_id=candidate_id,
                status="published",
                rag_doc_id=metadata.get("rag_doc_id"),
                indexed_chunk_count=int(metadata.get("rag_indexed_chunk_count") or metadata.get("indexed_chunk_count") or 0),
                reason=None,
            )
        except Exception as exc:  # noqa: BLE001
            return PolicyCrawlerBatchPublishItem(
                candidate_id=candidate_id,
                status="failed",
                reason=str(exc),
            )

    def _auto_crawler_target_kb_id(self) -> str | None:
        try:
            return self.get_policy_crawler_auto_rag_kb_status().kb_id
        except Exception:
            return None

    @staticmethod
    def _maintenance_run_payload(payload: PolicyCrawlerActiveMaintenanceRequest) -> PolicyCrawlerRunRequest:
        return PolicyCrawlerRunRequest(
            auto_rag_ingest_enabled=True,
            auto_rag_ingest_min_quality=payload.auto_rag_ingest_min_quality,
            auto_rag_ingest_min_extraction=payload.auto_rag_ingest_min_extraction,
            auto_rag_ingest_min_markdown_size=payload.auto_rag_ingest_min_markdown_size,
            auto_rag_ingest_skip_duplicate=payload.auto_rag_ingest_skip_duplicate,
        )

    @staticmethod
    def _candidate_needs_rag_ingestion_retry(candidate) -> bool:
        metadata = candidate.metadata
        if candidate.status != "pending_review":
            return False
        if metadata.get("rag_doc_id") and metadata.get("rag_pipeline_status") == "indexed" and int(metadata.get("rag_indexed_chunk_count") or 0) > 0:
            return False
        if metadata.get("rag_pipeline_status") in {None, "", "failed"}:
            return True
        if int(metadata.get("rag_indexed_chunk_count") or metadata.get("indexed_chunk_count") or 0) <= 0:
            return True
        if metadata.get("rag_search_smoke_passed") is False:
            return True
        return False

    def _select_sources_for_active_maintenance(self, payload: PolicyCrawlerActiveMaintenanceRequest):
        scheduler = get_policy_crawler_scheduler()
        source_ids = {item.strip() for item in payload.source_ids if item.strip()}
        domains = {item.strip().lower().lstrip(".") for item in payload.domains if item.strip()}
        selected = []
        for source in scheduler.list_sources():
            if not source.is_enabled:
                continue
            source_domain = source.allowed_domain.lower().lstrip(".")
            explicit_match = (source.source_id in source_ids) or (source_domain in domains)
            metadata_enabled = bool(source.metadata.get("active_relay_auto_update_enabled"))
            never_crawled = source.last_run_at is None
            if source_ids or domains:
                if explicit_match:
                    selected.append(source)
                continue
            if metadata_enabled and never_crawled:
                selected.append(source)
        selected.sort(key=lambda item: int(item.metadata.get("priority") or 50), reverse=True)
        return selected

    def reject_policy_crawler_candidate(
        self,
        *,
        candidate_id: str,
        reviewed_by_user_id: str | None,
    ) -> PolicyCrawlerCandidateSummary:
        scheduler = get_policy_crawler_scheduler()
        candidate = scheduler.reject_candidate(
            candidate_id=candidate_id,
            reviewed_by_user_id=reviewed_by_user_id,
        )
        return PolicyCrawlerCandidateSummary.model_validate(candidate.model_dump(mode="python"))

    def update_private_sample(self, *, doc_id: str, is_enabled: bool, session_attachable: bool, updated_by_user_id: str):
        knowledge_service = get_knowledge_service()
        item = knowledge_service.store.get_item(doc_id)
        if item is None or item.library_scope != "shared":
            item = knowledge_service.store.get_item_by_source(
                owner_user_id=None,
                library_scope="shared",
                source_type="private_sample_repo",
                source_ref=doc_id,
            )
        if item is None:
            raise KeyError(doc_id)
        knowledge_service.store.upsert_item(
            {
                **item.model_dump(mode="python"),
                "is_enabled": is_enabled,
                "session_attachable": session_attachable,
                "updated_at": self._utcnow().isoformat(),
            }
        )
        self._clear_retrieval_caches("private_sample")
        refreshed = knowledge_service.store.get_item(item.knowledge_item_id) or item
        return AdminPrivateSampleItem.model_validate(
            {
                "doc_id": refreshed.knowledge_item_id,
                "title": refreshed.title,
                "source_type": refreshed.source_type,
                "sample_type": refreshed.sample_type or "doc",
                "business_topic": refreshed.business_topic or "project_background",
                "session_attachable": refreshed.session_attachable,
                "is_enabled": refreshed.is_enabled,
            }
        )

    def list_knowledge_items(self, *, owner_user_id: str | None = None, filters=None) -> list[KnowledgeItemSummary]:
        knowledge_service = get_knowledge_service()
        items = knowledge_service.list_visible_items(owner_user_id=owner_user_id, filters=filters)
        return [KnowledgeItemSummary.model_validate(item.model_dump()) for item in items]

    def update_knowledge_item(
        self,
        *,
        knowledge_item_id: str,
        is_enabled: bool | None = None,
        session_attachable: bool | None = None,
    ) -> KnowledgeItemSummary:
        knowledge_service = get_knowledge_service()
        item = knowledge_service.store.get_item(knowledge_item_id)
        if item is None:
            raise KeyError(knowledge_item_id)
        updated_item = knowledge_service.store.upsert_item(
            {
                **item.model_dump(mode="python"),
                "is_enabled": item.is_enabled if is_enabled is None else is_enabled,
                "session_attachable": item.session_attachable if session_attachable is None else session_attachable,
                "updated_at": self._utcnow().isoformat(),
            }
        )
        self._clear_retrieval_caches("private_sample")
        return KnowledgeItemSummary.model_validate(updated_item.model_dump())

    def list_knowledge_tasks(self, *, owner_user_id: str | None = None) -> list[KnowledgeTaskSummary]:
        knowledge_service = get_knowledge_service()
        tasks = knowledge_service.list_tasks(owner_user_id=owner_user_id, include_shared=True)
        return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in tasks]

    def trigger_knowledge_scan(self, *, requested_by_user_id: str, scope: str = "all") -> list[KnowledgeTaskSummary]:
        knowledge_service = get_knowledge_service()
        discovered = knowledge_service.discover_pending_sources()
        try:
            knowledge_service.run_queued_tasks()
        except Exception:
            pass
        self._clear_retrieval_caches("private_sample")
        return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in discovered]

    def trigger_knowledge_rebuild(self, *, requested_by_user_id: str, scope: str = "all") -> list[KnowledgeTaskSummary]:
        del requested_by_user_id, scope
        knowledge_service = get_knowledge_service()
        tasks = knowledge_service.run_queued_tasks()
        self._clear_retrieval_caches("private_sample")
        return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in tasks]

    def retry_knowledge_task(self, *, task_id: str, requested_by_user_id: str | None = None) -> KnowledgeTaskSummary:
        knowledge_service = get_knowledge_service()
        task = knowledge_service.retry_task(task_id=task_id, requested_by_user_id=requested_by_user_id)
        try:
            knowledge_service.run_queued_tasks()
        except Exception:
            pass
        self._clear_retrieval_caches("private_sample")
        latest = knowledge_service.get_task(task.task_id) or task
        return KnowledgeTaskSummary.model_validate(latest.model_dump())

    def list_knowledge_refresh_tasks(self) -> list[KnowledgeRefreshTask]:
        return []

    def trigger_knowledge_refresh(self, *, scope: KnowledgeRefreshScope, requested_by_user_id: str) -> KnowledgeRefreshTask:
        del scope
        tasks = self.trigger_knowledge_scan(requested_by_user_id=requested_by_user_id)
        if tasks:
            return KnowledgeRefreshTask(
                task_id=tasks[0].task_id,
                scope="all",
                status=tasks[0].status,
                requested_by_user_id=requested_by_user_id,
                summary=tasks[0].summary,
                created_at=tasks[0].created_at,
                started_at=tasks[0].started_at,
                finished_at=tasks[0].finished_at,
            )
        return KnowledgeRefreshTask(
            task_id=f"refresh-{uuid4().hex[:12]}",
            scope="all",
            status="succeeded",
            requested_by_user_id=requested_by_user_id,
            summary="Knowledge refresh completed.",
            created_at=self._utcnow(),
            started_at=self._utcnow(),
            finished_at=self._utcnow(),
        )

    def get_system_status(self) -> AdminSystemStatus:
        settings = get_settings()
        provider = get_chat_provider().describe()
        knowledge_service = get_knowledge_service()
        private_samples = self.list_private_samples()
        knowledge_items = knowledge_service.list_visible_items(owner_user_id=None)
        knowledge_tasks = knowledge_service.list_tasks(owner_user_id=None, include_shared=True)
        latest_refresh_status = knowledge_tasks[0].status if knowledge_tasks else None
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) AS count FROM users")
                    total_users = cursor.fetchone()["count"]
                    cursor.execute("SELECT COUNT(*) AS count FROM sessions")
                    total_sessions = cursor.fetchone()["count"]
                    cursor.execute("SELECT COUNT(*) AS count FROM reports")
                    total_reports = cursor.fetchone()["count"]
                    cursor.execute("SELECT COUNT(*) AS count FROM feedback_entries")
                    total_feedback = cursor.fetchone()["count"]
                    cursor.execute("SELECT COUNT(*) AS count FROM knowledge_items")
                    total_knowledge_items = cursor.fetchone()["count"]
                    cursor.execute("SELECT COUNT(*) AS count FROM knowledge_tasks")
                    total_knowledge_tasks = cursor.fetchone()["count"]
            else:
                total_users = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
                total_sessions = connection.execute("SELECT COUNT(*) AS count FROM sessions").fetchone()["count"]
                total_reports = connection.execute("SELECT COUNT(*) AS count FROM reports").fetchone()["count"]
                total_feedback = connection.execute("SELECT COUNT(*) AS count FROM feedback_entries").fetchone()["count"]
                total_knowledge_items = connection.execute("SELECT COUNT(*) AS count FROM knowledge_items").fetchone()["count"]
                total_knowledge_tasks = connection.execute("SELECT COUNT(*) AS count FROM knowledge_tasks").fetchone()["count"]
        return AdminSystemStatus(
            app_name=settings.app_name,
            version=settings.app_version,
            env=settings.app_env,
            database_backend=self.backend_kind,
            model_provider_mode=provider.mode,
            model_name=provider.default_model,
            total_users=int(total_users),
            total_sessions=int(total_sessions),
            total_reports=int(total_reports),
            total_feedback_entries=int(total_feedback),
            total_private_samples=len(private_samples),
            enabled_private_samples=sum(1 for item in private_samples if item.is_enabled),
            latest_refresh_status=latest_refresh_status,
            total_knowledge_items=int(total_knowledge_items),
            total_knowledge_tasks=int(total_knowledge_tasks),
        )

    def _count_grouped_rows(self, table_name: str, column_name: str) -> dict[str, int]:
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT {column_name} AS owner_user_id, COUNT(*) AS count
                        FROM {table_name}
                        WHERE {column_name} IS NOT NULL
                        GROUP BY {column_name}
                        """
                    )
                    rows = cursor.fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT {column_name} AS owner_user_id, COUNT(*) AS count
                    FROM {table_name}
                    WHERE {column_name} IS NOT NULL
                    GROUP BY {column_name}
                    """
                ).fetchall()
        return {row["owner_user_id"]: int(row["count"]) for row in rows}

    def _persist_refresh_task(
        self,
        *,
        task_id: str,
        scope: KnowledgeRefreshScope,
        status: KnowledgeRefreshStatus,
        requested_by_user_id: str,
        summary: str,
        created_at: datetime,
        started_at: datetime | None,
        finished_at: datetime | None,
        replace: bool = False,
    ) -> None:
        created_at_value = created_at.isoformat()
        started_at_value = started_at.isoformat() if started_at else None
        finished_at_value = finished_at.isoformat() if finished_at else None
        if replace:
            delete_statement = "DELETE FROM knowledge_refresh_tasks WHERE task_id = %s" if self.backend_kind == "postgresql" else "DELETE FROM knowledge_refresh_tasks WHERE task_id = ?"
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    if replace:
                        cursor.execute(delete_statement, (task_id,))
                    cursor.execute(
                        """
                        INSERT INTO knowledge_refresh_tasks (
                            task_id, scope, status, requested_by_user_id, summary, created_at, started_at, finished_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            task_id,
                            scope,
                            status,
                            requested_by_user_id,
                            summary,
                            created_at_value,
                            started_at_value,
                            finished_at_value,
                        ),
                    )
            else:
                if replace:
                    connection.execute(delete_statement, (task_id,))
                connection.execute(
                    """
                    INSERT INTO knowledge_refresh_tasks (
                        task_id, scope, status, requested_by_user_id, summary, created_at, started_at, finished_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        scope,
                        status,
                        requested_by_user_id,
                        summary,
                        created_at_value,
                        started_at_value,
                        finished_at_value,
                    ),
                )

    @staticmethod
    def _clear_retrieval_caches(scope: KnowledgeRefreshScope) -> None:
        from app.rag.service import get_rag_engine_service

        if scope in {"public_policy", "all"}:
            load_public_policy_documents.cache_clear()
            get_public_policy_retriever.cache_clear()
        if scope in {"private_sample", "all"}:
            refresh_private_sample_catalog()
            load_private_sample_documents.cache_clear()
            get_private_sample_retriever.cache_clear()
        get_mixed_scope_retriever.cache_clear()
        get_rag_engine_service.cache_clear()

    @staticmethod
    def _policy_showcase_source_summary(source: ShowcasePolicySource) -> PolicyShowcaseSourceSummary:
        return PolicyShowcaseSourceSummary(
            source_id=source.source_id,
            title=source.title,
            source_url=source.source_url,
            source_label=source.source_label,
            description=source.description,
            default_query=source.default_query,
            content_type=source.content_type,
            metadata=source.metadata,
        )

    @staticmethod
    def _get_policy_showcase_item(source: ShowcasePolicySource):
        knowledge_service = get_knowledge_service()
        return knowledge_service.store.get_item_by_source(
            owner_user_id=None,
            library_scope="shared",
            source_type="public_policy_web",
            source_ref=source.source_url,
        )

    @staticmethod
    def _validate_reloaded_sources(scope: KnowledgeRefreshScope) -> str:
        summaries: list[str] = []
        if scope in {"public_policy", "all"}:
            public_documents = load_public_policy_documents()
            get_public_policy_retriever()
            summaries.append(f"public_policy={len(public_documents)} docs")
        if scope in {"private_sample", "all"}:
            private_documents = load_private_sample_documents()
            get_private_sample_retriever()
            summaries.append(f"private_sample={len(private_documents)} docs")
        get_mixed_scope_retriever()
        return "; ".join(summaries) or "no-op"


def _json_value(value: object, *, default: object) -> object:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _json_object(value: object) -> dict[str, Any]:
    parsed = _json_value(value, default={})
    return parsed if isinstance(parsed, dict) else {}


@lru_cache(maxsize=1)
def get_admin_service() -> AdminService:
    return AdminService()
