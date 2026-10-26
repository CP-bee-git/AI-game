import json
import re
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import Settings


T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleProvider:
    """Connects Qwen Cloud, DeepSeek, or another OpenAI-compatible provider."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
        )

    async def chat(self, system: str, user: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return response.choices[0].message.content or ""

    async def chat_json(self, system: str, user: str, schema: type[T]) -> T:
        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        content = response.choices[0].message.content or "{}"
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        return schema.model_validate(json.loads(content))

    async def list_models(self) -> list[str]:
        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            max_tokens=1,
            messages=[{"role": "user", "content": "Reply with OK."}],
        )
        return [response.model or self.settings.openai_model]


def model_config(settings: Settings) -> dict[str, str | int]:
    return {
        "provider": settings.model_provider,
        "base_url": settings.openai_base_url,
        "model": settings.openai_model,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
    }

