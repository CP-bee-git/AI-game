import json
from io import BytesIO
from pathlib import Path
import time

from docx import Document
import httpx


ROOT = Path(__file__).resolve().parents[1]


def main():
    checks = []
    began = time.monotonic()
    with httpx.Client(base_url="http://127.0.0.1:8010/api/v1", timeout=300) as client:
        def call(name, method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if response.is_error:
                try:
                    code = response.json().get("error_code", "business_error")
                except ValueError:
                    code = "invalid_response"
                raise RuntimeError(f"{name}: HTTP {response.status_code} / {code}")
            checks.append({"check": name, "status": "passed"})
            print(name + ": PASS", flush=True)
            return response.json()

        status = call("orchestration", "GET", "/orchestration")
        if not all(status["workflows"].values()):
            raise RuntimeError("Dify workflows are not fully configured")
        document = Document()
        document.add_heading("合成演示简历，不是真实候选人", 0)
        document.add_paragraph("候选人：虚构候选人。2026年毕业于虚构大学计算机专业，本科学历。")
        document.add_paragraph("掌握Python、SQL，使用Python和SQL完成课程数据清洗项目。")
        document.add_paragraph("项目时间：2025年9月至2026年1月；个人职责：清洗1000条记录，检查缺失值，并编写SQL汇总查询。")
        document.add_paragraph("求职意向：上海数据分析实习岗位，可2026年7月到岗。")
        output = BytesIO()
        document.save(output)
        upload = call("upload", "POST", "/resumes/upload", files={"file": ("synthetic-dify-check.docx", output.getvalue())}, data={"privacy_acknowledged": "true"})
        resume_id = upload["resume_id"]
        profile = call("qwen_profile", "POST", f"/resumes/{resume_id}/profile")
        call("profile_confirm", "POST", f"/resumes/{resume_id}/profile/confirm", json={name: profile[name] for name in ("education", "skills", "experiences", "projects", "preferences")})
        analysis = call("deepseek_analysis_review_and_career_match", "GET", f"/resumes/{resume_id}/analysis")
        if len(analysis["dimensions"]) != 5 or len(analysis["careers"]["results"]) != 10:
            raise RuntimeError("Analysis shape invalid")
        jobset = call("jobset", "POST", "/jobsets", json={"name": "Dify真实链路合成岗位"})
        jobset_id = jobset["jobset_id"]
        call("jobs", "POST", f"/jobsets/{jobset_id}/jobs/import", json={"jobs": [{"title": "数据分析实习", "company": "虚构公司", "location": "上海", "education_required": "本科", "required_skills": ["Python", "SQL"], "synthetic": True}]})
        call("deepseek_job_match", "POST", "/matches/run", json={"resume_id": resume_id, "jobset_id": jobset_id})
        payload = {"resume_id": resume_id, "jobset_id": jobset_id, "job_title": "数据分析实习"}
        report = call("qwen_report_deepseek_review", "POST", "/reports/diagnosis", json=payload)
        call("report_html_export", "POST", "/exports", json={"type": "diagnosis", "resource_id": report["report_id"], "format": "html"})
        interview = call("qwen_interview_questions", "POST", "/interviews", json=payload)
        for index in range(6):
            if interview["status"] == "completed":
                break
            interview = call(f"deepseek_interview_answer_{index + 1}", "POST", f"/interviews/{interview['session_id']}/answer", json={"answer": "这是合成练习回答：我在课程项目中负责清洗1000条记录，先检查缺失值和重复记录，用Python处理，再用SQL汇总核对记录数。我只能确认这些课程实践；尚未在生产系统做过相关工作。"})
        if interview["status"] != "completed":
            raise RuntimeError("Interview did not finish")
        call("qwen_interview_summary", "POST", f"/interviews/{interview['session_id']}/summary")
        call("interview_json_export", "POST", "/exports", json={"type": "interview", "resource_id": interview["session_id"], "format": "json"})
        with httpx.Client(base_url="http://127.0.0.1:8010/api/v1") as other:
            if other.get(f"/resumes/{resume_id}/analysis").status_code != 404:
                raise RuntimeError("Browser session isolation failed")
        checks.append({"check": "browser_isolation", "status": "passed"})
    result = {"status": "passed", "synthetic_data": True, "uses_real_dify_and_models": True, "media_generation_submitted": False, "elapsed_seconds": round(time.monotonic() - began), "checks": checks}
    destination = ROOT / ".private/dify/live-check.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    destination.chmod(0o600)
    print("Complete real Dify chain: PASS", flush=True)


if __name__ == "__main__":
    main()
