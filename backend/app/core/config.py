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
    ai_chat_provider: str = "ollama"
    model_provider_mode: str = "ollama"

    model_api_base_url: str = "http://127.0.0.1:11434"
    model_api_key: str = ""
    model_name: str = "deepseek-r1:8b"
    model_temperature: float = 0.2
    model_max_tokens: int = 4096
    model_timeout_seconds: float = 180.0
    model_max_retries: int = 1
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-r1:8b"
    ollama_timeout_seconds: float = 180.0
    ollama_max_retries: int = 1
    ollama_num_ctx: int = 8192
    ollama_keep_alive: str = "10m"
    ollama_think: bool = True
    rag_generation_provider: str = "ollama"
    rag_generation_model: str = "deepseek-r1:8b"

    embedding_api_base_url: str = "https://api.example.com/v1"
    embedding_api_key: str = "replace-with-embedding-api-key"
    embedding_model: str = "replace-with-embedding-model"

    rag_engine_enabled: bool = True
    rag_vector_enabled: bool = True
    rag_vector_backend: str = "milvus"
    rag_require_real_vector: bool = True
    rag_milvus_uri: str = "http://127.0.0.1:19530"
    rag_milvus_collection_prefix: str = "carbonrag"
    rag_embedding_provider: str = "bge_m3"
    rag_embedding_model: str = "BAAI/bge-m3"
    rag_embedding_device: str = "cpu"
    rag_model_cache_dir: str = "./data/outputs/models"
    rag_model_auto_download: bool = False
    rag_hf_endpoint: str = "https://hf-mirror.com"
    rag_langchain_enabled: bool = True
    rag_bm25_enabled: bool = True
    rag_hyde_enabled: bool = True
    rag_rerank_enabled: bool = True
    rag_rerank_provider: str = "bge_reranker"
    rag_rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rag_default_mode: str = "mix"
    rag_chroma_persist_dir: str = "./data/outputs/chroma"
    rag_chroma_collection: str = "carbonrag_langchain"
    rag_langchain_chunk_size: int = 800
    rag_langchain_chunk_overlap: int = 120
    rag_langchain_default_top_k: int = 5
    rag_langsmith_tracing: bool = False
    rag_parser_provider: str = "default"
    rag_enable_mineru: bool = False
    rag_parser_fallback_chain: str = "docling,mineru,default"
    rag_enable_policy_crawler: bool = True
    rag_policy_crawler_backend: str = "local_scrapy"
    rag_policy_scrapyd_endpoint: str = "http://127.0.0.1:6800"
    rag_policy_scrapyd_project: str = "carbonrag"
    rag_policy_scrapyd_spider: str = "carbonrag_policy_spider"
    rag_policy_scrapyd_health_timeout_seconds: float = 3.0
    rag_policy_scrapyd_poll_interval_seconds: float = 1.0
    rag_policy_scrapyd_poll_timeout_seconds: float = 60.0
    rag_policy_scrapyd_feed_url_template: str | None = None
    rag_policy_live_crawler_manual_enabled: bool = True
    rag_policy_live_crawler_scheduled_enabled: bool = False
    rag_policy_live_crawler_startup_seed_sources: bool = True
    rag_policy_live_crawler_auto_publish: bool = False
    rag_policy_live_crawler_initial_delay_seconds: float = 60.0
    rag_policy_live_crawler_interval_seconds: int = 86_400
    rag_policy_live_crawler_failure_backoff_seconds: int = 3_600
    rag_policy_live_crawler_max_depth: int = 1
    rag_policy_live_crawler_max_pages: int = 8
    rag_policy_live_crawler_download_delay_seconds: float = 1.0
    rag_policy_live_crawler_concurrent_per_domain: int = 1
    rag_policy_live_crawler_timeout_seconds: float = 120.0
    rag_policy_live_crawler_user_agent: str = "CarbonRagPolicyCrawler/1.0 (+official-policy-knowledge)"
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
    enable_web_ssh_terminal: bool = False

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def resolve_repo_path(path_value: str | Path) -> Path:
    """Resolve relative runtime paths against the repository root, not process cwd."""

    path = Path(path_value)
    return path if path.is_absolute() else REPO_ROOT / path
