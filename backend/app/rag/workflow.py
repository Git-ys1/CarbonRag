from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


GovernanceVisibility = Literal["public", "tenant", "private", "demo"]
WorkflowRunStatus = Literal["pending", "running", "completed", "failed", "skipped"]
WorkflowNodeStatus = Literal["pending", "running", "completed", "failed", "skipped", "succeeded"]
WorkflowNodeType = Literal[
    "upload_received",
    "crawl_source",
    "stage_crawled_document",
    "parse_document",
    "normalize_policy_metadata",
    "build_blocks",
    "build_chunks",
    "build_embeddings",
    "upsert_vector_index",
    "build_graph_candidates",
    "index_completed",
    "chunk_document",
    "upsert_vectors",
    "build_graph",
    "mark_indexed",
]


def workflow_utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    node_id: str
    workflow_id: str | None = None
    node_type: WorkflowNodeType
    status: WorkflowNodeStatus = "pending"
    input_ref: str | None = None
    output_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = Field(default=0, ge=0)
    depends_on: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_name(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "node_type" not in data and "name" in data:
            data["node_type"] = data["name"]
        if data.get("status") == "succeeded":
            data["status"] = "completed"
        return data

    @property
    def name(self) -> WorkflowNodeType:
        return self.node_type


class ExecutionCheckpoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    checkpoint_id: str = Field(default_factory=lambda: f"rag-checkpoint-{uuid4().hex[:12]}")
    workflow_id: str
    node_id: str
    state_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=workflow_utcnow)
    status: WorkflowNodeStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "workflow_id" not in data and "workflow_run_id" in data:
            data["workflow_id"] = data["workflow_run_id"]
        if "state_json" not in data and "payload" in data:
            data["state_json"] = data["payload"]
        if data.get("status") == "succeeded":
            data["status"] = "completed"
        return data

    @property
    def workflow_run_id(self) -> str:
        return self.workflow_id

    @property
    def payload(self) -> dict[str, Any]:
        return self.state_json


