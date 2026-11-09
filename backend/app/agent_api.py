import hmac
import sqlite3
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.services.agent_tools import AgentTools
from app.services.llm import CloudModelError


app = FastAPI(title="CareerPilot Agent Tools", docs_url=None, redoc_url=None)
settings = get_settings()
tools = AgentTools(settings)


class ToolInput(BaseModel):
    payload: dict[str, Any]
    previous: dict[str, Any] | None = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/tools/{operation}")
async def execute(operation: str, request: Request, authorization: str = Header(default="")):
    expected = settings.agent_tools_token
    if not expected or not hmac.compare_digest(authorization, "Bearer " + expected):
        raise HTTPException(status_code=401, detail="Tool authentication required")
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Tool payload too large")
    try:
        data = ToolInput.model_validate_json(content)
        result = await tools.execute(operation, data.payload, data.previous)
        return {"result": result}
    except ValidationError:
        raise HTTPException(status_code=422, detail="Tool payload does not match the contract") from None
    except CloudModelError as failure:
        return JSONResponse(status_code=failure.status_code, content={"error_code": failure.error_code, "detail": failure.detail})
    except (KeyError, ValueError, TypeError, sqlite3.Error):
        raise HTTPException(status_code=502, detail="Tool input or provider configuration invalid") from None
