import asyncio
import json

from app.config import get_settings
from app.schemas import ChatResponse
from app.services.agent_tools import AgentTools
from app.services.llm import CloudModelError


async def main():
    tools = AgentTools(get_settings())
    for provider in ("deepseek", "qwen"):
        try:
            result = await tools.complete(provider, "连接检查，只返回 reply=连接正常。", {"probe": True}, ChatResponse)
            print(json.dumps({"provider": provider, "status": "passed", "reply_present": bool(result["reply"])}, ensure_ascii=False))
        except CloudModelError as error:
            print(json.dumps({"provider": provider, "status": "failed", "error_code": error.error_code}, ensure_ascii=False))
    try:
        result = await tools.request("ark", "GET", "/models")
        choices = [item.get("id") for item in result.get("data", []) if "seedream" in item.get("id", "") or "seedance" in item.get("id", "")]
        print(json.dumps({"provider": "ark", "status": "catalog_only", "media_models": choices, "generation_submitted": False}, ensure_ascii=False))
    except CloudModelError as error:
        print(json.dumps({"provider": "ark", "status": "failed", "error_code": error.error_code}))


if __name__ == "__main__":
    asyncio.run(main())
