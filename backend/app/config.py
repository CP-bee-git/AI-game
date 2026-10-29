from functools import lru_cache
from pathlib import Path

from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "CareerPilot API"
    api_prefix: str = "/api/v1"
    local_storage_dir: Path = Path("backend/storage/uploads")
    state_db_path: Path = Path("backend/storage/careerpilot.sqlite3")

    qwen_api_key: str = Field(default="", repr=False, validation_alias=AliasChoices("DASHSCOPE_API_KEY", "QWEN_API_KEY", "qwen_api_key"))
    qwen_region: Literal["china", "singapore"] = "china"
    qwen_chat_model: str = "qwen-plus"
    qwen_vision_model: str = "qwen-vl-plus"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    allowed_upload_extensions: str = ".pdf,.docx,.png,.jpg,.jpeg"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True, extra="ignore")

    @property
    def allowed_extensions(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_upload_extensions.split(",") if item.strip()}

    @property
    def qwen_chat_configured(self) -> bool:
        return bool(self.qwen_api_key and self.qwen_chat_model)

    @property
    def qwen_vision_configured(self) -> bool:
        return bool(self.qwen_api_key and self.qwen_vision_model)

    @property
    def qwen_base_url(self) -> str:
        # Only Alibaba Cloud endpoints are accepted; URLs supplied by users are never fetched.
        return {
            "china": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "singapore": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        }[self.qwen_region]


@lru_cache
def get_settings() -> Settings:
    return Settings()