class WorkflowRun(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workflow_id: str = Field(default_factory=lambda: f"rag-workflow-{uuid4().hex[:12]}")
    workflow_type: str = "rag_ingest"
    status: WorkflowRunStatus = "pending"
    current_node: str | None = None
    created_at: datetime = Field(default_factory=workflow_utcnow)
    updated_at: datetime = Field(default_factory=workflow_utcnow)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    nodes: list[WorkflowNode] = Field(default_factory=list)
    checkpoints: list[ExecutionCheckpoint] = Field(default_factory=list)
    knowledge_item_id: str | None = None
    tenant_id: str | None = None
    owner_user_id: str | None = None
    visibility: GovernanceVisibility = "private"
    created_by: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "workflow_id" not in data and "workflow_run_id" in data:
            data["workflow_id"] = data["workflow_run_id"]
        if data.get("status") == "succeeded":
            data["status"] = "completed"
        return data

    @property
    def workflow_run_id(self) -> str:
        return self.workflow_id

    def node(self, node_id: str) -> WorkflowNode | None:
        return next((node for node in self.nodes if node.node_id == node_id), None)


class WorkflowRecorder:
    def __init__(self, run: WorkflowRun) -> None:
        self.run = run

    def start_run(self) -> WorkflowRun:
        self.run.status = "running"
        self.run.updated_at = workflow_utcnow()
        return self.run

    def start_node(self, node_id: str, *, input_ref: str | None = None, state: dict[str, Any] | None = None) -> WorkflowNode:
        node = self._require_node(node_id)
        now = workflow_utcnow()
        node.status = "running"
        node.started_at = node.started_at or now
        node.finished_at = None
        node.error_message = None
        node.input_ref = input_ref if input_ref is not None else node.input_ref
        self.run.status = "running"
        self.run.current_node = node_id
        self.run.updated_at = now
        self.checkpoint(node_id=node_id, status="running", state=state or {})
        return node

    def complete_node(
        self,
        node_id: str,
        *,
        output_ref: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> WorkflowNode:
        node = self._require_node(node_id)
        now = workflow_utcnow()
        node.status = "completed"
        node.output_ref = output_ref if output_ref is not None else node.output_ref
        node.finished_at = now
        node.error_message = None
        self.run.current_node = node_id
        self.run.updated_at = now
        self.checkpoint(node_id=node_id, status="completed", state=state or {})
        return node

    def skip_node(self, node_id: str, *, reason: str, state: dict[str, Any] | None = None) -> WorkflowNode:
        node = self._require_node(node_id)
        now = workflow_utcnow()
        node.status = "skipped"
        node.finished_at = now
        node.error_message = reason
        self.run.current_node = node_id
        self.run.updated_at = now
        self.checkpoint(node_id=node_id, status="skipped", state={"reason": reason, **(state or {})})
        return node

    def fail_node(self, node_id: str, *, error_message: str, state: dict[str, Any] | None = None) -> WorkflowNode:
        node = self._require_node(node_id)
        now = workflow_utcnow()
        node.status = "failed"
        node.finished_at = now
        node.error_message = error_message
        self.run.status = "failed"
        self.run.current_node = node_id
        self.run.error_message = error_message
        self.run.updated_at = now
        self.checkpoint(node_id=node_id, status="failed", state={"error_message": error_message, **(state or {})})
        return node

    def complete_run(self, *, state: dict[str, Any] | None = None) -> WorkflowRun:
        self.run.status = "completed"
        self.run.current_node = "index_completed"
        self.run.error_message = None
        self.run.updated_at = workflow_utcnow()
        if state is not None:
            self.run.metadata.update(state)
        return self.run

    def checkpoint(
        self,
        *,
        node_id: str,
        status: WorkflowNodeStatus | None = None,
        state: dict[str, Any] | None = None,
    ) -> ExecutionCheckpoint:
        checkpoint = ExecutionCheckpoint(
            workflow_id=self.run.workflow_id,
            node_id=node_id,
            status=status,
            state_json=state or {},
        )
        self.run.checkpoints.append(checkpoint)
        return checkpoint

    def _require_node(self, node_id: str) -> WorkflowNode:
        node = self.run.node(node_id)
        if node is None:
            raise KeyError(f"workflow node not found: {node_id}")
        return node


def build_rag_ingest_workflow(
    *,
    knowledge_item_id: str | None = None,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    visibility: GovernanceVisibility = "private",
    created_by: str | None = None,
    workflow_type: str = "rag_ingest",
    metadata: dict[str, Any] | None = None,
) -> WorkflowRun:
    workflow_id = f"rag-workflow-{uuid4().hex[:12]}"
    node_specs: list[tuple[str, WorkflowNodeType, list[str]]] = [
        ("upload_received", "upload_received", []),
        ("parse_document", "parse_document", ["upload_received"]),
        ("build_blocks", "build_blocks", ["parse_document"]),
        ("build_chunks", "build_chunks", ["build_blocks"]),
        ("build_embeddings", "build_embeddings", ["build_chunks"]),
        ("upsert_vector_index", "upsert_vector_index", ["build_embeddings"]),
        ("build_graph_candidates", "build_graph_candidates", ["build_chunks"]),
        ("index_completed", "index_completed", ["upsert_vector_index", "build_graph_candidates"]),
    ]
    nodes = [
        WorkflowNode(
            workflow_id=workflow_id,
            node_id=node_id,
            node_type=node_type,
            depends_on=depends_on,
        )
        for node_id, node_type, depends_on in node_specs
    ]
    return WorkflowRun(
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        knowledge_item_id=knowledge_item_id,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        visibility=visibility,
        created_by=created_by,
        nodes=nodes,
        metadata=metadata or {},
    )


def build_policy_ingest_workflow(
    *,
    knowledge_item_id: str | None = None,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    visibility: GovernanceVisibility = "public",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkflowRun:
    workflow_id = f"rag-workflow-{uuid4().hex[:12]}"
    node_specs: list[tuple[str, WorkflowNodeType, list[str]]] = [
        ("crawl_source", "crawl_source", []),
        ("stage_crawled_document", "stage_crawled_document", ["crawl_source"]),
        ("parse_document", "parse_document", ["stage_crawled_document"]),
        ("normalize_policy_metadata", "normalize_policy_metadata", ["parse_document"]),
        ("build_chunks", "build_chunks", ["normalize_policy_metadata"]),
        ("upsert_vector_index", "upsert_vector_index", ["build_chunks"]),
        ("index_completed", "index_completed", ["upsert_vector_index"]),
    ]
    nodes = [
        WorkflowNode(
            workflow_id=workflow_id,
            node_id=node_id,
            node_type=node_type,
            depends_on=depends_on,
        )
        for node_id, node_type, depends_on in node_specs
    ]
    return WorkflowRun(
        workflow_id=workflow_id,
        workflow_type="policy_ingest",
        knowledge_item_id=knowledge_item_id,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        visibility=visibility,
        created_by=created_by,
        nodes=nodes,
        metadata=metadata or {},
    )


def build_default_indexing_workflow(*, knowledge_item_id: str | None = None) -> WorkflowRun:
    workflow_id = f"rag-workflow-{uuid4().hex[:12]}"
    nodes = [
        WorkflowNode(workflow_id=workflow_id, node_id="parse", node_type="parse_document"),
        WorkflowNode(workflow_id=workflow_id, node_id="chunk", node_type="chunk_document", depends_on=["parse"]),
        WorkflowNode(workflow_id=workflow_id, node_id="vector", node_type="upsert_vectors", depends_on=["chunk"]),
        WorkflowNode(workflow_id=workflow_id, node_id="graph", node_type="build_graph", depends_on=["chunk"]),
        WorkflowNode(workflow_id=workflow_id, node_id="indexed", node_type="mark_indexed", depends_on=["vector", "graph"]),
    ]
    return WorkflowRun(
        workflow_id=workflow_id,
        workflow_type="legacy_indexing",
        knowledge_item_id=knowledge_item_id,
        nodes=nodes,
    )
