from fastapi import APIRouter, Depends, HTTPException

from app.admin.schemas import (
    AdminFeedbackOverview,
    AdminPrivateSampleItem,
    AdminSystemStatus,
    AdminUserSummary,
    KnowledgeRefreshTask,
    TriggerKnowledgeRefreshRequest,
    UpdateAdminPrivateSampleRequest,
    UpdateAdminUserRequest,
)
from app.admin.service import get_admin_service
from app.auth.dependencies import require_admin
from app.auth.schemas import AuthenticatedUser, ResetPasswordResponse
from app.knowledge import get_knowledge_service
from app.knowledge.schemas import KnowledgeItemSummary, KnowledgeTaskSummary
from app.private_samples.catalog import refresh_private_sample_catalog
from app.rag.service import get_rag_engine_service
from app.retrieval.mixed_retriever import get_mixed_scope_retriever
from app.retrieval.private_retriever import get_private_sample_retriever

router = APIRouter(prefix="/admin")


def _clear_private_retrieval_caches() -> None:
    get_private_sample_retriever.cache_clear()
    get_mixed_scope_retriever.cache_clear()
    get_rag_engine_service.cache_clear()


@router.get("/system/status", response_model=AdminSystemStatus)
def get_admin_system_status(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> AdminSystemStatus:
    del current_user
    return get_admin_service().get_system_status()


@router.get("/users", response_model=list[AdminUserSummary])
def list_admin_users(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> list[AdminUserSummary]:
    del current_user
    return get_admin_service().list_users()


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
def update_admin_user(
    user_id: str,
    payload: UpdateAdminUserRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
) -> AdminUserSummary:
    del current_user
    try:
        get_admin_service().update_user(user_id=user_id, role=payload.role, is_active=payload.is_active)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found.")
    return next(item for item in get_admin_service().list_users() if item.user_id == user_id)


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
def reset_admin_user_password(
    user_id: str,
    current_user: AuthenticatedUser = Depends(require_admin),
) -> ResetPasswordResponse:
    del current_user
    try:
        temporary_password = get_admin_service().reset_password(user_id=user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found.")
    return ResetPasswordResponse(temporary_password=temporary_password)


@router.get("/feedback/overview", response_model=AdminFeedbackOverview)
def get_admin_feedback_overview(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> AdminFeedbackOverview:
    del current_user
    return get_admin_service().get_feedback_overview()


@router.get("/private-samples", response_model=list[AdminPrivateSampleItem])
def list_admin_private_samples(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> list[AdminPrivateSampleItem]:
    del current_user
    return get_admin_service().list_private_samples()


@router.patch("/private-samples/{doc_id}", response_model=AdminPrivateSampleItem)
def update_admin_private_sample(
    doc_id: str,
    payload: UpdateAdminPrivateSampleRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
) -> AdminPrivateSampleItem:
    try:
        return get_admin_service().update_private_sample(
            doc_id=doc_id,
            is_enabled=payload.is_enabled,
            session_attachable=payload.session_attachable,
            updated_by_user_id=current_user.user_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Private sample not found.")
    finally:
        _clear_private_retrieval_caches()


@router.get("/knowledge-refresh-tasks", response_model=list[KnowledgeRefreshTask])
def list_knowledge_refresh_tasks(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> list[KnowledgeRefreshTask]:
    del current_user
    return get_admin_service().list_knowledge_refresh_tasks()


@router.post("/knowledge-refresh-tasks", response_model=KnowledgeRefreshTask)
def trigger_knowledge_refresh_task(
    payload: TriggerKnowledgeRefreshRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
) -> KnowledgeRefreshTask:
    try:
        return get_admin_service().trigger_knowledge_refresh(
            scope=payload.scope,
            requested_by_user_id=current_user.user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/knowledge-items", response_model=list[KnowledgeItemSummary])
def list_admin_knowledge_items(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> list[KnowledgeItemSummary]:
    del current_user
    service = get_knowledge_service()
    refresh_private_sample_catalog()
    try:
        service.run_queued_tasks()
    except Exception:
        pass
    _clear_private_retrieval_caches()
    items = service.list_visible_items(owner_user_id=None)
    return [KnowledgeItemSummary.model_validate(item.model_dump()) for item in items]


@router.patch("/knowledge-items/{knowledge_item_id}", response_model=KnowledgeItemSummary)
def update_admin_knowledge_item(
    knowledge_item_id: str,
    payload: UpdateAdminPrivateSampleRequest,
    current_user: AuthenticatedUser = Depends(require_admin),
) -> KnowledgeItemSummary:
    del current_user
    service = get_knowledge_service()
    item = service.store.get_item(knowledge_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found.")
    updated_item = service.store.upsert_item(
        {
            **item.model_dump(mode="python"),
            "is_enabled": payload.is_enabled,
            "session_attachable": payload.session_attachable,
            "updated_at": get_admin_service()._utcnow().isoformat(),
        }
    )
    _clear_private_retrieval_caches()
    return KnowledgeItemSummary.model_validate(updated_item.model_dump())


@router.get("/knowledge-tasks", response_model=list[KnowledgeTaskSummary])
def list_admin_knowledge_tasks(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> list[KnowledgeTaskSummary]:
    del current_user
    tasks = get_knowledge_service().list_tasks(owner_user_id=None, include_shared=True)
    return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in tasks]


@router.post("/knowledge-tasks/scan", response_model=list[KnowledgeTaskSummary])
def scan_admin_knowledge_tasks(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> list[KnowledgeTaskSummary]:
    del current_user
    service = get_knowledge_service()
    discovered = service.discover_pending_sources()
    try:
        service.run_queued_tasks()
    except Exception:
        pass
    _clear_private_retrieval_caches()
    return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in discovered]


@router.post("/knowledge-tasks/rebuild", response_model=list[KnowledgeTaskSummary])
def rebuild_admin_knowledge_tasks(
    current_user: AuthenticatedUser = Depends(require_admin),
) -> list[KnowledgeTaskSummary]:
    del current_user
    service = get_knowledge_service()
    tasks = service.run_queued_tasks()
    _clear_private_retrieval_caches()
    return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in tasks]


@router.post("/knowledge-tasks/{task_id}/retry", response_model=KnowledgeTaskSummary)
def retry_admin_knowledge_task(
    task_id: str,
    current_user: AuthenticatedUser = Depends(require_admin),
) -> KnowledgeTaskSummary:
    del current_user
    service = get_knowledge_service()
    task = service.retry_task(task_id=task_id, requested_by_user_id=None)
    try:
        service.run_queued_tasks()
    except Exception:
        pass
    _clear_private_retrieval_caches()
    latest = service.get_task(task.task_id) or task
    return KnowledgeTaskSummary.model_validate(latest.model_dump())
