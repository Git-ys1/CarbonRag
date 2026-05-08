import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from app.admin.schemas import (
    AdminFeedbackOverview,
    AdminFeedbackRecentEntry,
    AdminPrivateSampleItem,
    AdminSystemStatus,
    AdminUserSummary,
    KnowledgeRefreshTask,
    KnowledgeRefreshStatus,
    KnowledgeRefreshScope,
    PolicyShowcaseChunkSummary,
    PolicyShowcaseRetrievalHit,
    PolicyShowcaseRetrievalPreview,
    PolicyShowcaseSourceSummary,
    PolicyShowcaseStatus,
    PolicyShowcaseWorkflowNodeSummary,
    PolicyShowcaseWorkflowSummary,
)
from app.ai_runtime.providers.factory import get_chat_provider
from app.auth.schemas import UserRole
from app.auth.service import AuthService, get_auth_service
from app.core.config import get_settings
from app.knowledge import get_knowledge_service
from app.knowledge.policy_showcase import (
    ShowcasePolicySource,
    get_showcase_policy_source,
    list_showcase_policy_sources,
)
from app.private_samples.catalog import (
    list_admin_private_sample_catalog,
    refresh_private_sample_catalog,
)
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

    def update_user(self, *, user_id: str, role: UserRole, is_active: bool):
        return self.auth_service.update_user(user_id=user_id, role=role, is_active=is_active)

    def reset_password(self, *, user_id: str) -> str:
        return self.auth_service.reset_password(user_id=user_id)

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


@lru_cache(maxsize=1)
def get_admin_service() -> AdminService:
    return AdminService()
