from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
LOCAL_PROVIDER_CONFIG_PATH = BACKEND_DIR / "local_provider_config.json"


class Settings(BaseSettings):
    app_name: str = "CarbonRag"
    app_version: str = "v1.1.13"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    api_prefix: str = "/api/v1"
    model_provider_mode: str = "openai_compatible"

    model_api_base_url: str = "https://api.example.com/v1"
    model_api_key: str = "replace-with-model-api-key"
    model_name: str = "gpt-5.4"
    model_temperature: float = 0.2
    model_max_tokens: int = 4096
    model_timeout_seconds: float = 30.0
    model_max_retries: int = 2

    embedding_api_base_url: str = "https://api.example.com/v1"
    embedding_api_key: str = "replace-with-embedding-api-key"
    embedding_model: str = "replace-with-embedding-model"

    rag_engine_enabled: bool = False
    rag_vector_enabled: bool = False
    rag_vector_backend: str = "current"
    rag_rerank_enabled: bool = False
    rag_default_mode: str = "mix"
    rag_parser_provider: str = "default"
    rag_enable_mineru: bool = False
    rag_parser_fallback_chain: str = "docling,mineru,default"
    rag_enable_policy_crawler: bool = False
    rag_policy_live_crawler_manual_enabled: bool = True
    rag_policy_live_crawler_scheduled_enabled: bool = False
    rag_policy_live_crawler_startup_seed_sources: bool = True
    rag_policy_live_crawler_initial_delay_seconds: float = 60.0
    rag_policy_live_crawler_interval_seconds: int = 86_400
    rag_policy_live_crawler_failure_backoff_seconds: int = 3_600
    rag_policy_live_crawler_max_depth: int = 1
    rag_policy_live_crawler_max_pages: int = 20
    rag_policy_live_crawler_download_delay_seconds: float = 2.0
    rag_policy_live_crawler_concurrent_per_domain: int = 1
    rag_policy_live_crawler_timeout_seconds: float = 60.0
    rag_policy_live_crawler_user_agent: str = "CarbonRagPolicyCrawler/1.0 (+admin-reviewed)"
    vector_store_path: str = "./data/outputs/vector_store"
    public_data_dir: str = "./data/public"
    private_sample_dir: str = "./data/private_sample"
    factor_data_dir: str = "./data/factors"
    upload_dir: str = "./data/outputs/uploads"
    database_url: str | None = None
    memory_backend: str | None = None
    settings_encryption_key: str = "carbonrag-dev-settings-key"
    memory_context_budget_estimate: int = 258_000
    memory_compaction_trigger_estimate: int = 206_400
    memory_recent_turn_window: int = 6
    memory_min_recent_message_count: int = 4
    memory_note_read_limit: int = 5
    memory_note_max_chars: int = 3_000

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
