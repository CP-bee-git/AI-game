from datetime import UTC, datetime
from io import BytesIO
import logging
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
import pymupdf

from app.config import get_settings
from app.schemas import (
    HealthResponse,
    DiagnosisRequest,
    DiagnosticReport,
    ExportArtifactResponse,
    ExportRequest,
    InterviewAnswerRequest,
    InterviewCreateRequest,
    InterviewSessionResponse,
    InterviewTurn,
    JobImportRequest,
    JobSetCreate,
    JobSetResponse,
    MatchResult,
    MatchRunRequest,
    MatchRunResponse,
    ModelConfigResponse,
    ModelConfigureRequest,
    ModelPingResponse,
    ProfileConfirmRequest,
    ProfileDraft,
    ResumeResponse,
    TaskStatus,
)
from app.services.llm import CloudModelError, QwenCloudProvider, model_config
from app.services.diagnosis import build_diagnosis
from app.services.diagnosis import generate_coaching
from app.services.demo import load_china_demo, make_demo_resume
from app.services.exporter import render_export
from app.services.analysis import profile_analysis
from app.services.careers import career_matches
from app.services.interview import build_questions, evaluate_answer, evaluate_answer_with_model, generate_questions
from app.services.matching import match_jobs
from app.services.profile import extract_profile
from app.services.resume import initial_resume_blocks
from app.services.state import SQLiteMap
from app.services.storage import LocalStorage
from app.services.session import BrowserSessionMiddleware, allow_configuration_attempt, clear_model_settings, model_settings, save_model_settings

settings = get_settings()
logger = logging.getLogger("careerpilot.api")
storage = LocalStorage(settings.local_storage_dir)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    BrowserSessionMiddleware,
    api_prefix=settings.api_prefix,
    public_paths=tuple(f"{settings.api_prefix}{path}" for path in ("/health", "/demo/china", "/demo/china/resume")),
)

def configure_state(path: Path | None = None) -> None:
    global _resume_blocks, _profiles, _jobsets, _interviews, _reports, _exports, _match_runs, _consents
    state_path = path or settings.state_db_path
    _resume_blocks = SQLiteMap(state_path, "resume_blocks")
    _profiles = SQLiteMap(state_path, "profiles")
    _jobsets = SQLiteMap(state_path, "jobsets")
    _interviews = SQLiteMap(state_path, "interviews")
    _reports = SQLiteMap(state_path, "reports")
    _exports = SQLiteMap(state_path, "exports")
    _match_runs = SQLiteMap(state_path, "match_runs")
    _consents = SQLiteMap(state_path, "consents")


configure_state()


def require_qwen_chat() -> None:
    if not model_settings(settings).qwen_chat_configured:
        raise HTTPException(status_code=503, detail="请先输入千问 / 阿里云百炼 API Key 并连接云模型")


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path == f"{settings.api_prefix}/model/configure":
        # Never include request inputs: validation errors may contain a submitted secret.
        return JSONResponse(status_code=422, content={"detail": "配置格式无效，请检查 API Key、地域及 qwen 模型名；不接受自定义 API 地址"})
    return JSONResponse(status_code=422, content={"detail": [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]})


@app.exception_handler(CloudModelError)
async def safe_cloud_error(request: Request, exc: CloudModelError):
    logger.warning("qwen_cloud_failed error_code=%s", exc.error_code)
    headers = {"Retry-After": "30"} if exc.error_code == "cloud_rate_limit" else None
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "error_code": exc.error_code}, headers=headers)


def _source_notice(profile: dict, job: dict) -> str | None:
    if profile.get("demo_dataset") == "china-campus-demo-v1" and job.get("synthetic"):
        return load_china_demo()["notice"]
    if job.get("synthetic"):
        return "当前目标岗位为用户提供的合成岗位；此标记不表示候选人简历为合成数据。匹配和反馈为基础规则结果。"
    return None


def _is_china_demo(profile: dict) -> bool:
    return profile.get("demo_dataset") == "china-campus-demo-v1"


