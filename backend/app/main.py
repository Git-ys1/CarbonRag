from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.router import router as api_router
from app.auth.service import get_auth_service
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.knowledge import get_knowledge_service, get_knowledge_task_runner, get_policy_crawler_scheduler

settings = get_settings()
configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="CarbonRag conversation, calc-carbon, and report generation backend"
)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(api_router, prefix=settings.api_prefix)


@app.on_event("startup")
def bootstrap_identity_runtime() -> None:
    get_auth_service()
    get_knowledge_service().sync_shared_private_samples()
    get_knowledge_task_runner().start()
    get_policy_crawler_scheduler().start()


@app.on_event("shutdown")
def shutdown_knowledge_runtime() -> None:
    get_policy_crawler_scheduler().stop()
    get_knowledge_task_runner().stop()
