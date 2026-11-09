import argparse
import asyncio
import json
from pathlib import Path

import httpx

from app.config import get_settings
from app.services.agent_tools import AgentTools
from app.services.llm import CloudModelError


ROOT = Path(__file__).resolve().parents[1]


async def main(probe_media: bool):
    settings = get_settings().model_copy(update={"deepseek_provider": "bailian"})
    tools = AgentTools(settings)
    key, base, _model = tools.credentials("qwen")
    checks = []
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(base + "/models", headers={"Authorization": "Bearer " + key})
        if response.is_error:
            raise SystemExit(f"Bailian model catalog HTTP {response.status_code}")
        models = [item["id"] for item in response.json().get("data", [])]
        families = {family: [model for model in models if family in model.lower()] for family in ("deepseek", "doubao", "seedream", "seedance")}
        print("Catalog:", {family: len(items) for family, items in families.items()}, flush=True)
        payload = {"blocks": [{"block_id": "b1", "text": "合成简历：2026年毕业于虚构大学计算机专业，本科学历。掌握Python和SQL，课程项目负责清洗1000条记录，求职意向上海数据分析实习，7月到岗。"}], "profile": {"skills": [{"name": "Python"}, {"name": "SQL"}]}, "job": {"title": "数据分析实习", "required_skills": ["Python", "SQL"]}}
        for operation in ("analysis", "report"):
            try:
                result = await tools.execute(operation, payload)
                checks.append({"task": operation, "status": "passed", "output": result})
            except CloudModelError as error:
                checks.append({"task": operation, "status": "failed", "error_code": error.error_code})
            print({name: value for name, value in checks[-1].items() if name != "output"}, flush=True)
        attempts = [("doubao_text", base + "/chat/completions", {"model": "doubao-seed-2-1-lite-260915", "max_tokens": 32, "messages": [{"role": "user", "content": "只回复：连接正常"}]})]
        if probe_media:
            attempts += [
                ("seedream_image", "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation", {"model": "doubao-seedream-5-0-flash-260915", "input": {"messages": [{"role": "user", "content": [{"text": "数据分析师的办公场景职业插画，无身份信息。"}]}]}, "parameters": {"size": "1024*1024", "n": 1}}),
                ("seedance_video", "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis", {"model": "doubao-seedance-2-0-fast-260128", "input": {"prompt": "数据分析师的办公场景短片。"}, "parameters": {"size": "1280*720", "duration": 5}}),
            ]
        for operation, url, body in attempts:
            headers = {"Authorization": "Bearer " + key}
            if operation == "seedance_video":
                headers["X-DashScope-Async"] = "enable"
            response = await client.post(url, headers=headers, json=body)
            data = response.json()
            record = {"task": operation, "http_status": response.status_code, "error_code": data.get("error", {}).get("code") or data.get("code"), "generation_accepted": response.status_code == 200}
            checks.append(record)
            print(record, flush=True)
    result = {"same_bailian_key": True, "endpoint": base, "model_families": families, "checks": checks}
    destination = ROOT / ".private/dify/bailian-single-key-check.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    destination.chmod(0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-media", action="store_true", help="Try one Seedream and one Seedance request; supported calls may incur charges")
    asyncio.run(main(parser.parse_args().probe_media))