def _validate_file(extension: str, content: bytes) -> None:
    if extension in {".png", ".jpg", ".jpeg"}:
        expected_format = "PNG" if extension == ".png" else "JPEG"
        try:
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                if image.format != expected_format:
                    raise HTTPException(status_code=415, detail=f"File content does not match {extension}")
                if width * height > 25_000_000:
                    raise HTTPException(status_code=413, detail="Image exceeds the 25-megapixel processing limit")
                image.verify()
        except HTTPException:
            raise
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise HTTPException(status_code=415, detail=f"File content is not a valid {expected_format} image") from exc
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="File content is not a PDF")
        try:
            with pymupdf.open(stream=content, filetype="pdf") as document:
                if document.page_count > 20:
                    raise HTTPException(status_code=413, detail="PDF exceeds the 20-page processing limit")
                scale = 200 / 72
                total_pixels = sum(page.rect.width * page.rect.height * scale * scale for page in document)
                if total_pixels > 120_000_000:
                    raise HTTPException(status_code=413, detail="PDF exceeds the 120-megapixel OCR budget")
                if any(page.rect.width * page.rect.height * scale * scale > 25_000_000 for page in document):
                    raise HTTPException(status_code=413, detail="PDF page exceeds the 25-megapixel OCR limit")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=415, detail="File content is not a readable PDF") from exc
    if extension == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                valid_docx = "word/document.xml" in archive.namelist()
                safe_size = len(archive.infolist()) <= 2000 and sum(item.file_size for item in archive.infolist()) <= 30 * 1024 * 1024
        except BadZipFile:
            valid_docx = False
            safe_size = False
        if valid_docx and not safe_size:
            raise HTTPException(status_code=413, detail="DOCX expands beyond the 30 MB processing limit")
        if not valid_docx:
            raise HTTPException(status_code=415, detail="File content is not a DOCX document")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}


