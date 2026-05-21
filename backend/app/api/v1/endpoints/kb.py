from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.dependencies import require_authenticated_user
from app.auth.schemas import AuthenticatedUser
from app.core.config import REPO_ROOT, get_settings
from app.files.service import FileService
from app.rag.kb.models import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseOverview,
    KnowledgeBaseUpdate,
    RagChunk,
    RagDocument,
    RagDocumentCreate,
    RagPipelineBatchRequest,
    RagPipelineBatchResult,
    RagPipelineRunRequest,
    RagPipelineResult,
)
from app.rag.spine import get_rag_spine_service

router = APIRouter(prefix="/kb")
logger = logging.getLogger(__name__)


@router.get("", response_model=list[KnowledgeBase])
def list_knowledge_bases(current_user: AuthenticatedUser = Depends(require_authenticated_user)) -> list[KnowledgeBase]:
    return get_rag_spine_service().list_kbs(owner_user_id=current_user.user_id)


@router.post("", response_model=KnowledgeBase)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> KnowledgeBase:
    return get_rag_spine_service().create_kb(owner_user_id=current_user.user_id, payload=payload)


@router.get("/{kb_id}", response_model=KnowledgeBase)
def get_knowledge_base(
    kb_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> KnowledgeBase:
    try:
        return get_rag_spine_service().get_kb(owner_user_id=current_user.user_id, kb_id=kb_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="knowledge base not found") from exc


@router.get("/{kb_id}/overview", response_model=KnowledgeBaseOverview)
def get_knowledge_base_overview(
    kb_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> KnowledgeBaseOverview:
    try:
        return get_rag_spine_service().get_kb_overview(owner_user_id=current_user.user_id, kb_id=kb_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="knowledge base not found") from exc


@router.patch("/{kb_id}", response_model=KnowledgeBase)
def update_knowledge_base(
    kb_id: str,
    payload: KnowledgeBaseUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> KnowledgeBase:
    try:
        return get_rag_spine_service().update_kb(owner_user_id=current_user.user_id, kb_id=kb_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="knowledge base not found") from exc


@router.delete("/{kb_id}")
def delete_knowledge_base(
    kb_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, str]:
    get_rag_spine_service().delete_kb(owner_user_id=current_user.user_id, kb_id=kb_id)
    return {"status": "deleted", "kb_id": kb_id}


@router.post("/{kb_id}/documents", response_model=RagDocument)
def create_document(
    kb_id: str,
    payload: RagDocumentCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    try:
        return get_rag_spine_service().create_document(owner_user_id=current_user.user_id, kb_id=kb_id, payload=payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="knowledge base or source document not found") from exc


@router.get("/{kb_id}/documents", response_model=list[RagDocument])
def list_documents(
    kb_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> list[RagDocument]:
    try:
        return get_rag_spine_service().list_documents(owner_user_id=current_user.user_id, kb_id=kb_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="knowledge base not found") from exc


@router.post("/{kb_id}/documents/upload", response_model=RagDocument)
async def upload_document_to_kb(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    """Upload a file directly into the RAG-Pro knowledge-base document pipeline."""

    content = await file.read()
    filename = file.filename or "upload.bin"
    mime_type = file.content_type or "application/octet-stream"
    try:
        FileService().validate_upload(filename=filename, mime_type=mime_type, size=len(content))
        suffix = Path(filename).suffix.lower()
        stored_name = f"kb-upload-{uuid4().hex[:12]}{suffix}"
        root = Path(get_settings().upload_dir)
        upload_root = root if root.is_absolute() else REPO_ROOT / root
        target_dir = upload_root / "kb" / kb_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / stored_name
        target_path.write_bytes(content)
        return get_rag_spine_service().create_document(
            owner_user_id=current_user.user_id,
            kb_id=kb_id,
            payload=RagDocumentCreate(
                title=filename,
                filename=filename,
                file_type=suffix.lstrip("."),
                file_size=len(content),
                file_path=str(target_path),
                source_type="private_upload",
                chunk_method="recursive",
            ),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="knowledge base not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except TypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    finally:
        await file.close()


@router.get("/{kb_id}/documents/{doc_id}", response_model=RagDocument)
def get_document(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    try:
        return get_rag_spine_service().get_document(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.get("/{kb_id}/documents/{doc_id}/status", response_model=RagDocument)
def get_document_status(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    try:
        return get_rag_spine_service().get_document(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.post("/{kb_id}/documents/{doc_id}/parse", response_model=RagDocument)
def parse_document(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    try:
        return get_rag_spine_service().parse_document(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.post("/{kb_id}/documents/{doc_id}/chunk", response_model=RagDocument)
def chunk_document(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    try:
        return get_rag_spine_service().chunk_document(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.post("/{kb_id}/documents/{doc_id}/index", response_model=RagDocument)
def index_document(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    try:
        return get_rag_spine_service().index_document(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.post("/{kb_id}/documents/{doc_id}/run-pipeline", response_model=RagPipelineResult)
def run_document_pipeline(
    kb_id: str,
    doc_id: str,
    payload: RagPipelineRunRequest | None = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagPipelineResult:
    try:
        return get_rag_spine_service().run_document_pipeline(
            owner_user_id=current_user.user_id,
            kb_id=kb_id,
            doc_id=doc_id,
            pipeline_mode=(payload.pipeline_mode if payload else "quick"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.post("/{kb_id}/documents/run-pipeline-batch", response_model=RagPipelineBatchResult)
def run_document_pipeline_batch(
    kb_id: str,
    payload: RagPipelineBatchRequest | None = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagPipelineBatchResult:
    try:
        return get_rag_spine_service().run_document_pipeline_batch(
            owner_user_id=current_user.user_id,
            kb_id=kb_id,
            doc_ids=(payload.doc_ids if payload else None),
            pipeline_mode=(payload.pipeline_mode if payload else "quick"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="knowledge base or document not found") from exc


@router.delete("/{kb_id}/documents/{doc_id}")
def delete_kb_document(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, str]:
    try:
        get_rag_spine_service().delete_document(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
        return {"status": "deleted", "kb_id": kb_id, "doc_id": doc_id}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.post("/{kb_id}/documents/{doc_id}/rebuild-index", response_model=RagDocument)
def rebuild_kb_document_index(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> RagDocument:
    try:
        return get_rag_spine_service().rebuild_document_index(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc


@router.get("/{kb_id}/documents/{doc_id}/chunks", response_model=list[RagChunk])
def list_document_chunks(
    kb_id: str,
    doc_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> list[RagChunk]:
    try:
        return get_rag_spine_service().list_chunks(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc

