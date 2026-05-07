from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from app.core.config import get_settings
from app.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeChunkInput,
    KnowledgeItemDetailResponse,
    KnowledgeIndexStatus,
    KnowledgeIngestStatus,
    KnowledgeItem,
    KnowledgeItemListFilters,
    KnowledgeParseStatus,
    MyUploadEntry,
    KnowledgeTask,
    KnowledgeTaskListFilters,
    KnowledgeTaskStatus,
    KnowledgeTaskType,
)
from app.runtime_db.compat import connect_postgres
from app.runtime_db.bootstrap import bootstrap_runtime_database, get_runtime_backend_kind
from app.session.store import DEFAULT_SESSION_DB_PATH


class KnowledgeStore:
    def __init__(self, *, database_url: str | None = None, sqlite_db_path: Path | str | None = None) -> None:
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self.sqlite_db_path = Path(sqlite_db_path or DEFAULT_SESSION_DB_PATH)
        self.db_path = self.sqlite_db_path
        self.backend_kind = get_runtime_backend_kind(self.database_url)
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_runtime_database(database_url=self.database_url, sqlite_db_path=self.sqlite_db_path)

    def _connect(self):
        if self.backend_kind == "postgresql":
            return connect_postgres(self.database_url)
        connection = sqlite3.connect(self.sqlite_db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)

    def get_item(self, knowledge_item_id: str) -> KnowledgeItem | None:
        rows = self._select("SELECT * FROM knowledge_items WHERE knowledge_item_id = {p}", [knowledge_item_id])
        if not rows:
            return None
        return self._decorate_item(self._row_to_item(rows[0]))

    def get_visible_item(self, *, owner_user_id: str | None, knowledge_item_id: str) -> KnowledgeItem | None:
        item = self.get_item(knowledge_item_id)
        if item is None:
            return None
        if owner_user_id is not None and item.owner_user_id == owner_user_id:
            return item
        if item.library_scope == "shared" and item.is_enabled:
            return item
        if owner_user_id is None:
            return item
        return None

    def get_item_by_source(
        self,
        *,
        owner_user_id: str | None,
        library_scope: str,
        source_type: str,
        source_ref: str,
    ) -> KnowledgeItem | None:
        items = self.list_items(
            owner_user_id=owner_user_id,
            include_shared=True,
            library_scope=library_scope,
            source_type=source_type,
            source_ref=source_ref,
        )
        return items[0] if items else None

    def list_items(
        self,
        *,
        owner_user_id: str | None = None,
        include_shared: bool = True,
        knowledge_item_ids: list[str] | None = None,
        **filters: Any,
    ) -> list[KnowledgeItem]:
        filter_model = KnowledgeItemListFilters.model_validate(filters)
        clauses: list[str] = []
        params: list[object] = []

        if knowledge_item_ids:
            placeholders = ", ".join(self._placeholder() for _ in knowledge_item_ids)
            clauses.append(f"knowledge_item_id IN ({placeholders})")
            params.extend(knowledge_item_ids)

        if owner_user_id is not None:
            if include_shared:
                clauses.append(
                    f"((owner_user_id = {self._placeholder()}) OR (library_scope = 'shared' AND is_enabled = {self._placeholder()}))"
                )
                params.extend([owner_user_id, True])
            else:
                clauses.append(f"owner_user_id = {self._placeholder()}")
                params.append(owner_user_id)
        elif filter_model.owner_user_id is not None:
            clauses.append(f"owner_user_id = {self._placeholder()}")
            params.append(filter_model.owner_user_id)

        if filter_model.library_scope is not None:
            clauses.append(f"library_scope = {self._placeholder()}")
            params.append(filter_model.library_scope)
        if filter_model.source_type is not None:
            clauses.append(f"source_type = {self._placeholder()}")
            params.append(filter_model.source_type)
        if filter_model.parse_status is not None:
            clauses.append(f"parse_status = {self._placeholder()}")
            params.append(filter_model.parse_status)
        if filter_model.ingest_status is not None:
            clauses.append(f"ingest_status = {self._placeholder()}")
            params.append(filter_model.ingest_status)
        if filter_model.index_status is not None:
            clauses.append(f"index_status = {self._placeholder()}")
            params.append(filter_model.index_status)
        if filter_model.session_attachable is not None:
            clauses.append(f"session_attachable = {self._placeholder()}")
            params.append(filter_model.session_attachable)
        if filter_model.is_enabled is not None:
            clauses.append(f"is_enabled = {self._placeholder()}")
            params.append(filter_model.is_enabled)
        if filter_model.source_ref is not None:
            clauses.append(f"source_ref = {self._placeholder()}")
            params.append(filter_model.source_ref)
        if filter_model.file_id is not None:
            clauses.append(f"file_id = {self._placeholder()}")
            params.append(filter_model.file_id)

        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._select(f"SELECT * FROM knowledge_items{where_sql} ORDER BY updated_at DESC, created_at DESC", params)
        items = [self._decorate_item(self._row_to_item(row)) for row in rows]

        if knowledge_item_ids:
            order_map = {knowledge_item_id: index for index, knowledge_item_id in enumerate(knowledge_item_ids)}
            items.sort(key=lambda item: order_map.get(item.knowledge_item_id, len(order_map)))
        return items

    def list_visible_items(self, *, owner_user_id: str | None, filters: KnowledgeItemListFilters | None = None) -> list[KnowledgeItem]:
        filters = filters or KnowledgeItemListFilters()
        return self.list_items(
            owner_user_id=owner_user_id,
            include_shared=True,
            knowledge_item_ids=filters.knowledge_item_ids or None,
            library_scope=filters.library_scope,
            source_type=filters.source_type,
            parse_status=filters.parse_status,
            ingest_status=filters.ingest_status,
            index_status=filters.index_status,
            session_attachable=filters.session_attachable,
            is_enabled=filters.is_enabled,
            source_ref=filters.source_ref,
            file_id=filters.file_id,
        )

    def list_admin_items(self, *, filters: KnowledgeItemListFilters | None = None) -> list[KnowledgeItem]:
        filters = filters or KnowledgeItemListFilters()
        return self.list_items(
            owner_user_id=None,
            include_shared=True,
            knowledge_item_ids=filters.knowledge_item_ids or None,
            library_scope=filters.library_scope,
            source_type=filters.source_type,
            parse_status=filters.parse_status,
            ingest_status=filters.ingest_status,
            index_status=filters.index_status,
            session_attachable=filters.session_attachable,
            is_enabled=filters.is_enabled,
            source_ref=filters.source_ref,
            file_id=filters.file_id,
        )

    def upsert_item(self, item: KnowledgeItem | dict[str, Any]) -> KnowledgeItem:
        model = item if isinstance(item, KnowledgeItem) else KnowledgeItem.model_validate(item)
        existing = self.get_item(model.knowledge_item_id)
        params = (
            model.knowledge_item_id,
            model.tenant_id,
            model.owner_user_id,
            model.visibility,
            model.created_by,
            model.library_scope,
            model.source_type,
            model.source_ref,
            model.file_id,
            model.source,
            model.source_url,
            model.sample_type,
            model.business_topic,
            model.title,
            model.mime_type,
            model.storage_path,
            model.parse_status,
            model.ingest_status,
            model.index_status,
            model.is_enabled,
            model.session_attachable,
            model.source_hash,
            model.source_mtime,
            model.last_error,
            model.created_at.isoformat(),
            model.updated_at.isoformat(),
            model.last_indexed_at.isoformat() if model.last_indexed_at else None,
        )
        if existing is None:
            self._execute(
                """
                INSERT INTO knowledge_items (
                    knowledge_item_id, tenant_id, owner_user_id, visibility, created_by,
                    library_scope, source_type, source_ref, file_id, source, source_url,
                    sample_type, business_topic, title, mime_type, storage_path,
                    parse_status, ingest_status, index_status, is_enabled, session_attachable,
                    source_hash, source_mtime, last_error, created_at, updated_at, last_indexed_at
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                list(params),
            )
        else:
            self._execute(
                """
                UPDATE knowledge_items
                SET tenant_id = {p}, owner_user_id = {p}, visibility = {p}, created_by = {p},
                    library_scope = {p}, source_type = {p}, source_ref = {p}, file_id = {p},
                    source = {p}, source_url = {p}, sample_type = {p}, business_topic = {p}, title = {p},
                    mime_type = {p}, storage_path = {p}, parse_status = {p}, ingest_status = {p}, index_status = {p},
                    is_enabled = {p}, session_attachable = {p}, source_hash = {p}, source_mtime = {p},
                    last_error = {p}, created_at = {p}, updated_at = {p}, last_indexed_at = {p}
                WHERE knowledge_item_id = {p}
                """,
                [*params[1:], model.knowledge_item_id],
            )
        refreshed = self.get_item(model.knowledge_item_id)
        if refreshed is None:
            raise RuntimeError("knowledge item refresh failed")
        return refreshed

    def replace_chunks(
        self,
        *,
        knowledge_item_id: str,
        chunks: list[KnowledgeChunk | KnowledgeChunkInput | dict[str, Any]],
        indexed_at: datetime | None = None,
    ) -> None:
        self._execute("DELETE FROM knowledge_chunks WHERE knowledge_item_id = {p}", [knowledge_item_id])
        for chunk in chunks:
            model = chunk if isinstance(chunk, KnowledgeChunk) else KnowledgeChunk.model_validate(chunk)
            self._execute(
                """
                INSERT INTO knowledge_chunks (
                    knowledge_item_id, chunk_id, tenant_id, owner_user_id, visibility, created_by,
                    title, source_type, library_scope, source, source_url,
                    issued_at, region, doc_type, sample_type, business_topic, snippet, order_index,
                    metadata_json, created_at, updated_at
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                [
                    model.knowledge_item_id,
                    model.chunk_id,
                    model.tenant_id,
                    model.owner_user_id,
                    model.visibility,
                    model.created_by,
                    model.title,
                    model.source_type,
                    model.library_scope,
                    model.source,
                    model.source_url,
                    model.issued_at,
                    model.region,
                    model.doc_type,
                    model.sample_type,
                    model.business_topic,
                    model.snippet,
                    model.order_index,
                    json.dumps(model.metadata, ensure_ascii=False),
                    (model.created_at or indexed_at or self.utcnow()).isoformat(),
                    (model.updated_at or model.created_at or indexed_at or self.utcnow()).isoformat(),
                ],
            )
        self.mark_item_stage(
            knowledge_item_id=knowledge_item_id,
            parse_status="parsed",
            ingest_status="ingested",
            index_status="indexed",
            last_error=None,
            last_indexed_at=indexed_at or self.utcnow(),
        )

    def list_chunks(
        self,
        knowledge_item_id: str | None = None,
        *,
        knowledge_item_ids: list[str] | None = None,
    ) -> list[KnowledgeChunk]:
        ids: list[str] = []
        if knowledge_item_id is not None:
            ids.append(knowledge_item_id)
        if knowledge_item_ids:
            ids.extend(knowledge_item_ids)
        if not ids:
            return []

        placeholders = ", ".join(self._placeholder() for _ in ids)
        rows = self._select(
            f"""
            SELECT c.*
            FROM knowledge_chunks c
            JOIN knowledge_items i ON i.knowledge_item_id = c.knowledge_item_id
            WHERE c.knowledge_item_id IN ({placeholders})
              AND i.is_enabled = {self._placeholder()}
              AND i.index_status = {self._placeholder()}
            ORDER BY c.knowledge_item_id ASC, c.order_index ASC
            """,
            [*ids, True, "indexed"],
        )
        chunks = [self._row_to_chunk(row) for row in rows]
        if knowledge_item_id is not None and not knowledge_item_ids:
            return chunks

        order_map = {item_id: index for index, item_id in enumerate(ids)}
        chunks.sort(key=lambda chunk: (order_map.get(chunk.knowledge_item_id, len(order_map)), chunk.order_index))
        return chunks

    def mark_item_stage(
        self,
        *,
        knowledge_item_id: str,
        parse_status: KnowledgeParseStatus | None = None,
        ingest_status: KnowledgeIngestStatus | None = None,
        index_status: KnowledgeIndexStatus | None = None,
        last_error: str | None = None,
        last_indexed_at: datetime | None = None,
    ) -> None:
        item = self.get_item(knowledge_item_id)
        if item is None:
            return
        self._execute(
            """
            UPDATE knowledge_items
            SET parse_status = {p}, ingest_status = {p}, index_status = {p}, last_error = {p},
                updated_at = {p}, last_indexed_at = {p}
            WHERE knowledge_item_id = {p}
            """,
            [
                parse_status or item.parse_status,
                ingest_status or item.ingest_status,
                index_status or item.index_status,
                last_error,
                self.utcnow().isoformat(),
                (last_indexed_at or item.last_indexed_at).isoformat() if (last_indexed_at or item.last_indexed_at) else None,
                knowledge_item_id,
            ],
        )

    def create_task(self, task: KnowledgeTask | dict[str, Any] | None = None, **kwargs: Any) -> KnowledgeTask:
        payload: dict[str, Any]
        if isinstance(task, KnowledgeTask):
            model = task
        else:
            payload = dict(task or {})
            payload.update(kwargs)
            now = self.utcnow()
            payload.setdefault("task_id", f"ktask-{uuid4().hex[:12]}")
            payload.setdefault("status", "queued")
            payload.setdefault("summary", None)
            payload.setdefault("error_detail", None)
            payload.setdefault("attempt_count", 0)
            payload.setdefault("created_at", now)
            payload.setdefault("started_at", None)
            payload.setdefault("finished_at", None)
            model = KnowledgeTask.model_validate(payload)
        self._execute(
            """
            INSERT INTO knowledge_tasks (
                task_id, knowledge_item_id, owner_user_id, requested_by_user_id, task_type, status,
                summary, error_detail, attempt_count, created_at, started_at, finished_at
            )
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            [
                model.task_id,
                model.knowledge_item_id,
                model.owner_user_id,
                model.requested_by_user_id,
                model.task_type,
                model.status,
                model.summary,
                model.error_detail,
                model.attempt_count,
                model.created_at.isoformat(),
                model.started_at.isoformat() if model.started_at else None,
                model.finished_at.isoformat() if model.finished_at else None,
            ],
        )
        refreshed = self.get_task(model.task_id)
        if refreshed is None:
            raise RuntimeError("knowledge task creation failed")
        return refreshed

    def get_task(self, task_id: str) -> KnowledgeTask | None:
        rows = self._select("SELECT * FROM knowledge_tasks WHERE task_id = {p}", [task_id])
        return self._row_to_task(rows[0]) if rows else None

    def list_tasks(
        self,
        *,
        owner_user_id: str | None = None,
        include_shared: bool = True,
        status: KnowledgeTaskStatus | None = None,
        task_type: KnowledgeTaskType | None = None,
        knowledge_item_id: str | None = None,
        requested_by_user_id: str | None = None,
    ) -> list[KnowledgeTask]:
        clauses: list[str] = []
        params: list[object] = []
        if owner_user_id is not None:
            clauses.append(f"owner_user_id = {self._placeholder()}")
            params.append(owner_user_id)
        elif not include_shared:
            clauses.append("owner_user_id IS NOT NULL")
        if status is not None:
            clauses.append(f"status = {self._placeholder()}")
            params.append(status)
        if task_type is not None:
            clauses.append(f"task_type = {self._placeholder()}")
            params.append(task_type)
        if knowledge_item_id is not None:
            clauses.append(f"knowledge_item_id = {self._placeholder()}")
            params.append(knowledge_item_id)
        if requested_by_user_id is not None:
            clauses.append(f"requested_by_user_id = {self._placeholder()}")
            params.append(requested_by_user_id)
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._select(f"SELECT * FROM knowledge_tasks{where_sql} ORDER BY created_at DESC, task_seq DESC", params)
        return [self._row_to_task(row) for row in rows]

    def list_tasks_for_user(self, *, owner_user_id: str, filters: KnowledgeTaskListFilters | None = None) -> list[KnowledgeTask]:
        filters = filters or KnowledgeTaskListFilters()
        return self.list_tasks(
            owner_user_id=owner_user_id,
            status=filters.status,
            task_type=filters.task_type,
            knowledge_item_id=filters.knowledge_item_id,
            requested_by_user_id=filters.requested_by_user_id,
        )

    def list_admin_tasks(self, *, filters: KnowledgeTaskListFilters | None = None) -> list[KnowledgeTask]:
        filters = filters or KnowledgeTaskListFilters()
        return self.list_tasks(
            owner_user_id=filters.owner_user_id,
            include_shared=True,
            status=filters.status,
            task_type=filters.task_type,
            knowledge_item_id=filters.knowledge_item_id,
            requested_by_user_id=filters.requested_by_user_id,
        )

    def claim_next_task(self) -> KnowledgeTask | None:
        rows = self._select(
            "SELECT * FROM knowledge_tasks WHERE status = {p} ORDER BY created_at ASC, task_seq ASC LIMIT 1",
            ["queued"],
        )
        if not rows:
            return None
        task = self._row_to_task(rows[0])
        self.update_task_status(
            task_id=task.task_id,
            status="running",
            started_at=self.utcnow(),
            summary=task.summary or "知识任务正在执行。",
        )
        self._execute(
            "UPDATE knowledge_tasks SET attempt_count = attempt_count + 1 WHERE task_id = {p}",
            [task.task_id],
        )
        return self.get_task(task.task_id)

    def reset_running_tasks(self) -> None:
        self._execute(
            "UPDATE knowledge_tasks SET status = {p}, summary = {p}, started_at = NULL, finished_at = NULL WHERE status = {p}",
            ["queued", "应用重启后重新排队。", "running"],
        )

    def update_task_status(
        self,
        *,
        task_id: str,
        status: KnowledgeTaskStatus,
        summary: str | None = None,
        error_detail: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> KnowledgeTask | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        self._execute(
            """
            UPDATE knowledge_tasks
            SET status = {p},
                summary = {p},
                error_detail = {p},
                started_at = {p},
                finished_at = {p}
            WHERE task_id = {p}
            """,
            [
                status,
                summary if summary is not None else task.summary,
                error_detail,
                started_at.isoformat() if started_at else task.started_at.isoformat() if task.started_at else None,
                finished_at.isoformat() if finished_at else task.finished_at.isoformat() if task.finished_at else None,
                task_id,
            ],
        )
        return self.get_task(task_id)

    def finish_task(self, *, task_id: str, status: KnowledgeTaskStatus, summary: str | None, error_detail: str | None) -> KnowledgeTask | None:
        return self.update_task_status(
            task_id=task_id,
            status=status,
            summary=summary,
            error_detail=error_detail,
            finished_at=self.utcnow(),
        )

    def save_workflow_run(self, run: WorkflowRun) -> WorkflowRun:
        existing = self.get_workflow_run(workflow_id=run.workflow_id)
        params = [
            run.workflow_id,
            run.workflow_type,
            run.status,
            run.current_node,
            run.knowledge_item_id,
            run.tenant_id,
            run.owner_user_id,
            run.visibility,
            run.created_by,
            run.created_at.isoformat(),
            run.updated_at.isoformat(),
            run.error_message,
            json.dumps(run.metadata, ensure_ascii=False),
        ]
        if existing is None:
            self._execute(
                """
                INSERT INTO workflow_runs (
                    workflow_id, workflow_type, status, current_node, knowledge_item_id,
                    tenant_id, owner_user_id, visibility, created_by, created_at, updated_at,
                    error_message, metadata_json
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                params,
            )
        else:
            self._execute(
                """
                UPDATE workflow_runs
                SET workflow_type = {p}, status = {p}, current_node = {p}, knowledge_item_id = {p},
                    tenant_id = {p}, owner_user_id = {p}, visibility = {p}, created_by = {p},
                    created_at = {p}, updated_at = {p}, error_message = {p}, metadata_json = {p}
                WHERE workflow_id = {p}
                """,
                [*params[1:], run.workflow_id],
            )
        for node in run.nodes:
            self.save_workflow_node(node.model_copy(update={"workflow_id": run.workflow_id}))
        for checkpoint in run.checkpoints:
            self.save_execution_checkpoint(checkpoint)
        refreshed = self.get_workflow_run(workflow_id=run.workflow_id)
        if refreshed is None:
            raise RuntimeError("workflow run refresh failed")
        return refreshed

    def save_workflow_node(self, node: WorkflowNode) -> WorkflowNode:
        if node.workflow_id is None:
            raise ValueError("workflow node requires workflow_id")
        existing = self._select(
            "SELECT * FROM workflow_nodes WHERE workflow_id = {p} AND node_id = {p}",
            [node.workflow_id, node.node_id],
        )
        params = [
            node.workflow_id,
            node.node_id,
            node.node_type,
            node.status,
            node.input_ref,
            node.output_ref,
            node.started_at.isoformat() if node.started_at else None,
            node.finished_at.isoformat() if node.finished_at else None,
            node.error_message,
            node.retry_count,
            json.dumps(node.depends_on, ensure_ascii=False),
            json.dumps(node.metadata, ensure_ascii=False),
        ]
        if not existing:
            self._execute(
                """
                INSERT INTO workflow_nodes (
                    workflow_id, node_id, node_type, status, input_ref, output_ref,
                    started_at, finished_at, error_message, retry_count, depends_on_json, metadata_json
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                params,
            )
        else:
            self._execute(
                """
                UPDATE workflow_nodes
                SET node_type = {p}, status = {p}, input_ref = {p}, output_ref = {p},
                    started_at = {p}, finished_at = {p}, error_message = {p}, retry_count = {p},
                    depends_on_json = {p}, metadata_json = {p}
                WHERE workflow_id = {p} AND node_id = {p}
                """,
                [*params[2:], node.workflow_id, node.node_id],
            )
        refreshed = self._select(
            "SELECT * FROM workflow_nodes WHERE workflow_id = {p} AND node_id = {p}",
            [node.workflow_id, node.node_id],
        )
        return self._row_to_workflow_node(refreshed[0])

    def save_execution_checkpoint(self, checkpoint: ExecutionCheckpoint) -> ExecutionCheckpoint:
        existing = self._select(
            "SELECT * FROM execution_checkpoints WHERE checkpoint_id = {p}",
            [checkpoint.checkpoint_id],
        )
        if existing:
            return self._row_to_execution_checkpoint(existing[0])
        self._execute(
            """
            INSERT INTO execution_checkpoints (checkpoint_id, workflow_id, node_id, status, state_json, created_at)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p})
            """,
            [
                checkpoint.checkpoint_id,
                checkpoint.workflow_id,
                checkpoint.node_id,
                checkpoint.status,
                json.dumps(checkpoint.state_json, ensure_ascii=False),
                checkpoint.created_at.isoformat(),
            ],
        )
        refreshed = self._select(
            "SELECT * FROM execution_checkpoints WHERE checkpoint_id = {p}",
            [checkpoint.checkpoint_id],
        )
        return self._row_to_execution_checkpoint(refreshed[0])

    def get_workflow_run(self, *, workflow_id: str) -> WorkflowRun | None:
        rows = self._select("SELECT * FROM workflow_runs WHERE workflow_id = {p}", [workflow_id])
        if not rows:
            return None
        run = self._row_to_workflow_run(rows[0])
        run.nodes = self.list_workflow_nodes(workflow_id=workflow_id)
        run.checkpoints = self.list_execution_checkpoints(workflow_id=workflow_id)
        return run

    def get_latest_workflow_run(self, *, knowledge_item_id: str) -> WorkflowRun | None:
        rows = self._select(
            "SELECT * FROM workflow_runs WHERE knowledge_item_id = {p} ORDER BY updated_at DESC, workflow_seq DESC LIMIT 1",
            [knowledge_item_id],
        )
        if not rows:
            return None
        return self.get_workflow_run(workflow_id=str(rows[0]["workflow_id"]))

    def list_workflow_nodes(self, *, workflow_id: str) -> list[WorkflowNode]:
        rows = self._select(
            "SELECT * FROM workflow_nodes WHERE workflow_id = {p} ORDER BY node_seq ASC",
            [workflow_id],
        )
        return [self._row_to_workflow_node(row) for row in rows]

    def list_execution_checkpoints(self, *, workflow_id: str) -> list[ExecutionCheckpoint]:
        rows = self._select(
            "SELECT * FROM execution_checkpoints WHERE workflow_id = {p} ORDER BY checkpoint_seq ASC",
            [workflow_id],
        )
        return [self._row_to_execution_checkpoint(row) for row in rows]

    def requeue_task(self, *, task_id: str) -> KnowledgeTask | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        self._execute(
            """
            UPDATE knowledge_tasks
            SET status = {p}, summary = {p}, error_detail = NULL, started_at = NULL, finished_at = NULL
            WHERE task_id = {p}
            """,
            ["queued", "已重新排队。", task_id],
        )
        return self.get_task(task_id)

    def list_uploaded_files(self, *, owner_user_id: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[object] = []
        if owner_user_id is not None:
            clauses.append(f"owner_user_id = {self._placeholder()}")
            params.append(owner_user_id)
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return [dict(row) for row in self._select(f"SELECT * FROM files{where_sql} ORDER BY file_seq DESC", params)]

    def replace_session_knowledge_items(
        self,
        *,
        session_id: str,
        knowledge_item_ids: list[str],
        attached_at: str,
    ) -> None:
        unique_ids = list(dict.fromkeys(knowledge_item_ids))
        self._execute("DELETE FROM session_knowledge_items WHERE session_id = {p}", [session_id])
        for knowledge_item_id in unique_ids:
            self._execute(
                """
                INSERT INTO session_knowledge_items (session_id, knowledge_item_id, attached_at)
                VALUES ({p}, {p}, {p})
                """,
                [session_id, knowledge_item_id, attached_at],
            )
        self._execute("UPDATE sessions SET updated_at = {p} WHERE session_id = {p}", [attached_at, session_id])

    def list_session_knowledge_item_ids(self, *, session_id: str) -> list[str]:
        rows = self._select(
            "SELECT knowledge_item_id FROM session_knowledge_items WHERE session_id = {p} ORDER BY attachment_seq ASC",
            [session_id],
        )
        return [row["knowledge_item_id"] for row in rows]

    def list_session_knowledge_items(self, *, session_id: str) -> list[KnowledgeItem]:
        item_ids = self.list_session_knowledge_item_ids(session_id=session_id)
        return self.list_items(knowledge_item_ids=item_ids)

    def get_item_detail(self, *, knowledge_item_id: str) -> KnowledgeItemDetailResponse | None:
        item = self.get_item(knowledge_item_id)
        if item is None:
            return None
        return KnowledgeItemDetailResponse(
            item=item,
            chunks=self.list_chunks(knowledge_item_id=knowledge_item_id),
            tasks=self.list_tasks(knowledge_item_id=knowledge_item_id),
        )

    def list_my_uploads(self, *, owner_user_id: str) -> list[MyUploadEntry]:
        rows = self._select(
            """
            SELECT
                f.file_id,
                f.session_id,
                f.filename,
                f.size,
                f.mime_type,
                f.stored_at,
                f.storage_path,
                i.knowledge_item_id,
                i.parse_status,
                i.ingest_status,
                i.index_status,
                t.status AS latest_task_status
            FROM files f
            LEFT JOIN knowledge_items i ON i.file_id = f.file_id
            LEFT JOIN knowledge_tasks t ON t.task_id = (
                SELECT task_id
                FROM knowledge_tasks
                WHERE knowledge_item_id = i.knowledge_item_id
                ORDER BY created_at DESC, task_seq DESC
                LIMIT 1
            )
            WHERE f.owner_user_id = {p}
            ORDER BY f.file_seq DESC
            """,
            [owner_user_id],
        )
        entries: list[MyUploadEntry] = []
        for row in rows:
            payload = dict(row)
            payload["latest_task_status"] = payload.get("latest_task_status")
            entries.append(MyUploadEntry.model_validate(payload))
        return entries

    def _decorate_item(self, item: KnowledgeItem) -> KnowledgeItem:
        item.chunk_count = self._count_rows(
            "SELECT COUNT(*) AS count FROM knowledge_chunks WHERE knowledge_item_id = {p}",
            [item.knowledge_item_id],
        )
        item.task_count = self._count_rows(
            "SELECT COUNT(*) AS count FROM knowledge_tasks WHERE knowledge_item_id = {p}",
            [item.knowledge_item_id],
        )
        latest_task = self._select(
            "SELECT status FROM knowledge_tasks WHERE knowledge_item_id = {p} ORDER BY created_at DESC, task_seq DESC LIMIT 1",
            [item.knowledge_item_id],
        )
        item.latest_task_status = latest_task[0]["status"] if latest_task else None
        return item

    @staticmethod
    def _row_to_item(row) -> KnowledgeItem:
        payload = dict(row)
        payload["is_enabled"] = bool(payload.get("is_enabled", True))
        payload["session_attachable"] = bool(payload.get("session_attachable", True))
        return KnowledgeItem.model_validate(payload)

    @staticmethod
    def _row_to_chunk(row) -> KnowledgeChunk:
        payload = dict(row)
        payload["metadata"] = _parse_json_object(payload.pop("metadata_json", None))
        return KnowledgeChunk.model_validate(payload)

    @staticmethod
    def _row_to_task(row) -> KnowledgeTask:
        return KnowledgeTask.model_validate(dict(row))

    @staticmethod
    def _row_to_workflow_run(row) -> WorkflowRun:
        from app.rag.workflow import WorkflowRun

        payload = dict(row)
        payload["metadata"] = _parse_json_object(payload.pop("metadata_json", None))
        return WorkflowRun.model_validate(payload)

    @staticmethod
    def _row_to_workflow_node(row) -> WorkflowNode:
        from app.rag.workflow import WorkflowNode

        payload = dict(row)
        payload["depends_on"] = _parse_json_list(payload.pop("depends_on_json", None))
        payload["metadata"] = _parse_json_object(payload.pop("metadata_json", None))
        return WorkflowNode.model_validate(payload)

    @staticmethod
    def _row_to_execution_checkpoint(row) -> ExecutionCheckpoint:
        from app.rag.workflow import ExecutionCheckpoint

        payload = dict(row)
        payload["state_json"] = _parse_json_object(payload.get("state_json"))
        return ExecutionCheckpoint.model_validate(payload)

    def _select(self, query: str, params: list[object]) -> list[dict[str, Any]]:
        compiled = self._compile(query)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(compiled, tuple(params))
                    return [dict(row) for row in cursor.fetchall()]
            rows = connection.execute(compiled, tuple(params)).fetchall()
            return [dict(row) for row in rows]

    def _execute(self, query: str, params: list[object]) -> None:
        compiled = self._compile(query)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(compiled, tuple(params))
            else:
                connection.execute(compiled, tuple(params))

    def _count_rows(self, query: str, params: list[object]) -> int:
        rows = self._select(query, params)
        if not rows:
            return 0
        value = rows[0].get("count")
        return int(value or 0)

    def _compile(self, query: str) -> str:
        return query.replace("{p}", self._placeholder())

    def _placeholder(self) -> str:
        return "%s" if self.backend_kind == "postgresql" else "?"


class BaseKnowledgeStore(KnowledgeStore):
    pass


if TYPE_CHECKING:
    from app.rag.workflow import ExecutionCheckpoint, WorkflowNode, WorkflowRun


def build_knowledge_store(*, database_url: str | None = None, sqlite_db_path: Path | str | None = None) -> BaseKnowledgeStore:
    return BaseKnowledgeStore(database_url=database_url, sqlite_db_path=sqlite_db_path)


def _parse_json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if not isinstance(value, str) or not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []


@lru_cache(maxsize=1)
def get_default_knowledge_store() -> BaseKnowledgeStore:
    settings = get_settings()
    return build_knowledge_store(database_url=settings.database_url)