@app.get(f"{settings.api_prefix}/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(service=settings.app_name, environment=settings.app_env)


@app.get(f"{settings.api_prefix}/model-config", response_model=ModelConfigResponse)
async def model_configuration() -> ModelConfigResponse:
    return ModelConfigResponse(**model_config(model_settings(settings)))


@app.post(f"{settings.api_prefix}/model/configure", response_model=ModelConfigResponse)
async def configure_model(payload: ModelConfigureRequest, request: Request) -> ModelConfigResponse:
    if not allow_configuration_attempt(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="连接尝试过于频繁，请一分钟后重试", headers={"Retry-After": "60"})
    candidate = settings.model_copy(update={
        "qwen_api_key": payload.api_key.get_secret_value(),
        "qwen_region": payload.region,
        "qwen_chat_model": payload.model,
    })
    try:
        await QwenCloudProvider(candidate).ping()
    except CloudModelError:
        raise
    except Exception as exc:
        logger.warning("qwen_cloud_configuration_failed error=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="千问云 API 验证失败，请检查 API Key 所属地域、模型权限、余额及网络连接；原配置未更改") from None
    save_model_settings(candidate)
    return ModelConfigResponse(**model_config(candidate))


@app.delete(f"{settings.api_prefix}/model/configure", response_model=ModelConfigResponse)
async def disconnect_model() -> ModelConfigResponse:
    clear_model_settings()
    return ModelConfigResponse(**model_config(model_settings(settings)))


@app.post(f"{settings.api_prefix}/model/ping", response_model=ModelPingResponse)
async def model_ping() -> ModelPingResponse:
    require_qwen_chat()
    try:
        models = await QwenCloudProvider(model_settings(settings)).ping()
    except CloudModelError:
        raise
    except Exception as exc:
        logger.warning("qwen_cloud_ping_failed error=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="无法连接千问云 API，请检查 API Key、地域、模型权限及余额") from None
    return ModelPingResponse(
        status="ok",
        provider="阿里云百炼 · 千问",
        model=model_settings(settings).qwen_chat_model,
        models=models,
    )


@app.post(f"{settings.api_prefix}/resumes/upload", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    privacy_acknowledged: bool = Form(default=False),
) -> ResumeResponse:
    if not privacy_acknowledged:
        raise HTTPException(status_code=400, detail="请先阅读并确认数据处理说明")
    filename = Path(file.filename or "resume").name
    extension = Path(filename).suffix.lower()
    if extension not in settings.allowed_extensions:
        raise HTTPException(status_code=415, detail=f"Unsupported file extension: {extension or 'none'}")

    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds MAX_UPLOAD_BYTES")
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    _validate_file(extension, content)

    resume_id = uuid4()
    destination = storage.save(resume_id, filename, content)
    try:
        vision_ocr = QwenCloudProvider(model_settings(settings)).vision_ocr if model_settings(settings).qwen_vision_configured else None
        _resume_blocks[resume_id] = await run_in_threadpool(initial_resume_blocks, destination, file.content_type or "", vision_ocr)
    except CloudModelError:
        storage.delete(destination)
        raise
    except RuntimeError:
        storage.delete(destination)
        raise HTTPException(status_code=503, detail="图片或扫描 PDF 需要已连接、具有多模态权限的千问云 API，请检查配置后重试") from None
    except Exception as exc:
        storage.delete(destination)
        logger.warning("resume_parse_failed resume_id=%s", resume_id)
        raise HTTPException(status_code=502, detail="千问云 Qwen-VL 简历识别失败，请检查 API Key 的多模态模型权限、余额及网络连接。") from exc
    _consents[resume_id] = {"policy_version": "preview-2026-10", "acknowledged_at": datetime.now(UTC).isoformat()}
    task = TaskStatus(
        task_id=uuid4(),
        status="succeeded",
        progress=100,
        message="文件接收和基础文本解析完成；可以生成能力画像。",
    )
    return ResumeResponse(
        resume_id=resume_id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        status="uploaded",
        task=task,
        created_at=datetime.now(UTC),
    )


@app.get(f"{settings.api_prefix}/resumes/{{resume_id}}/blocks")
async def resume_blocks(resume_id: UUID) -> dict[str, object]:
    blocks = _resume_blocks.get(resume_id)
    if blocks is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"resume_id": resume_id, "blocks": blocks}


@app.post(f"{settings.api_prefix}/resumes/{{resume_id}}/profile", response_model=ProfileDraft)
async def resume_profile(resume_id: UUID) -> ProfileDraft:
    blocks = _resume_blocks.get(resume_id)
    if blocks is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    if not any(block.get("text") and not str(block.get("block_id", "")).startswith("ocr_empty") for block in blocks):
        raise HTTPException(status_code=422, detail="Resume has no extractable text; OCR is required")
    require_qwen_chat()
    try:
        payload = await extract_profile(resume_id, blocks, QwenCloudProvider(model_settings(settings)))
        _profiles[resume_id] = payload
        return ProfileDraft.model_validate(payload)
    except HTTPException:
        raise
    except CloudModelError:
        raise
    except Exception as exc:
        logger.warning("profile_generation_failed resume_id=%s model=%s", resume_id, model_settings(settings).qwen_chat_model)
        raise HTTPException(status_code=502, detail="千问云 API 返回内容无效或服务不可用，请检查模型权限、余额及 JSON 输出能力。") from exc


@app.get(f"{settings.api_prefix}/resumes/{{resume_id}}/profile", response_model=ProfileDraft)
async def get_resume_profile(resume_id: UUID) -> ProfileDraft:
    profile = _profiles.get(resume_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileDraft.model_validate(profile)


@app.post(f"{settings.api_prefix}/resumes/{{resume_id}}/profile/confirm", response_model=ProfileDraft)
async def confirm_resume_profile(resume_id: UUID, request: ProfileConfirmRequest) -> ProfileDraft:
    if resume_id not in _resume_blocks:
        raise HTTPException(status_code=404, detail="Resume not found")
    profile = {
        "resume_id": resume_id,
        "status": "confirmed",
        **request.model_dump(),
        "warnings": _profiles.get(resume_id, {}).get("warnings", []),
        "demo_dataset": _profiles.get(resume_id, {}).get("demo_dataset"),
    }
    _profiles[resume_id] = profile
    return ProfileDraft.model_validate(profile)


def _analysis_for(resume_id: UUID) -> dict:
    profile = _profiles.get(resume_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="未找到当前浏览器的画像")
    if profile.get("status") != "confirmed":
        raise HTTPException(status_code=409, detail="请先确认画像，再查看星级分析与职业匹配")
    return {
        "resume_id": str(resume_id),
        **profile_analysis(profile, _resume_blocks.get(resume_id, [])),
        "data_notice": load_china_demo()["notice"] if _is_china_demo(profile) else "依据用户确认的简历画像生成；个人自述和资历未经过第三方核验。",
        "careers": career_matches(profile, limit=10),
    }


@app.get(f"{settings.api_prefix}/resumes/{{resume_id}}/analysis")
async def get_profile_analysis(resume_id: UUID) -> dict:
    return _analysis_for(resume_id)


@app.post(f"{settings.api_prefix}/jobsets", response_model=JobSetResponse, status_code=201)
async def create_jobset(request: JobSetCreate) -> JobSetResponse:
    jobset_id = uuid4()
    _jobsets[jobset_id] = {"name": request.name, "jobs": []}
    return JobSetResponse(jobset_id=jobset_id, name=request.name, jobs=[])


@app.post(f"{settings.api_prefix}/jobsets/{{jobset_id}}/jobs/import", response_model=JobSetResponse)
async def import_jobs(jobset_id: UUID, request: JobImportRequest) -> JobSetResponse:
    jobset = _jobsets.get(jobset_id)
    if jobset is None:
        raise HTTPException(status_code=404, detail="Job set not found")
    jobset["jobs"] = [job.model_dump() for job in request.jobs]
    _jobsets[jobset_id] = jobset
    return JobSetResponse(jobset_id=jobset_id, name=jobset["name"], jobs=request.jobs)


@app.get(f"{settings.api_prefix}/jobsets/{{jobset_id}}", response_model=JobSetResponse)
async def get_jobset(jobset_id: UUID) -> JobSetResponse:
    jobset = _jobsets.get(jobset_id)
    if jobset is None:
        raise HTTPException(status_code=404, detail="Job set not found")
    return JobSetResponse(jobset_id=jobset_id, name=jobset["name"], jobs=jobset["jobs"])


@app.post(f"{settings.api_prefix}/matches/run", response_model=MatchRunResponse)
async def run_matches(request: MatchRunRequest) -> MatchRunResponse:
    profile = _profiles.get(request.resume_id)
    jobset = _jobsets.get(request.jobset_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.get("status") != "confirmed":
        raise HTTPException(status_code=409, detail="Confirm the profile before matching")
    if jobset is None:
        raise HTTPException(status_code=404, detail="Job set not found")
    jobs = jobset["jobs"]
    results = [MatchResult.model_validate(item) for item in match_jobs(profile, jobs)]
    _match_runs[f"{request.resume_id}:{request.jobset_id}"] = [result.model_dump(mode="json") for result in results]
    return MatchRunResponse(resume_id=request.resume_id, jobset_id=request.jobset_id, results=results)


@app.post(f"{settings.api_prefix}/reports/diagnosis", response_model=DiagnosticReport)
async def create_diagnosis(request: DiagnosisRequest) -> DiagnosticReport:
    profile = _profiles.get(request.resume_id)
    jobset = _jobsets.get(request.jobset_id)
    if profile is None or profile.get("status") != "confirmed":
        raise HTTPException(status_code=409, detail="Confirm the profile before diagnosis")
    if jobset is None:
        raise HTTPException(status_code=404, detail="Job set not found")
    job = next((item for item in jobset["jobs"] if item["title"] == request.job_title), None)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    previous_run = _match_runs.get(f"{request.resume_id}:{request.jobset_id}", [])
    result = next((item for item in previous_run if item["job_title"] == request.job_title), None)
    if result is None:
        result = match_jobs(profile, [job])[0]
    report = build_diagnosis(uuid4(), job, result)
    if model_settings(settings).qwen_chat_configured:
        try:
            advice = await generate_coaching(profile, job, result, QwenCloudProvider(model_settings(settings)))
            report["optional_improve"] = advice.optional_improve or report["optional_improve"]
            report["checklist"] = advice.checklist or report["checklist"]
            report["engine"] = "model"
        except CloudModelError:
            raise
        except Exception as exc:
            logger.warning("qwen_diagnosis_failed resume_id=%s model=%s", request.resume_id, model_settings(settings).qwen_chat_model)
            raise HTTPException(status_code=502, detail="千问云 API 诊断建议生成失败，请检查 API Key、地域及模型权限") from exc
    elif not _is_china_demo(profile):
        require_qwen_chat()
    report["notice"] = _source_notice(profile, job)
    report["profile_analysis"] = profile_analysis(profile, _resume_blocks.get(request.resume_id, []))
    _reports[report["report_id"]] = report
    return DiagnosticReport.model_validate(report)


@app.post(f"{settings.api_prefix}/interviews", response_model=InterviewSessionResponse, status_code=201)
async def create_interview(request: InterviewCreateRequest) -> InterviewSessionResponse:
    profile = _profiles.get(request.resume_id)
    jobset = _jobsets.get(request.jobset_id)
    if profile is None or profile.get("status") != "confirmed":
        raise HTTPException(status_code=409, detail="Confirm the profile before interview")
    if jobset is None:
        raise HTTPException(status_code=404, detail="Job set not found")
    job = next((item for item in jobset["jobs"] if item["title"] == request.job_title), None)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    engine = "rules"
    if model_settings(settings).qwen_chat_configured:
        try:
            questions = await generate_questions(profile, job, QwenCloudProvider(model_settings(settings)))
            engine = "model"
        except CloudModelError:
            raise
        except Exception as exc:
            logger.warning("qwen_interview_question_generation_failed resume_id=%s model=%s", request.resume_id, model_settings(settings).qwen_chat_model)
            raise HTTPException(status_code=502, detail="千问云 API 面试题生成失败，请检查 API Key、地域及模型权限和 JSON 输出能力") from exc
    elif _is_china_demo(profile):
        questions = build_questions(job)
    else:
        require_qwen_chat()
    session_id = uuid4()
    _interviews[session_id] = {
        "job_title": job["title"],
        "profile_analysis": profile_analysis(profile, _resume_blocks.get(request.resume_id, [])),
        "notice": _source_notice(profile, job),
        "engine": engine,
        "questions": questions,
        "turns": [],
        "index": 0,
        "status": "active",
        "summary": [],
    }
    return _interview_response(session_id)


def _interview_response(session_id: UUID) -> InterviewSessionResponse:
    session = _interviews[session_id]
    turns = [InterviewTurn.model_validate(turn) for turn in session["turns"]]
    current = None
    if session["status"] == "active":
        current = session["questions"][session["index"]]["question"]
    scores = [turn.score for turn in turns if turn.score is not None]
    return InterviewSessionResponse(
        session_id=session_id,
        job_title=session["job_title"],
        status=session["status"],
        current_question=current,
        turns=turns,
        overall_score=round(sum(scores) / len(scores), 2) if scores else None,
        summary=session["summary"],
        notice=session.get("notice"),
        engine=session.get("engine", "rules"),
    )


@app.get(f"{settings.api_prefix}/interviews/{{session_id}}", response_model=InterviewSessionResponse)
async def get_interview(session_id: UUID) -> InterviewSessionResponse:
    if session_id not in _interviews:
        raise HTTPException(status_code=404, detail="Interview session not found")
    return _interview_response(session_id)


@app.post(f"{settings.api_prefix}/interviews/{{session_id}}/answer", response_model=InterviewSessionResponse)
async def answer_interview(session_id: UUID, request: InterviewAnswerRequest) -> InterviewSessionResponse:
    session = _interviews.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session["status"] == "completed":
        raise HTTPException(status_code=409, detail="Interview is already completed")
    question = session["questions"][session["index"]]
    if session.get("engine") == "model":
        require_qwen_chat()
        try:
            evaluation = await evaluate_answer_with_model(request.answer, question, QwenCloudProvider(model_settings(settings)))
            score, feedback = evaluation.score, evaluation.feedback
        except CloudModelError:
            raise
        except Exception as exc:
            logger.warning("qwen_interview_answer_evaluation_failed session_id=%s model=%s", session_id, model_settings(settings).qwen_chat_model)
            raise HTTPException(status_code=502, detail="千问云 API 面试回答评价失败，请检查 API Key、地域及模型权限") from exc
    else:
        score, feedback = evaluate_answer(request.answer, question)
    session["turns"].append({
        "sequence": session["index"] + 1,
        "question": question["question"],
        "answer": request.answer,
        "score": score,
        "feedback": feedback,
    })
    session["index"] += 1
    if session["index"] >= len(session["questions"]):
        session["status"] = "completed"
        if session.get("engine") == "model":
            session["summary"] = ["面试问题和回答反馈由千问云 API 生成，属于求职练习意见，不验证技术正确性或经历真实性。", "建议对照原始项目材料核验回答内容，并由本人决定是否采用修改建议。"]
        else:
            session["summary"] = ["当前为规则演示评分，仅检查关键词、回答长度和数字；不验证技术正确性或经历真实性。", "请优先补充回答中的项目职责和可核验结果，完整语义评价待模型接入后验证。"]
    _interviews[session_id] = session
    return _interview_response(session_id)


@app.post(f"{settings.api_prefix}/exports", response_model=ExportArtifactResponse, status_code=201)
async def create_export(request: ExportRequest) -> ExportArtifactResponse:
    if request.type == "profile":
        data = _analysis_for(request.resource_id)
    elif request.type == "diagnosis":
        report = _reports.get(request.resource_id)
        data = DiagnosticReport.model_validate(report).model_dump(mode="json") if report else None
        if data is not None and report.get("profile_analysis"):
            data["profile_analysis"] = report["profile_analysis"]
    else:
        data = _interview_response(request.resource_id).model_dump(mode="json") if request.resource_id in _interviews else None
        if data is not None and _interviews[request.resource_id].get("profile_analysis"):
            data["profile_analysis"] = _interviews[request.resource_id]["profile_analysis"]
    if data is None:
        raise HTTPException(status_code=404, detail="Export source not found")
    export_id = uuid4()
    filename, content_type, content = render_export(data, request.type, request.format)
    artifact = {"export_id": export_id, "filename": filename, "content_type": content_type, "content": content}
    _exports[export_id] = artifact
    return ExportArtifactResponse.model_validate(artifact)


@app.get(f"{settings.api_prefix}/exports/{{export_id}}", response_model=ExportArtifactResponse)
async def get_export(export_id: UUID) -> ExportArtifactResponse:
    artifact = _exports.get(export_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Export not found")
    return ExportArtifactResponse.model_validate(artifact)


@app.get(f"{settings.api_prefix}/demo/china")
async def china_demo() -> dict:
    data = load_china_demo()
    return {**data, "resume_text": "\n\n".join(data["resume_paragraphs"])}


@app.get(f"{settings.api_prefix}/demo/china/resume")
async def download_china_resume() -> Response:
    return Response(
        make_demo_resume(load_china_demo()),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="CAND-001-synthetic-resume.docx"'},
    )


@app.post(f"{settings.api_prefix}/demo/china/start", status_code=201)
async def start_china_demo() -> dict:
    data = load_china_demo()
    resume_id, jobset_id = uuid4(), uuid4()
    content = make_demo_resume(data)
    filename = "CAND-001-synthetic-resume.docx"
    destination = storage.save(resume_id, filename, content)
    _resume_blocks[resume_id] = initial_resume_blocks(destination, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    profile = ProfileDraft.model_validate({**data["profile"], "resume_id": resume_id})
    _profiles[resume_id] = {**profile.model_dump(), "demo_dataset": data["dataset_id"]}
    jobset = JobSetResponse(jobset_id=jobset_id, name="中国内地·合成校园岗位（10条）", jobs=data["jobs"])
    _jobsets[jobset_id] = {"name": jobset.name, "jobs": [job.model_dump() for job in jobset.jobs]}
    resume = ResumeResponse(
        resume_id=resume_id, filename=filename, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=len(content), status="uploaded", created_at=datetime.now(UTC),
        task=TaskStatus(task_id=uuid4(), status="succeeded", progress=100, message="合成DOCX已实际解析；画像为人工预置样例，不是模型返回。"),
    )
    return {"notice": data["notice"], "resume": resume, "profile": profile, "jobset": jobset}

