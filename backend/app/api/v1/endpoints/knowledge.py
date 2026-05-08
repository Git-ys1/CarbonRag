from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_authenticated_user
from app.auth.schemas import AuthenticatedUser
from app.knowledge import get_knowledge_service
from app.knowledge.schemas import KnowledgeItemDetail, KnowledgeItemSummary, KnowledgeTaskSummary
from app.private_samples.catalog import refresh_private_sample_catalog
from app.rag.service import get_rag_engine_service
from app.retrieval.mixed_retriever import get_mixed_scope_retriever
from app.retrieval.private_retriever import get_private_sample_retriever
from app.session.schemas import ReplaceAttachedPrivateSamplesRequest, SessionDetail

router = APIRouter()


def _sync_user_knowledge(owner_user_id: str) -> None:
    service = get_knowledge_service()
    refresh_private_sample_catalog()
    service.sync_uploaded_files(owner_user_id=owner_user_id)
    try:
        service.run_queued_tasks()
    except Exception:
        pass
    get_private_sample_retriever.cache_clear()
    get_mixed_scope_retriever.cache_clear()
    get_rag_engine_service.cache_clear()


def _get_bound_session_service():
    from app.api.v1.endpoints.sessions import get_session_service

    return get_session_service()


@router.get("/knowledge-items", response_model=list[KnowledgeItemSummary])
def list_knowledge_items(
    library_scope: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    parse_status: str | None = Query(default=None),
    ingest_status: str | None = Query(default=None),
    index_status: str | None = Query(default=None),
    session_attachable: bool | None = Query(default=None),
    is_enabled: bool | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> list[KnowledgeItemSummary]:
    _sync_user_knowledge(current_user.user_id)
    items = get_knowledge_service().list_visible_items(
        owner_user_id=current_user.user_id,
        library_scope=library_scope,
        source_type=source_type,
        parse_status=parse_status,
        ingest_status=ingest_status,
        index_status=index_status,
        session_attachable=session_attachable,
        is_enabled=is_enabled,
    )
    return [KnowledgeItemSummary.model_validate(item.model_dump()) for item in items]


@router.get("/knowledge-items/{knowledge_item_id}", response_model=KnowledgeItemDetail)
def get_knowledge_item(
    knowledge_item_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> KnowledgeItemDetail:
    service = get_knowledge_service()
    visible_items = service.list_visible_items(
        owner_user_id=current_user.user_id,
        knowledge_item_ids=[knowledge_item_id],
    )
    item = visible_items[0] if visible_items else None
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found.")
    return KnowledgeItemDetail.model_validate(item.model_dump())


@router.get("/knowledge-tasks", response_model=list[KnowledgeTaskSummary])
def list_knowledge_tasks(
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> list[KnowledgeTaskSummary]:
    _sync_user_knowledge(current_user.user_id)
    tasks = get_knowledge_service().list_tasks(
        owner_user_id=current_user.user_id,
        include_shared=True,
        status=status,
        task_type=task_type,
    )
    return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in tasks]


@router.post("/knowledge-tasks/{task_id}/retry", response_model=KnowledgeTaskSummary)
def retry_knowledge_task(
    task_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> KnowledgeTaskSummary:
    service = get_knowledge_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Knowledge task not found.")
    if task.owner_user_id not in {None, current_user.user_id}:
        raise HTTPException(status_code=404, detail="Knowledge task not found.")
    try:
        retried = service.retry_task(task_id=task_id, requested_by_user_id=current_user.user_id)
        service.run_queued_tasks()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail="Knowledge task not found.")
    latest = service.get_task(retried.task_id) or retried
    return KnowledgeTaskSummary.model_validate(latest.model_dump())


@router.put("/sessions/{session_id}/knowledge-items", response_model=SessionDetail)
def replace_session_knowledge_items(
    session_id: str,
    payload: ReplaceAttachedPrivateSamplesRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> SessionDetail:
    session_service = _get_bound_session_service()
    knowledge_item_ids = payload.knowledge_item_ids or payload.doc_ids
    try:
        session_service.replace_attached_knowledge_items(
            owner_user_id=current_user.user_id,
            session_id=session_id,
            knowledge_item_ids=knowledge_item_ids,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    session = session_service.get_session(owner_user_id=current_user.user_id, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session
