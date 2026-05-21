import logging

from fastapi import APIRouter, Depends, HTTPException

from app.admin.schemas import (
    AdminFeedbackOverview,
    AdminPrivateSampleItem,
    AdminSystemStatus,
    AdminUserSummary,
    CreateAdminUserRequest,
    DeleteAdminUsersRequest,
    DeleteAdminUsersResponse,
    KnowledgeRefreshTask,
    PolicyCrawlerActiveMaintenanceRequest,
    PolicyCrawlerActiveMaintenanceResponse,
    PolicyCrawlerAutoRagKbStatus,
    PolicyCrawlerBatchPublishRequest,
    PolicyCrawlerBatchPublishResponse,
    PolicyCrawlerCandidateStatus,
    PolicyCrawlerCandidateArtifactsSummary,
    PolicyCrawlerCandidatePage,
    PolicyCrawlerCandidateSummary,
    PolicyCrawlerDryRunSummary,
    PolicyCrawlerMaintenanceRunPage,
    PolicyCrawlerMaintenanceRunSummary,
    PolicyCrawlerMaintenanceStatus,
    PolicyCrawlerRecommendedImportSummary,
    PolicyCrawlerRunPage,
    PolicyCrawlerRunRequest,
    PolicyCrawlerRunSummary,
    PolicyCrawlerSourceSummary,
    PolicyCrawlerSourceUpsertRequest,
    PolicyCrawlerStatusSummary,
    PolicyShowcaseChunkSummary,
    PolicyShowcaseRetrievalPreview,
    PolicyShowcaseSourceSummary,
    PolicyShowcaseStatus,
    TriggerKnowledgeRefreshRequest,
    UpdateAdminPrivateSampleRequest,
    UpdateAdminUserRequest,
)
from app.admin.service import get_admin_service
from app.auth.dependencies import require_admin, require_management_active_relay, require_management_action_ack
from app.auth.schemas import AuthenticatedUser, ResetPasswordResponse
from app.auth.service import AuthenticationError, ProtectedAccountDeletionError
from app.knowledge import get_knowledge_service
from app.knowledge.policy_live_crawler import PolicyCrawlerBusyError
from app.knowledge.schemas import KnowledgeItemSummary, KnowledgeTaskSummary
from app.private_samples.catalog import refresh_private_sample_catalog
from app.rag.service import get_rag_engine_service
from app.retrieval.mixed_retriever import get_mixed_scope_retriever
from app.retrieval.private_retriever import get_private_sample_retriever

router = APIRouter(prefix="/admin")
logger = logging.getLogger(__name__)


def _clear_private_retrieval_caches() -> None:
    get_private_sample_retriever.cache_clear()
    get_mixed_scope_retriever.cache_clear()
    get_rag_engine_service.cache_clear()


