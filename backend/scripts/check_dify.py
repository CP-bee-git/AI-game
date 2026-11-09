import asyncio
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient
import httpx

from app import main
from app.config import Settings
from app.services.agent_tools import AgentTools
from app.services.dify import DifyClient, OPERATIONS
from app.services.llm import CloudModelError
from app.services.session import _sessions
from app.services.storage import LocalStorage


class DifyChecks(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        keys = self.root / "keys.json"
        keys.write_text(json.dumps({operation: "app-test-" + operation for operation in OPERATIONS}))
        self.settings = Settings(_env_file=None, ai_backend="dify", dify_app_keys_file=keys,
                                 state_db_path=self.root / "state.db", local_storage_dir=self.root / "uploads",
                                 co_worker_db_path=self.root / "missing.db", qwen_api_key="test-qwen", deepseek_api_key="test-deepseek")

    def tearDown(self):
        self.directory.cleanup()

    def test_client_fails_closed_and_never_retries_paid_runs(self):
        for body in [{"data": {"status": "failed", "error": "app-secret"}}, {"data": {"status": "succeeded", "outputs": {"result": "bad"}}}]:
            calls = []
            def upstream(request):
                calls.append(request)
                return httpx.Response(200, json=body)
            client = DifyClient(self.settings, httpx.MockTransport(upstream))
            with self.assertRaises(CloudModelError) as error:
                asyncio.run(client.run("chat", {}))
            self.assertNotIn("app-secret", str(error.exception))
            self.assertEqual(len(calls), 1)
        client = DifyClient(self.settings, httpx.MockTransport(lambda request: httpx.Response(429)))
        with self.assertRaises(CloudModelError) as error:
            asyncio.run(client.run("chat", {}))
        self.assertEqual(error.exception.status_code, 429)

    def test_scoring_and_reports_use_assigned_providers_and_reject_false_evidence(self):
        calls = []
        names = ["教育描述", "技能证据", "项目表达", "实践经历", "求职目标"]
        def upstream(request):
            body = json.loads(request.content)
            calls.append((request.url.host, body))
            if request.url.host == "api.deepseek.com":
                result = {"dimensions": [{"name": name, "score": 50, "evidence": [{"block_id": "b1", "quote": "Python"}], "note": "原文明确提到Python"} for name in names]}
            else:
                result = {"strengths": ["已写明Python"], "must_fix": [], "optional_improve": ["核对项目职责"], "ats_keywords": ["Python"], "checklist": ["核对事实"]}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result, ensure_ascii=False)}}]})
        tools = AgentTools(self.settings, httpx.MockTransport(upstream))
        payload = {"blocks": [{"block_id": "b1", "text": "Python 项目"}]}
        result = asyncio.run(tools.execute("analysis", payload))
        self.assertEqual(len(result["dimensions"]), 5)
        asyncio.run(tools.execute("report", payload))
        self.assertEqual([host for host, body in calls], ["api.deepseek.com", "dashscope.aliyuncs.com"])
        self.assertEqual(calls[0][1]["temperature"], 0)
        with self.assertRaises(CloudModelError):
            asyncio.run(tools.execute("analysis", {"blocks": [{"block_id": "b1", "text": "Excel"}]}))

    def test_media_idempotency_conflict_status_and_consent(self):
        self.settings.media_enabled = True
        self.settings.ark_video_model = "seedance-test"
        self.settings.ark_api_key = "test-ark"
        calls = []
        def upstream(request):
            calls.append(request.method)
            return httpx.Response(200, json={"id": "video-task"} if request.method == "POST" else {"status": "succeeded", "content": {"video_url": "https://example.com/video.mp4"}})
        tools = AgentTools(self.settings, httpx.MockTransport(upstream))
        payload = {"owner": "browser-one", "request_id": "1234567890abcdef", "kind": "video", "prompt": "职业场景短片", "consent": True}
        first = asyncio.run(tools.execute("media_create", payload))
        second = asyncio.run(tools.execute("media_create", payload))
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(calls, ["POST"])
        completed = asyncio.run(tools.execute("media_status", payload))
        self.assertEqual(completed["status"], "succeeded")
        with self.assertRaises(CloudModelError) as error:
            asyncio.run(tools.execute("media_create", {**payload, "prompt": "其他职业场景"}))
        self.assertEqual(error.exception.status_code, 409)
        with self.assertRaises(CloudModelError):
            asyncio.run(tools.execute("media_status", {**payload, "owner": "browser-two"}))

    def test_business_flow_uses_dify_and_keeps_browser_resources_isolated(self):
        calls = []
        summaries = 0
        def upstream(request):
            nonlocal summaries
            operation = request.headers["authorization"].removeprefix("Bearer app-test-")
            body = json.loads(request.content)
            payload = json.loads(body["inputs"]["payload"])
            self.assertNotEqual(body["user"], "system")
            calls.append(operation)
            if operation == "profile":
                result = {"education": [], "skills": [{"name": "Python", "normalized_name": "Python"}], "projects": [], "experiences": [], "preferences": {}, "warnings": []}
            elif operation == "analysis":
                result = {"dimensions": [{"name": name, "score": 0, "evidence": [], "note": "缺少对应证据"} for name in ["教育描述", "技能证据", "项目表达", "实践经历", "求职目标"]]}
            elif operation == "match":
                result = {"results": [{"job_index": index, "skill_coverage": 80, "education_match": 50, "preference_fit": 100, "evidence": [], "reason": "根据已确认技能比较"} for index, job in enumerate(payload["jobs"])]}
            elif operation == "report":
                result = {"strengths": ["Python"], "must_fix": [], "optional_improve": ["补充职责"], "ats_keywords": ["Python"], "checklist": ["检查事实"]}
            elif operation == "questions":
                result = {"questions": [{"question": "请介绍一个具体项目及其结果。", "keywords": []} for index in range(4)]}
            elif operation == "evaluate":
                result = {"score": 4, "feedback": "说明了职责，还需可核验的结果。"}
            elif operation == "summary":
                summaries += 1
                if summaries == 1:
                    return httpx.Response(200, json={"data": {"status": "failed"}})
                result = {"summary": ["补充可以核验的项目结果。"]}
            elif operation == "chat":
                result = {"reply": "可以先谈谈你的求职方向。"}
            else:
                raise AssertionError(operation)
            return httpx.Response(200, json={"data": {"status": "succeeded", "outputs": {"result": json.dumps(result, ensure_ascii=False)}}})
        client = DifyClient(self.settings, httpx.MockTransport(upstream))
        original_settings, original_storage = main.settings, main.storage
        main.settings, main.storage = self.settings, LocalStorage(self.settings.local_storage_dir)
        main.configure_state()
        _sessions.clear()
        try:
            with patch("app.main.DifyClient", return_value=client), TestClient(main.app) as browser, TestClient(main.app) as other:
                document = Document()
                document.add_paragraph("使用Python完成项目。")
                data = BytesIO()
                document.save(data)
                upload = browser.post("/api/v1/resumes/upload", files={"file": ("resume.docx", data.getvalue())}, data={"privacy_acknowledged": "true"})
                self.assertEqual(upload.status_code, 201, upload.text)
                resume_id = upload.json()["resume_id"]
                profile = browser.post(f"/api/v1/resumes/{resume_id}/profile").json()
                confirmed = browser.post(f"/api/v1/resumes/{resume_id}/profile/confirm", json={name: profile[name] for name in ("education", "skills", "experiences", "projects", "preferences")})
                self.assertEqual(confirmed.status_code, 200)
                self.assertEqual(browser.get(f"/api/v1/resumes/{resume_id}/analysis").status_code, 200)
                self.assertEqual(other.get(f"/api/v1/resumes/{resume_id}/analysis").status_code, 404)
                jobset_id = browser.post("/api/v1/jobsets", json={"name": "测试"}).json()["jobset_id"]
                browser.post(f"/api/v1/jobsets/{jobset_id}/jobs/import", json={"jobs": [{"title": "开发", "required_skills": ["Python"]}]})
                match = browser.post("/api/v1/matches/run", json={"resume_id": resume_id, "jobset_id": jobset_id})
                self.assertEqual(match.status_code, 200, match.text)
                payload = {"resume_id": resume_id, "jobset_id": jobset_id, "job_title": "开发"}
                report = browser.post("/api/v1/reports/diagnosis", json=payload)
                self.assertEqual(report.status_code, 200, report.text)
                interview = browser.post("/api/v1/interviews", json=payload)
                self.assertEqual(interview.status_code, 201, interview.text)
                session_id = interview.json()["session_id"]
                for index in range(4):
                    answer = browser.post(f"/api/v1/interviews/{session_id}/answer", json={"answer": "我用Python完成了数据整理。"})
                    self.assertEqual(answer.status_code, 200, answer.text)
                self.assertEqual(answer.json()["status"], "completed")
                self.assertEqual(len(answer.json()["turns"]), 4)
                self.assertIn("已保存", answer.json()["summary"][0])
                retried = browser.post(f"/api/v1/interviews/{session_id}/summary")
                self.assertEqual(retried.json()["summary"], ["补充可以核验的项目结果。"])
                self.assertEqual(calls.count("evaluate"), 4)
                export = browser.post("/api/v1/exports", json={"type": "diagnosis", "resource_id": report.json()["report_id"], "format": "html"})
                self.assertEqual(export.status_code, 201, export.text)
                self.assertEqual(browser.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "你好"}]}).status_code, 200)
                self.assertEqual(calls.count("analysis"), 1)
                self.assertIn("summary", calls)
                self.assertEqual(browser.post("/api/v1/model/configure", json={"api_key": "sk-test-valid"}).status_code, 409)
        finally:
            main.settings, main.storage = original_settings, original_storage
            main.configure_state()
            _sessions.clear()

    def test_tool_endpoint_requires_secret_and_never_echoes_invalid_payload(self):
        from app import agent_api
        original = agent_api.settings.agent_tools_token
        agent_api.settings.agent_tools_token = "test-tool-token"
        try:
            with TestClient(agent_api.app) as client:
                self.assertEqual(client.post("/tools/analysis", json={"payload": {}}).status_code, 401)
                invalid = client.post("/tools/analysis", content='{"payload":"private-content"}', headers={"Authorization": "Bearer test-tool-token"})
                self.assertEqual(invalid.status_code, 422)
                self.assertNotIn("private-content", invalid.text)
        finally:
            agent_api.settings.agent_tools_token = original

    def test_workflow_files_have_auth_and_no_paid_retries(self):
        root = Path(__file__).resolve().parents[2] / "dify/workflows"
        for operation in OPERATIONS:
            data = json.loads((root / f"{operation}.yml").read_text())
            nodes = data["workflow"]["graph"]["nodes"]
            for node in nodes:
                if node["data"]["type"] == "http-request":
                    self.assertIn("AGENT_TOOLS_TOKEN", node["data"]["headers"])
                    self.assertFalse(node["data"]["retry_config"]["enabled"])
            self.assertEqual(nodes[-1]["data"]["outputs"][0]["variable"], "result")


if __name__ == "__main__":
    unittest.main(verbosity=2)
