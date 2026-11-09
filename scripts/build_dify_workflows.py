import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = {
    "profile": ("简历结构化 · 千问", ["profile"]),
    "analysis": ("五维评分 · DeepSeek 与复核", ["analysis", "analysis_review", "analysis_final"]),
    "match": ("岗位多维匹配 · DeepSeek", ["match"]),
    "report": ("诊断报告 · 千问写作与 DeepSeek 评审", ["report", "report_review", "report_final"]),
    "questions": ("面试出题 · 千问", ["questions"]),
    "evaluate": ("面试评分 · DeepSeek", ["evaluate"]),
    "summary": ("面试复盘 · 千问", ["summary"]),
    "chat": ("职业咨询 · 千问", ["chat"]),
    "ocr": ("简历 OCR · 千问视觉", ["ocr"]),
    "media_create": ("职业媒体创建 · 豆包", ["media_create"]),
    "media_status": ("职业视频状态 · 豆包", ["media_status"]),
}


def node(identifier: str, data: dict, index: int) -> dict:
    position = {"x": index * 340, "y": 100}
    return {"id": identifier, "type": "custom", "data": data, "position": position, "positionAbsolute": position, "width": 280, "height": 100, "sourcePosition": "right", "targetPosition": "left", "selected": False}


def code_node(identifier: str, title: str, code: str, variables: list, index: int) -> dict:
    return node(identifier, {"type": "code", "title": title, "code_language": "python3", "code": code, "variables": variables, "outputs": {"result": {"type": "string", "children": None}}}, index)


def variable(name: str, selector: list[str]) -> dict:
    return {"variable": name, "value_selector": selector, "value_type": "string"}


def workflow(operation: str, title: str, stages: list[str]) -> dict:
    nodes = [node("start", {"type": "start", "title": "任务输入", "variables": [{"variable": "payload", "label": "JSON 业务输入", "type": "paragraph", "required": True, "max_length": 8000000, "options": []}]}, 0)]
    for stage in stages:
        previous = nodes[-1]["id"]
        variables = [variable("payload", ["start", "payload"])]
        code = "import json\ndef main(payload: str) -> dict:\n    return {'result': json.dumps({'payload': json.loads(payload)}, ensure_ascii=False)}\n"
        if stage.endswith("_review"):
            variables.append(variable("draft", [previous, "result"]))
            code = "import json\ndef main(payload: str, draft: str) -> dict:\n    return {'result': json.dumps({'payload': json.loads(payload), 'previous': json.loads(draft)}, ensure_ascii=False)}\n"
        elif stage.endswith("_final"):
            draft_id = stages[0] + "_parsed"
            variables += [variable("draft", [draft_id, "result"]), variable("review", [previous, "result"])]
            code = "import json\ndef main(payload: str, draft: str, review: str) -> dict:\n    return {'result': json.dumps({'payload': json.loads(payload), 'previous': {'draft': json.loads(draft), 'review': json.loads(review)}}, ensure_ascii=False)}\n"
        nodes.append(code_node(stage + "_input", "准备 " + stage, code, variables, len(nodes)))
        nodes.append(node(stage + "_http", {
            "type": "http-request", "title": title if len(stages) == 1 else stage, "method": "POST",
            "url": "{{#env.AGENT_TOOLS_URL#}}/tools/" + stage,
            "authorization": {"type": "no-auth"},
            "headers": "Content-Type:application/json\nAuthorization:Bearer {{#env.AGENT_TOOLS_TOKEN#}}",
            "params": "", "body": {"type": "raw-text", "data": [{"id": "body", "key": "", "type": "text", "value": "{{#" + stage + "_input.result#}}"}]},
            "timeout": {"connect": 10, "read": 180, "write": 30},
            "retry_config": {"enabled": False, "max_retries": 0, "retry_interval": 1000},
        }, len(nodes)))
        nodes.append(code_node(stage + "_parsed", "检查工具输出", "import json\ndef main(body: str, status: int) -> dict:\n    if status != 200:\n        raise ValueError('Agent tool failed; inspect tool error_code')\n    data = json.loads(body)\n    return {'result': json.dumps(data['result'], ensure_ascii=False)}\n",
                               [variable("body", [stage + "_http", "body"]), {"variable": "status", "value_selector": [stage + "_http", "status_code"], "value_type": "number"}], len(nodes)))
    nodes.append(node("end", {"type": "end", "title": "业务结果", "outputs": [{"variable": "result", "value_selector": [nodes[-1]["id"], "result"], "value_type": "string"}]}, len(nodes)))
    edges = [{"id": first["id"] + "-" + second["id"], "type": "custom", "source": first["id"], "sourceHandle": "source", "target": second["id"], "targetHandle": "target", "data": {"sourceType": first["data"]["type"], "targetType": second["data"]["type"], "isInIteration": False, "isInLoop": False}} for first, second in zip(nodes, nodes[1:])]
    return {
        "version": "0.3.1", "kind": "app", "dependencies": [],
        "app": {"name": "CareerPilot / " + title, "description": "Dify 负责节点顺序与运行日志；本机工具服务负责供应商适配与强类型验证。HTTP 节点禁止自动重试。", "mode": "workflow", "icon": "🧭", "icon_background": "#F1F0EB", "use_icon_as_answer_icon": False},
        "workflow": {"conversation_variables": [], "environment_variables": [
            {"id": "tools-url", "name": "AGENT_TOOLS_URL", "value": "http://host.docker.internal:8091", "value_type": "string", "selector": ["env", "AGENT_TOOLS_URL"], "description": "本机工具服务地址"},
            {"id": "tools-token", "name": "AGENT_TOOLS_TOKEN", "value": "", "value_type": "secret", "selector": ["env", "AGENT_TOOLS_TOKEN"], "description": "从私有 tools.env 配置"},
        ], "features": {"file_upload": {"enabled": False}, "opening_statement": "", "retriever_resource": {"enabled": False}, "sensitive_word_avoidance": {"enabled": False}, "speech_to_text": {"enabled": False}, "suggested_questions": [], "suggested_questions_after_answer": {"enabled": False}, "text_to_speech": {"enabled": False}}, "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": .6}}},
    }


def main():
    destination = ROOT / "dify/workflows"
    destination.mkdir(parents=True, exist_ok=True)
    for operation, (title, stages) in OPERATIONS.items():
        (destination / f"{operation}.yml").write_text(json.dumps(workflow(operation, title, stages), ensure_ascii=False, indent=2) + "\n")
    print(f"Generated {len(OPERATIONS)} YAML-compatible JSON workflow files")


if __name__ == "__main__":
    main()
