import json
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.services.llm import CloudModelError
from app.services.session import current_session


Result = TypeVar("Result", bound=BaseModel)
OPERATIONS = ("profile", "analysis", "match", "report", "questions", "evaluate", "summary", "chat", "ocr", "media_create", "media_status")


class DifyClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def keys(self) -> dict[str, str]:
        try:
            data = json.loads(Path(self.settings.dify_app_keys_file).read_text())
            return {name: value for name, value in data.items() if name in OPERATIONS and isinstance(value, str) and value}
        except (OSError, ValueError, AttributeError):
            return {}

    def configured(self, operation: str) -> bool:
        return operation in self.keys()

    async def run(self, operation: str, payload: dict, schema: type[Result] | None = None) -> dict | Result:
        key = self.keys().get(operation)
        if not key:
            raise CloudModelError(503, "dify_not_configured", f"Dify 的 {operation} 工作流尚未配置或发布。")
        body = {
            "inputs": {"payload": json.dumps(payload, ensure_ascii=False, default=str)},
            "response_mode": "blocking",
            "user": current_session.get(),
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.dify_timeout_seconds, transport=self.transport) as client:
                response = await client.post(
                    f"{self.settings.dify_base_url.rstrip('/')}/workflows/run",
                    headers={"Authorization": f"Bearer {key}"}, json=body,
                )
        except httpx.TimeoutException:
            raise CloudModelError(504, "dify_timeout", "Dify 工作流超时；请检查运行日志后再决定是否重新执行。") from None
        except httpx.RequestError:
            raise CloudModelError(503, "dify_connection", "无法连接 Dify，请检查本机服务状态。") from None
        if response.status_code != 200:
            status = 429 if response.status_code == 429 else 503
            raise CloudModelError(status, "dify_request_failed", "Dify 拒绝了请求，请核对应用密钥、发布状态和限流设置。")
        try:
            data = response.json()["data"]
            if data.get("status") != "succeeded":
                raise ValueError("Workflow failed")
            result = data["outputs"]["result"]
            if isinstance(result, str):
                result = json.loads(result)
            if not isinstance(result, dict):
                raise ValueError("Expected object")
            if schema:
                return schema.model_validate(result)
            return result
        except (ValueError, TypeError, KeyError, AttributeError, ValidationError):
            raise CloudModelError(502, "dify_invalid_output", "Dify 工作流失败或返回格式不符；请在控制台检查节点输出。") from None
