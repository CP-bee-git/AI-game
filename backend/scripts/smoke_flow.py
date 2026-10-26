"""Run the first-round B2 workflow without a real cloud API key."""

from io import BytesIO
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient

from app import main


def make_docx() -> bytes:
    document = Document()
    document.add_heading("脱敏候选人简历", 0)
    document.add_paragraph("使用 Python 和 SQL 完成数据分析项目，处理 10 万条数据。")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def run() -> None:
    main.settings.openai_api_key = "smoke-test-key"
    main._resume_blocks.clear()
    main._profiles.clear()
    main._jobsets.clear()
    main._interviews.clear()
    main._reports.clear()
    main._exports.clear()
    async def fake_profile(resume_id, blocks, provider):
        return {
            "resume_id": resume_id,
            "status": "awaiting_confirmation",
            "education": [{"degree": "本科"}],
            "skills": [{"name": "Python", "normalized_name": "python"}, {"name": "SQL", "normalized_name": "sql"}],
            "experiences": [],
            "projects": [{"name": "数据分析项目"}],
            "preferences": {"cities": ["上海"]},
            "warnings": [],
        }

    with patch("app.main.extract_profile", fake_profile):
        client = TestClient(main.app)
        upload = client.post(
            "/api/v1/resumes/upload",
            files={"file": ("resume.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert upload.status_code == 201, upload.text
        resume_id = upload.json()["resume_id"]

        draft = client.post(f"/api/v1/resumes/{resume_id}/profile")
        assert draft.status_code == 200, draft.text
        confirmed = client.post(f"/api/v1/resumes/{resume_id}/profile/confirm", json=draft.json())
        assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed", confirmed.text

        jobset = client.post("/api/v1/jobsets", json={"name": "烟测岗位"})
        assert jobset.status_code == 201, jobset.text
        jobset_id = jobset.json()["jobset_id"]
        imported = client.post(f"/api/v1/jobsets/{jobset_id}/jobs/import", json={"jobs": [{
            "title": "数据分析师", "company": "示例公司", "location": "上海", "education_required": "本科",
            "required_skills": ["Python", "SQL"],
        }]})
        assert imported.status_code == 200, imported.text

        matches = client.post("/api/v1/matches/run", json={"resume_id": resume_id, "jobset_id": jobset_id})
        assert matches.status_code == 200 and matches.json()["results"][0]["eligible"], matches.text
        diagnosis = client.post("/api/v1/reports/diagnosis", json={"resume_id": resume_id, "jobset_id": jobset_id, "job_title": "数据分析师"})
        assert diagnosis.status_code == 200, diagnosis.text
        report_id = diagnosis.json()["report_id"]

        interview = client.post("/api/v1/interviews", json={"resume_id": resume_id, "jobset_id": jobset_id, "job_title": "数据分析师"})
        assert interview.status_code == 201, interview.text
        session = interview.json()
        while session["status"] == "active":
            answer = client.post(f"/api/v1/interviews/{session['session_id']}/answer", json={
                "answer": "我负责项目的数据清洗、分析和结果落地，使用 Python 与 SQL 处理 10 万条数据，最终提升报表效率 30%。",
            })
            assert answer.status_code == 200, answer.text
            session = answer.json()

        diagnosis_export = client.post("/api/v1/exports", json={"type": "diagnosis", "resource_id": report_id, "format": "json"})
        assert diagnosis_export.status_code == 201 and "数据分析师" in diagnosis_export.json()["content"], diagnosis_export.text
        interview_export = client.post("/api/v1/exports", json={"type": "interview", "resource_id": session["session_id"], "format": "html"})
        assert interview_export.status_code == 201 and "模拟面试反馈" in interview_export.json()["content"], interview_export.text

    print("B2 first-round flow: PASS")


if __name__ == "__main__":
    run()

