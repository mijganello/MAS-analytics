from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    # App
    environment: Literal["development", "production", "test"] = "development"
    secret_key: str = "dev-secret"

    # Database
    database_url: str = "postgresql+asyncpg://mas:mas@localhost:5432/mas_analytics"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    llm_provider: Literal["deepseek", "ollama"] = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    ollama_base_url: str = "http://localhost:11434"

    # Models
    orchestrator_model: str = "deepseek-reasoner"
    worker_model: str = "deepseek-chat"
    critic_model: str = "deepseek-chat"
    embedding_model: str = "BAAI/bge-m3"

    # Local Ollama models — qwen2.5 is recommended: good at Russian, JSON, structured output
    # Override via OLLAMA_WORKER_MODEL etc. in .env if you have more VRAM
    ollama_orchestrator_model: str = "qwen2.5:7b"
    ollama_worker_model: str = "qwen2.5:7b"
    ollama_critic_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "nomic-embed-text"

    # Limits
    max_upload_size_mb: int = 50
    session_ttl_hours: int = 24
    max_task_retries: int = 2
    max_task_tokens: int = 8000
    task_timeout_seconds: int = 120

    # Uploads
    upload_dir: str = "/app/uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
