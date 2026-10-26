from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "CareerPilot API"
    api_prefix: str = "/api/v1"
    web_origin: str = "http://localhost:3000"

    storage_backend: str = "local"
    local_storage_dir: Path = Path("backend/storage")

    database_url: str = "postgresql+psycopg://careerpilot:careerpilot@localhost:5432/careerpilot"
    redis_url: str = "redis://localhost:6379/0"

    model_provider: str = "qwen"
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openai_api_key: str = ""
    openai_model: str = "qwen-plus"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024

    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    allowed_upload_extensions: str = ".pdf,.docx,.png,.jpg,.jpeg"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_extensions(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_upload_extensions.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

