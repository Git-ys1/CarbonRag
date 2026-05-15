from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.calc_carbon import router as calc_carbon_router
from app.api.v1.endpoints.carbon_factors import router as carbon_factors_router
from app.api.v1.endpoints.feedback import router as feedback_router
from app.api.v1.endpoints.file_previews import router as file_previews_router
from app.api.v1.endpoints.files import router as files_router
from app.api.v1.endpoints.knowledge import router as knowledge_router
from app.api.v1.endpoints.kb import router as kb_router
from app.api.v1.endpoints.memory import router as memory_router
from app.management.router import router as management_router
from app.api.v1.endpoints.private_samples import router as private_samples_router
from app.api.v1.endpoints.rag import router as rag_router
from app.api.v1.endpoints.report_exports import router as report_exports_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.sessions import router as sessions_router
from app.api.v1.endpoints.settings import router as settings_router
from app.api.v1.endpoints.system import router as system_router

router = APIRouter()
router.include_router(auth_router, tags=["auth"])
router.include_router(admin_router, tags=["admin"])
router.include_router(calc_carbon_router, tags=["calc-carbon"])
router.include_router(carbon_factors_router, tags=["carbon-factors"])
router.include_router(feedback_router, tags=["feedback"])
router.include_router(file_previews_router, tags=["file-previews"])
router.include_router(files_router, tags=["files"])
router.include_router(kb_router, tags=["kb"])
router.include_router(knowledge_router, tags=["knowledge"])
router.include_router(memory_router, tags=["memory"])
router.include_router(management_router, tags=["management"])
router.include_router(me_router, tags=["me"])
router.include_router(private_samples_router, tags=["private-samples"])
router.include_router(rag_router, tags=["rag"])
router.include_router(report_exports_router, tags=["report-exports"])
router.include_router(reports_router, tags=["reports"])
router.include_router(sessions_router, tags=["sessions"])
router.include_router(settings_router, tags=["settings"])
router.include_router(system_router, tags=["system"])
