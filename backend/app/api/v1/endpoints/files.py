from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.dependencies import require_authenticated_user
from app.auth.schemas import AuthenticatedUser
from app.files.schemas import UploadedFileResponse
from app.files.service import FileService, get_file_service
from app.retrieval.mixed_retriever import get_mixed_scope_retriever
from app.retrieval.private_retriever import get_private_sample_retriever
from app.knowledge import get_knowledge_service
from app.rag.service import get_rag_engine_service
from app.session.service import get_session_service

router = APIRouter()


@router.post("/files", response_model=UploadedFileResponse)
async def upload_file(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> UploadedFileResponse:
    service: FileService = get_file_service()
    try:
        uploaded = service.save_upload(
            owner_user_id=current_user.user_id,
            session_id=session_id,
            filename=file.filename or "upload.bin",
            mime_type=file.content_type or "application/octet-stream",
            content=await file.read(),
        )
        knowledge_service = get_knowledge_service()
        knowledge_service.sync_uploaded_files(owner_user_id=current_user.user_id)
        try:
            knowledge_service.run_queued_tasks()
        except Exception:
            pass
        get_private_sample_retriever.cache_clear()
        get_mixed_scope_retriever.cache_clear()
        get_rag_engine_service.cache_clear()
        item = knowledge_service.store.get_item_by_source(
            owner_user_id=current_user.user_id,
            library_scope="personal",
            source_type="uploaded_file",
            source_ref=uploaded.file_id,
        )
        if item is not None:
            existing_item_ids = get_session_service().list_attached_knowledge_item_ids(
                owner_user_id=current_user.user_id,
                session_id=session_id,
            )
            get_session_service().replace_attached_knowledge_items(
                owner_user_id=current_user.user_id,
                session_id=session_id,
                knowledge_item_ids=[*existing_item_ids, item.knowledge_item_id],
            )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found.")
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    finally:
        await file.close()

    return UploadedFileResponse.model_validate(uploaded.model_dump())