@router.get("/system/status", response_model=AdminSystemStatus)
def get_admin_system_status(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> AdminSystemStatus:
    del current_user
    return get_admin_service().get_system_status()


@router.get("/users", response_model=list[AdminUserSummary])
def list_admin_users(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> list[AdminUserSummary]:
    del current_user
    return get_admin_service().list_users()


@router.post("/users", response_model=AdminUserSummary)
def create_admin_user(
    payload: CreateAdminUserRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_USER_CREATE", "user", default_target_id="new")),
) -> AdminUserSummary:
    try:
        return get_admin_service().create_user(payload=payload, actor_role=current_user.role)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ProtectedAccountDeletionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
def update_admin_user(
    user_id: str,
    payload: UpdateAdminUserRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_USER_UPDATE", "user", target_param="user_id")),
) -> AdminUserSummary:
    try:
        get_admin_service().update_user(
            user_id=user_id,
            role=payload.role,
            is_active=payload.is_active,
            actor_role=current_user.role,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found.")
    return next(item for item in get_admin_service().list_users() if item.user_id == user_id)


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
def reset_admin_user_password(
    user_id: str,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_USER_RESET_PASSWORD", "user", target_param="user_id")),
) -> ResetPasswordResponse:
    del current_user
    try:
        temporary_password = get_admin_service().reset_password(user_id=user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found.")
    return ResetPasswordResponse(temporary_password=temporary_password)


@router.delete("/users", response_model=DeleteAdminUsersResponse)
def delete_admin_users(
    payload: DeleteAdminUsersRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_USER_DELETE", "user_batch", default_target_id="batch")),
) -> DeleteAdminUsersResponse:
    try:
        deleted_user_ids = get_admin_service().delete_users(
            actor_user_id=current_user.user_id,
            actor_role=current_user.role,
            current_password=payload.current_password,
            user_ids=payload.user_ids,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ProtectedAccountDeletionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"User not found: {exc}")
    return DeleteAdminUsersResponse(deleted_user_ids=deleted_user_ids)


@router.get("/feedback/overview", response_model=AdminFeedbackOverview)
def get_admin_feedback_overview(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> AdminFeedbackOverview:
    del current_user
    return get_admin_service().get_feedback_overview()


@router.get("/private-samples", response_model=list[AdminPrivateSampleItem])
def list_admin_private_samples(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> list[AdminPrivateSampleItem]:
    del current_user
    return get_admin_service().list_private_samples()


@router.get("/policy-sources", response_model=list[PolicyShowcaseSourceSummary])
def list_admin_policy_sources(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> list[PolicyShowcaseSourceSummary]:
    del current_user
    return get_admin_service().list_policy_showcase_sources()


@router.post("/policy-sources/{source_id}/run", response_model=PolicyShowcaseStatus)
def run_admin_policy_source(
    source_id: str,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_POLICY_SOURCE_RUN", "policy_source", target_param="source_id")),
) -> PolicyShowcaseStatus:
    try:
        return get_admin_service().run_policy_showcase_source(
            source_id=source_id,
            requested_by_user_id=current_user.user_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy source not found.")
    except Exception as exc:
        logger.exception("Policy showcase ingestion failed for source_id=%s", source_id)
        raise HTTPException(status_code=500, detail="Policy showcase ingestion failed. Check task status and server logs.") from exc


@router.get("/policy-sources/{source_id}/status", response_model=PolicyShowcaseStatus)
def get_admin_policy_source_status(
    source_id: str,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyShowcaseStatus:
    del current_user
    try:
        return get_admin_service().get_policy_showcase_status(source_id=source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy source not found.")


@router.get("/policy-sources/{source_id}/chunks", response_model=list[PolicyShowcaseChunkSummary])
def list_admin_policy_source_chunks(
    source_id: str,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> list[PolicyShowcaseChunkSummary]:
    del current_user
    try:
        return get_admin_service().list_policy_showcase_chunks(source_id=source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy source not found.")


@router.get("/policy-sources/{source_id}/retrieval-preview", response_model=PolicyShowcaseRetrievalPreview)
def get_admin_policy_source_retrieval_preview(
    source_id: str,
    query: str | None = None,
    top_k: int = 5,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyShowcaseRetrievalPreview:
    del current_user
    try:
        return get_admin_service().get_policy_showcase_retrieval_preview(
            source_id=source_id,
            query=query,
            top_k=top_k,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy source not found.")


@router.get("/policy-crawler/status", response_model=PolicyCrawlerStatusSummary)
def get_admin_policy_crawler_status(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerStatusSummary:
    del current_user
    return get_admin_service().get_policy_crawler_status()


@router.get("/policy-crawler/sources", response_model=list[PolicyCrawlerSourceSummary])
def list_admin_policy_crawler_sources(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> list[PolicyCrawlerSourceSummary]:
    del current_user
    return get_admin_service().list_policy_crawler_sources()


@router.post("/policy-crawler/sources", response_model=PolicyCrawlerSourceSummary)
def create_admin_policy_crawler_source(
    payload: PolicyCrawlerSourceUpsertRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_SOURCE_CREATE", "policy_crawler_source", default_target_id="new")),
) -> PolicyCrawlerSourceSummary:
    del current_user
    try:
        return get_admin_service().create_policy_crawler_source(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/policy-crawler/sources/recommended/import", response_model=PolicyCrawlerRecommendedImportSummary)
def import_admin_recommended_policy_crawler_sources(
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_RECOMMENDED_IMPORT", "policy_crawler_source", default_target_id="recommended")),
) -> PolicyCrawlerRecommendedImportSummary:
    del current_user
    try:
        return get_admin_service().import_recommended_policy_crawler_sources()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/policy-crawler/sources/{source_id}", response_model=PolicyCrawlerSourceSummary)
def update_admin_policy_crawler_source(
    source_id: str,
    payload: PolicyCrawlerSourceUpsertRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_SOURCE_UPDATE", "policy_crawler_source", target_param="source_id")),
) -> PolicyCrawlerSourceSummary:
    del current_user
    try:
        return get_admin_service().update_policy_crawler_source(source_id=source_id, payload=payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler source not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/policy-crawler/sources/{source_id}")
def delete_admin_policy_crawler_source(
    source_id: str,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_SOURCE_DELETE", "policy_crawler_source", target_param="source_id")),
) -> dict[str, str]:
    del current_user
    try:
        return get_admin_service().delete_policy_crawler_source(source_id=source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler source not found.")


@router.post("/policy-crawler/sources/{source_id}/dry-run", response_model=PolicyCrawlerDryRunSummary)
def dry_run_admin_policy_crawler_source(
    source_id: str,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerDryRunSummary:
    del current_user
    try:
        return get_admin_service().dry_run_policy_crawler_source(source_id=source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler source not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/policy-crawler/sources/{source_id}/run", response_model=PolicyCrawlerRunSummary)
def run_admin_policy_crawler_source(
    source_id: str,
    payload: PolicyCrawlerRunRequest | None = None,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_SOURCE_RUN", "policy_crawler_source", target_param="source_id")),
) -> PolicyCrawlerRunSummary:
    try:
        return get_admin_service().run_policy_crawler_source(
            source_id=source_id,
            requested_by_user_id=current_user.user_id,
            payload=payload,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler source not found.")
    except PolicyCrawlerBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Policy crawler run failed for source_id=%s", source_id)
        raise HTTPException(status_code=500, detail="Policy crawler run failed. Check run status and server logs.") from exc


@router.get("/policy-crawler/runs", response_model=PolicyCrawlerRunPage)
def list_admin_policy_crawler_runs(
    source_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "started_at",
    sort_order: str = "desc",
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerRunPage:
    del current_user
    return get_admin_service().list_policy_crawler_runs_page(
        source_id=source_id,
        status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/policy-crawler/candidates", response_model=PolicyCrawlerCandidatePage)
def list_admin_policy_crawler_candidates(
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
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerCandidatePage:
    del current_user
    return get_admin_service().list_policy_crawler_candidates_page(
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


@router.get("/policy-crawler/auto-rag-kb/status", response_model=PolicyCrawlerAutoRagKbStatus)
def get_admin_policy_crawler_auto_rag_kb_status(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerAutoRagKbStatus:
    del current_user
    return get_admin_service().get_policy_crawler_auto_rag_kb_status()


@router.get("/policy-crawler/active-maintenance/status", response_model=PolicyCrawlerMaintenanceStatus)
def get_admin_policy_crawler_active_maintenance_status(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerMaintenanceStatus:
    del current_user
    return get_admin_service().get_policy_crawler_active_maintenance_status()


@router.post("/policy-crawler/active-maintenance/run", response_model=PolicyCrawlerActiveMaintenanceResponse)
def run_admin_policy_crawler_active_maintenance(
    payload: PolicyCrawlerActiveMaintenanceRequest | None = None,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerActiveMaintenanceResponse:
    return get_admin_service().run_policy_crawler_active_maintenance(
        reviewed_by_user_id=current_user.user_id,
        payload=payload or PolicyCrawlerActiveMaintenanceRequest(),
    )


@router.get("/policy-crawler/maintenance-runs", response_model=PolicyCrawlerMaintenanceRunPage)
def list_admin_policy_crawler_maintenance_runs(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerMaintenanceRunPage:
    del current_user
    return get_admin_service().list_policy_crawler_maintenance_runs_page(status=status, page=page, page_size=page_size)


@router.get("/policy-crawler/maintenance-runs/{maintenance_run_id}", response_model=PolicyCrawlerMaintenanceRunSummary)
def get_admin_policy_crawler_maintenance_run(
    maintenance_run_id: str,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerMaintenanceRunSummary:
    del current_user
    try:
        return get_admin_service().get_policy_crawler_maintenance_run(maintenance_run_id=maintenance_run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler maintenance run not found.")


@router.get("/policy-crawler/candidates/{candidate_id}/artifacts", response_model=PolicyCrawlerCandidateArtifactsSummary)
def get_admin_policy_crawler_candidate_artifacts(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> PolicyCrawlerCandidateArtifactsSummary:
    del current_user
    try:
        return get_admin_service().get_policy_crawler_candidate_artifacts(candidate_id=candidate_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler candidate not found.")


@router.post("/policy-crawler/candidates/{candidate_id}/publish", response_model=PolicyCrawlerCandidateSummary)
def publish_admin_policy_crawler_candidate(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_CANDIDATE_PUBLISH_LEGACY", "policy_crawler_candidate", target_param="candidate_id")),
) -> PolicyCrawlerCandidateSummary:
    try:
        return get_admin_service().publish_policy_crawler_candidate(
            candidate_id=candidate_id,
            reviewed_by_user_id=current_user.user_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler candidate not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=f"Candidate content file is missing: {exc}") from exc


@router.post("/policy-crawler/candidates/{candidate_id}/publish-to-rag", response_model=PolicyCrawlerCandidateSummary)
def publish_admin_policy_crawler_candidate_to_rag(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_CANDIDATE_PUBLISH_TO_RAG", "policy_crawler_candidate", target_param="candidate_id")),
) -> PolicyCrawlerCandidateSummary:
    try:
        return get_admin_service().publish_policy_crawler_candidate_to_rag(
            candidate_id=candidate_id,
            reviewed_by_user_id=current_user.user_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler candidate not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=f"Candidate content file is missing: {exc}") from exc
    except Exception as exc:
        logger.exception("Policy crawler candidate RAG publish failed; candidate_id=%s", candidate_id)
        raise HTTPException(status_code=500, detail=f"Candidate RAG publish failed: {exc}") from exc


@router.post("/policy-crawler/candidates/batch-publish-to-rag", response_model=PolicyCrawlerBatchPublishResponse)
def batch_publish_admin_policy_crawler_candidates_to_rag(
    payload: PolicyCrawlerBatchPublishRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_CANDIDATE_BATCH_PUBLISH_TO_RAG", "policy_crawler_candidate", default_target_id="batch")),
) -> PolicyCrawlerBatchPublishResponse:
    try:
        return get_admin_service().batch_publish_policy_crawler_candidates_to_rag(
            candidate_ids=payload.candidate_ids,
            reviewed_by_user_id=current_user.user_id,
            skip_duplicates=payload.skip_duplicates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/policy-crawler/candidates/{candidate_id}/reject", response_model=PolicyCrawlerCandidateSummary)
def reject_admin_policy_crawler_candidate(
    candidate_id: str,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("POLICY_CRAWLER_CANDIDATE_REJECT", "policy_crawler_candidate", target_param="candidate_id")),
) -> PolicyCrawlerCandidateSummary:
    try:
        return get_admin_service().reject_policy_crawler_candidate(
            candidate_id=candidate_id,
            reviewed_by_user_id=current_user.user_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Policy crawler candidate not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/private-samples/{doc_id}", response_model=AdminPrivateSampleItem)
def update_admin_private_sample(
    doc_id: str,
    payload: UpdateAdminPrivateSampleRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_PRIVATE_SAMPLE_UPDATE", "private_sample", target_param="doc_id")),
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
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> list[KnowledgeRefreshTask]:
    del current_user
    return get_admin_service().list_knowledge_refresh_tasks()


@router.post("/knowledge-refresh-tasks", response_model=KnowledgeRefreshTask)
def trigger_knowledge_refresh_task(
    payload: TriggerKnowledgeRefreshRequest,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_KNOWLEDGE_REFRESH_TRIGGER", "knowledge_refresh", default_target_id="trigger")),
) -> KnowledgeRefreshTask:
    try:
        return get_admin_service().trigger_knowledge_refresh(
            scope=payload.scope,
            requested_by_user_id=current_user.user_id,
        )
    except Exception as exc:
        logger.exception("Knowledge refresh failed for scope=%s", payload.scope)
        raise HTTPException(status_code=500, detail="Knowledge refresh failed. Please retry later or check server logs.") from exc


@router.get("/knowledge-items", response_model=list[KnowledgeItemSummary])
def list_admin_knowledge_items(
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
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
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_KNOWLEDGE_ITEM_UPDATE", "knowledge_item", target_param="knowledge_item_id")),
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
    current_user: AuthenticatedUser = Depends(require_management_active_relay),
) -> list[KnowledgeTaskSummary]:
    del current_user
    tasks = get_knowledge_service().list_tasks(owner_user_id=None, include_shared=True)
    return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in tasks]


@router.post("/knowledge-tasks/scan", response_model=list[KnowledgeTaskSummary])
def scan_admin_knowledge_tasks(
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_KNOWLEDGE_TASK_SCAN", "knowledge_task", default_target_id="scan")),
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
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_KNOWLEDGE_TASK_REBUILD", "knowledge_task", default_target_id="rebuild")),
) -> list[KnowledgeTaskSummary]:
    del current_user
    service = get_knowledge_service()
    tasks = service.run_queued_tasks()
    _clear_private_retrieval_caches()
    return [KnowledgeTaskSummary.model_validate(task.model_dump()) for task in tasks]


@router.post("/knowledge-tasks/{task_id}/retry", response_model=KnowledgeTaskSummary)
def retry_admin_knowledge_task(
    task_id: str,
    current_user: AuthenticatedUser = Depends(require_management_action_ack("ADMIN_KNOWLEDGE_TASK_RETRY", "knowledge_task", target_param="task_id")),
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
