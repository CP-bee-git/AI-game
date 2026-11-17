import hashlib
from datetime import UTC, datetime
from io import BytesIO
import json
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
    ChatRequest,
    ChatResponse,
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
    ResumeDraftRequest,
    ResumeDraftUpdateRequest,
    ResumeGuidanceRequest,
    ResumeRewriteRequest,
    ScenarioRunCreateRequest,
    TaskStatus,
)
from app.services.llm import CloudModelError, QwenCloudProvider, model_config
from app.services.diagnosis import build_diagnosis
from app.services.diagnosis import generate_coaching
from app.services.demo import load_china_demo, make_demo_resume
from app.services.exporter import render_export
from app.services.analysis import profile_analysis
from app.services.careers import career_matches
from app.services.chat import CHAT_SYSTEM_PROMPT
from app.services.interview import (
    build_questions,
    evaluate_answer,
    evaluate_answer_with_model,
    generate_questions,
)
from app.services.matching import match_jobs
from app.services.profile import extract_profile
from app.services.resume import initial_resume_blocks
from app.services.resume_docs import (
    collect_confirmed_facts,
    draft_placeholders,
    generate_guidance,
    generate_resume_draft,
    rewrite_blocks,
    validate_rewrite,
)
from app.services.scenarios import ScenarioInput, run_scenario
from app.services.state import SQLiteMap
from app.services.storage import LocalStorage
from app.services.session import BrowserSessionMiddleware, allow_configuration_attempt, clear_model_settings, model_settings, save_model_settings
from app.services.agent_contracts import MediaCreate, ReportContent, Summary
from app.services.dify import DifyClient
from app.services.dify_business import analyze as dify_analyze, score_matches
from app.services.interview import AnswerEvaluation, InterviewPlan
from app.services.profile import ProfilePayload
from app.services.session import current_session

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
    global _resume_blocks, _profiles, _jobsets, _interviews, _reports, _exports, _match_runs, _consents, _analyses, _media, _resume_guidance, _resume_drafts, _scenario_runs
    state_path = path or settings.state_db_path
    _resume_blocks = SQLiteMap(state_path, "resume_blocks")
    _profiles = SQLiteMap(state_path, "profiles")
    _jobsets = SQLiteMap(state_path, "jobsets")
    _interviews = SQLiteMap(state_path, "interviews")
    _reports = SQLiteMap(state_path, "reports")
    _exports = SQLiteMap(state_path, "exports")
    _match_runs = SQLiteMap(state_path, "match_runs")
    _consents = SQLiteMap(state_path, "consents")
    _analyses = SQLiteMap(state_path, "analyses")
    _media = SQLiteMap(state_path, "media")
    _resume_guidance = SQLiteMap(state_path, "resume_guidance")
    _resume_drafts = SQLiteMap(state_path, "resume_drafts")
    _scenario_runs = SQLiteMap(state_path, "scenario_runs")


configure_state()


def require_qwen_chat() -> None:
    if settings.ai_backend == "dify":
        if not DifyClient(settings).configured("chat"):
            raise HTTPException(status_code=503, detail="请先发布并配置 Dify 工作流")
        return
    if not model_settings(settings).qwen_chat_configured:
        raise HTTPException(status_code=503, detail="请先输入千问 / 阿里云百炼 API Key 并连接云模型")


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path == f"{settings.api_prefix}/model/configure":
        # Never include request inputs: validation errors may contain a submitted secret.
        fields = {error['loc'][-1] for error in exc.errors() if error.get('loc')}
        if 'api_key' in fields:
            detail = "API Key 格式无效：请复制完整密钥，去除内部空格和换行；支持新版工作空间 Key。"
        elif 'region' in fields:
            detail = "服务区域无效：请选择中国内地或新加坡，并与创建 Key 的地域一致。"
        elif 'model' in fields:
            detail = "模型名称无效：请填写 qwen 开头的模型名称，例如 qwen-plus。"
        else:
            detail = "配置格式无效：仅接受 API Key、地域和模型名，请勿添加自定义 API 地址。"
        return JSONResponse(status_code=422, content={"detail": detail, "error_code": "invalid_configuration"})
    return JSONResponse(status_code=422, content={"detail": [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]})


@app.exception_handler(CloudModelError)
async def safe_cloud_error(request: Request, exc: CloudModelError):
    logger.warning("ai_backend_failed error_code=%s", exc.error_code)
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
    if settings.ai_backend == "dify":
        client = DifyClient(settings)
        return ModelConfigResponse(backend="dify", provider="Dify · 多模型协作", model="DeepSeek 评分 / 千问报告", image_ocr="千问视觉工作流", matching="DeepSeek 多维评分 + 可核对证据", chat_configured=client.configured("chat"), vision_configured=client.configured("ocr"))
    return ModelConfigResponse(**model_config(model_settings(settings)))


@app.post(f"{settings.api_prefix}/model/configure", response_model=ModelConfigResponse)
async def configure_model(payload: ModelConfigureRequest, request: Request) -> ModelConfigResponse:
    if settings.ai_backend == "dify":
        raise HTTPException(status_code=409, detail="当前为 Dify 模式，模型凭据由服务端管理员配置；此页面不接收供应商 Key。")
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
    if settings.ai_backend == "dify":
        raise HTTPException(status_code=409, detail="Dify 服务连接由管理员管理。")
    clear_model_settings()
    return ModelConfigResponse(**model_config(model_settings(settings)))


@app.post(f"{settings.api_prefix}/model/ping", response_model=ModelPingResponse)
async def model_ping() -> ModelPingResponse:
    if settings.ai_backend == "dify":
        await DifyClient(settings).run("chat", {"messages": [{"role": "user", "content": "只回复：连接正常"}]}, ChatResponse)
        return ModelPingResponse(status="ok", provider="Dify", model="千问工作流", models=["千问工作流"])
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


@app.post(f"{settings.api_prefix}/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    if settings.ai_backend == "dify":
        return await DifyClient(settings).run("chat", payload.model_dump(), ChatResponse)
    require_qwen_chat()
    return await QwenCloudProvider(model_settings(settings)).chat_json(
        CHAT_SYSTEM_PROMPT,
        json.dumps([message.model_dump() for message in payload.messages], ensure_ascii=False),
        ChatResponse,
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
        if settings.ai_backend == "dify":
            import asyncio
            import base64
            async def run_ocr(image: bytes, media_type: str) -> str:
                with Image.open(BytesIO(image)) as source:
                    page_image = source.convert("RGB")
                    page_image.thumbnail((2400, 2400))
                    output = BytesIO()
                    page_image.save(output, format="JPEG", quality=88)
                result = await DifyClient(settings).run("ocr", {"image_base64": base64.b64encode(output.getvalue()).decode(), "media_type": "image/jpeg"})
                return str(result.get("text", ""))
            def vision_ocr(image: bytes, media_type: str) -> str:
                return asyncio.run(run_ocr(image, media_type))
        else:
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
    if settings.ai_backend != "dify":
        require_qwen_chat()
    try:
        if settings.ai_backend == "dify":
            extracted = await DifyClient(settings).run("profile", {"blocks": blocks}, ProfilePayload)
            payload = {"resume_id": str(resume_id), "status": "awaiting_confirmation", **extracted.model_dump()}
        else:
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
    revision = hashlib.sha256(json.dumps(request.model_dump(), ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]
    profile = {
        "resume_id": resume_id,
        "status": "confirmed",
        **request.model_dump(),
        "source_revision": revision,
        "warnings": _profiles.get(resume_id, {}).get("warnings", []),
        "demo_dataset": _profiles.get(resume_id, {}).get("demo_dataset"),
    }
    _profiles[resume_id] = profile
    _analyses.pop(resume_id, None)
    for key in list(_match_runs):
        if key.startswith(f"{resume_id}:"):
            del _match_runs[key]
    return ProfileDraft.model_validate(profile)


async def _analysis_for(resume_id: UUID) -> dict:
    profile = _profiles.get(resume_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="未找到当前浏览器的画像")
    if profile.get("status") != "confirmed":
        raise HTTPException(status_code=409, detail="请先确认画像，再查看星级分析与职业匹配")
    if settings.ai_backend == "dify" and not _is_china_demo(profile):
        cached = _analyses.get(resume_id)
        if cached is None:
            cached = {"resume_id": str(resume_id), **await dify_analyze(DifyClient(settings), profile, _resume_blocks.get(resume_id, []))}
            _analyses[resume_id] = cached
        return cached
    return {
        "resume_id": str(resume_id),
        **profile_analysis(profile, _resume_blocks.get(resume_id, [])),
        "data_notice": load_china_demo()["notice"] if _is_china_demo(profile) else "依据用户确认的简历画像生成；个人自述和资历未经过第三方核验。",
        "careers": career_matches(profile, limit=10),
    }


@app.get(f"{settings.api_prefix}/resumes/{{resume_id}}/analysis")
async def get_profile_analysis(resume_id: UUID) -> dict:
    return await _analysis_for(resume_id)


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
    for key in list(_match_runs):
        if key.endswith(f":{jobset_id}"):
            del _match_runs[key]
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
    if settings.ai_backend == "dify" and not _is_china_demo(profile):
        scored = await score_matches(DifyClient(settings), profile, _resume_blocks.get(request.resume_id, []), jobs)
    else:
        scored = match_jobs(profile, jobs)
    results = [MatchResult.model_validate(item) for item in scored]
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
    if result is None and settings.ai_backend == "dify" and not _is_china_demo(profile):
        result = (await score_matches(DifyClient(settings), profile, _resume_blocks.get(request.resume_id, []), [job]))[0]
    elif result is None:
        result = match_jobs(profile, [job])[0]
    report = build_diagnosis(uuid4(), job, result)
    if settings.ai_backend == "dify" and not _is_china_demo(profile):
        generated = await DifyClient(settings).run("report", {"profile": profile, "blocks": _resume_blocks.get(request.resume_id, []), "job": job, "match": result}, ReportContent)
        report.update(generated.model_dump(), engine="model")
    elif settings.ai_backend == "legacy" and model_settings(settings).qwen_chat_configured:
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
    report["profile_analysis"] = await _analysis_for(request.resume_id)
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
    if settings.ai_backend == "dify" and not _is_china_demo(profile):
        plan = await DifyClient(settings).run("questions", {"profile": profile, "job": job}, InterviewPlan)
        questions = [question.model_dump() for question in plan.questions]
        engine = "model"
    elif settings.ai_backend == "legacy" and model_settings(settings).qwen_chat_configured:
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
        "profile_analysis": await _analysis_for(request.resume_id),
        "ai_backend": settings.ai_backend,
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
        summary_pending=session.get("summary_pending", False),
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
    if session.get("ai_backend") == "dify" and session.get("engine") == "model":
        evaluation = await DifyClient(settings).run("evaluate", {"answer": request.answer, "question": question}, AnswerEvaluation)
        score, feedback = evaluation.score, evaluation.feedback
    elif session.get("engine") == "model":
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
        if session.get("ai_backend") == "dify" and session.get("engine") == "model":
            try:
                summary = await DifyClient(settings).run("summary", {"turns": session["turns"], "job_title": session["job_title"]}, Summary)
                session["summary"] = summary.summary
            except CloudModelError:
                session["summary"] = ["回答和评分已保存；复盘报告暂未生成，可以稍后重试。"]
                session["summary_pending"] = True
        elif session.get("engine") == "model":
            session["summary"] = ["面试问题和回答反馈由千问云 API 生成，属于求职练习意见，不验证技术正确性或经历真实性。", "建议对照原始项目材料核验回答内容，并由本人决定是否采用修改建议。"]
        else:
            session["summary"] = ["当前为规则演示评分，仅检查关键词、回答长度和数字；不验证技术正确性或经历真实性。", "请优先补充回答中的项目职责和可核验结果，完整语义评价待模型接入后验证。"]
    _interviews[session_id] = session
    return _interview_response(session_id)


@app.post(f"{settings.api_prefix}/interviews/{{session_id}}/summary", response_model=InterviewSessionResponse)
async def retry_interview_summary(session_id: UUID) -> InterviewSessionResponse:
    session = _interviews.get(session_id)
    if not session or session.get("ai_backend") != "dify" or session["status"] != "completed":
        raise HTTPException(status_code=409, detail="此会话没有已完成的 Dify 面试")
    if session.get("summary_pending"):
        summary = await DifyClient(settings).run("summary", {"turns": session["turns"], "job_title": session["job_title"]}, Summary)
        session.update(summary=summary.summary, summary_pending=False)
        _interviews[session_id] = session
    return _interview_response(session_id)


@app.post(f"{settings.api_prefix}/exports", response_model=ExportArtifactResponse, status_code=201)
async def create_export(request: ExportRequest) -> ExportArtifactResponse:
    if request.type == "profile":
        data = await _analysis_for(request.resource_id)
    elif request.type == "diagnosis":
        report = _reports.get(request.resource_id)
        data = DiagnosticReport.model_validate(report).model_dump(mode="json") if report else None
        if data is not None and report.get("profile_analysis"):
            data["profile_analysis"] = report["profile_analysis"]
    elif request.type == "resume_draft":
        data = _resume_drafts.get(request.resource_id)
        if data is not None and data.get("resume_id"):
            profile = _profiles.get(data["resume_id"])
            if profile and str(profile.get("source_revision", "")) != str(data.get("source_revision", "")):
                data = {**data, "stale_notice": "基于旧版本画像，请重新生成后再导出正式版。"}
    elif request.type == "scenario":
        data = _scenario_runs.get(request.resource_id)
        if data is not None and data.get("status") != "completed":
            raise HTTPException(status_code=409, detail="攻略尚未生成完成，暂不能导出。")
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


@app.get(f"{settings.api_prefix}/orchestration")
async def orchestration_status() -> dict:
    client = DifyClient(settings)
    return {
        "backend": settings.ai_backend,
        "workflows": {operation: client.configured(operation) for operation in ("profile", "analysis", "match", "report", "questions", "evaluate", "summary", "chat", "ocr", "media_create", "media_status")},
        "agents": {"scoring": "DeepSeek", "review": "DeepSeek", "report": "千问", "interview": "千问出题 / DeepSeek 评分 / 千问总结", "media": "豆包 Seedream / Seedance"},
        "media_enabled": settings.media_enabled,
        "media_capabilities": {"image": settings.media_enabled and bool(settings.ark_image_model), "video": settings.media_enabled and bool(settings.ark_video_model)},
    }


@app.post(f"{settings.api_prefix}/media", status_code=201)
async def create_media(request: MediaCreate) -> dict:
    if settings.ai_backend != "dify" or not settings.media_enabled:
        raise HTTPException(status_code=503, detail="Dify 媒体功能尚未启用。")
    payload = {**request.model_dump(), "owner": current_session.get()}
    result = await DifyClient(settings).run("media_create", payload)
    if not result.get("task_id") or result.get("request_id") != request.request_id:
        raise HTTPException(status_code=502, detail="媒体工作流返回无效任务")
    _media[result["task_id"]] = {"request_id": request.request_id}
    return {key: result.get(key) for key in ("task_id", "request_id", "kind", "status", "urls")}


@app.get(f"{settings.api_prefix}/media/{{task_id}}")
async def get_media(task_id: UUID) -> dict:
    record = _media.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="当前会话没有此媒体任务")
    result = await DifyClient(settings).run("media_status", {**record, "owner": current_session.get()})
    return {key: result.get(key) for key in ("task_id", "request_id", "kind", "status", "urls")}


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


def _confirmed_profile_or_404(resume_id: UUID | None) -> tuple[UUID, dict]:
    if resume_id is None:
        raise HTTPException(status_code=422, detail="请先上传简历并确认画像，或在请求中提供手填资料。")
    profile = _profiles.get(resume_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="未找到当前浏览器的画像")
    if profile.get("status") != "confirmed":
        raise HTTPException(status_code=409, detail="请先核对并确认简历画像")
    return resume_id, profile


def _check_revision(profile: dict, source_revision: str) -> None:
    current = str(profile.get("source_revision", ""))
    if source_revision and current and source_revision != current:
        raise HTTPException(status_code=409, detail="画像已更新，请基于最新确认内容重新生成。")


def _job_context(job_title: str) -> dict | None:
    return {"title": job_title} if job_title else None


@app.post(f"{settings.api_prefix}/resume-guidance", status_code=201)
async def create_resume_guidance(request: ResumeGuidanceRequest) -> dict:
    resume_id, profile = _confirmed_profile_or_404(request.resume_id)
    _check_revision(profile, request.source_revision)
    if settings.ai_backend == "dify":
        from app.services.resume_docs import GuidanceResult
        result = GuidanceResult.model_validate(await DifyClient(settings).run("resume_guidance", {"confirmed_facts": collect_confirmed_facts(profile), "job": _job_context(request.job_title)}, GuidanceResult))
    else:
        require_qwen_chat()
        provider = QwenCloudProvider(model_settings(settings))
        result = await generate_guidance(profile, _job_context(request.job_title), provider)
    guidance_id = str(uuid4())
    record = {
        "guidance_id": guidance_id,
        "resume_id": str(resume_id),
        "source_revision": profile.get("source_revision", ""),
        "job_title": request.job_title,
        "created_at": datetime.now(UTC).isoformat(),
        **result.model_dump(),
    }
    _resume_guidance[guidance_id] = record
    return record


@app.get(f"{settings.api_prefix}/resume-guidance/{{guidance_id}}")
async def get_resume_guidance(guidance_id: UUID) -> dict:
    record = _resume_guidance.get(guidance_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Guidance not found")
    stale = ""
    profile = _profiles.get(record.get("resume_id", ""))
    if profile and str(profile.get("source_revision", "")) != str(record.get("source_revision", "")):
        stale = "基于旧版本画像，请重新生成。"
    return {**record, "stale_notice": stale}


@app.post(f"{settings.api_prefix}/resume-rewrites", status_code=201)
async def create_resume_rewrites(request: ResumeRewriteRequest) -> dict:
    resume_id, profile = _confirmed_profile_or_404(request.resume_id)
    _check_revision(profile, request.source_revision)
    if not request.block_ids:
        raise HTTPException(status_code=422, detail="请至少选择一段原文进行润色。")
    blocks = _resume_blocks.get(resume_id) or []
    selected = [block for block in blocks if str(block.get("block_id")) in set(request.block_ids)]
    if not selected:
        raise HTTPException(status_code=404, detail="未找到所选原文段落。")
    facts = collect_confirmed_facts(profile)
    fact_ids = {fact["fact_id"] for fact in facts}
    if settings.ai_backend == "dify":
        from app.services.resume_docs import RewriteResult
        result = RewriteResult.model_validate(await DifyClient(settings).run("resume_rewrite", {"selected_blocks": selected, "confirmed_facts": facts, "job": _job_context(request.job_title)}, RewriteResult))
    else:
        require_qwen_chat()
        provider = QwenCloudProvider(model_settings(settings))
        result = await rewrite_blocks(selected, facts, _job_context(request.job_title), provider)
    checked = [validate_rewrite(item, selected, fact_ids).model_dump() for item in result.rewrites]
    return {
        "resume_id": str(resume_id),
        "source_revision": profile.get("source_revision", ""),
        "rewrites": checked,
    }


def _profile_from_manual(manual: dict) -> dict:
    profile = {
        "education": manual.get("education") or [],
        "skills": manual.get("skills") or [],
        "experiences": manual.get("experiences") or [],
        "projects": manual.get("projects") or [],
        "preferences": manual.get("preferences") or {},
        "warnings": ["手填资料为用户自述，未与原始文件核对。"],
        "status": "confirmed",
        "source_revision": "manual",
    }
    return profile


@app.post(f"{settings.api_prefix}/resume-drafts", status_code=201)
async def create_resume_draft(request: ResumeDraftRequest) -> dict:
    if request.manual_profile is not None:
        profile = _profile_from_manual(request.manual_profile)
        resume_id = request.resume_id
    else:
        resume_id, profile = _confirmed_profile_or_404(request.resume_id)
        _check_revision(profile, request.source_revision)
    if settings.ai_backend == "dify":
        from app.services.resume_docs import ResumeDraftContent
        content = ResumeDraftContent.model_validate(await DifyClient(settings).run("resume_draft", {"confirmed_facts": collect_confirmed_facts(profile), "template": "技术校招" if request.template == "campus" else "技术社招", "job": _job_context(request.job_title)}, ResumeDraftContent))
    else:
        require_qwen_chat()
        provider = QwenCloudProvider(model_settings(settings))
        content = await generate_resume_draft(profile, request.template, _job_context(request.job_title), provider)
    placeholders = draft_placeholders(content)
    draft_id = str(uuid4())
    record = {
        "draft_id": draft_id,
        "resume_id": str(resume_id) if resume_id else None,
        "template": request.template,
        "job_title": request.job_title,
        "source_revision": profile.get("source_revision", ""),
        "created_at": datetime.now(UTC).isoformat(),
        **content.model_dump(),
        "placeholders": placeholders,
        "export_blocked": bool(placeholders) and content.draft_status != "complete",
    }
    _resume_drafts[draft_id] = record
    return record


@app.get(f"{settings.api_prefix}/resume-drafts/{{draft_id}}")
async def get_resume_draft(draft_id: UUID) -> dict:
    record = _resume_drafts.get(draft_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    stale = ""
    if record.get("resume_id"):
        profile = _profiles.get(record["resume_id"])
        if profile and str(profile.get("source_revision", "")) != str(record.get("source_revision", "")):
            stale = "基于旧版本画像，请重新生成。"
    return {**record, "stale_notice": stale}


@app.patch(f"{settings.api_prefix}/resume-drafts/{{draft_id}}")
async def update_resume_draft(draft_id: UUID, request: ResumeDraftUpdateRequest) -> dict:
    record = _resume_drafts.get(draft_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if request.source_revision and record.get("source_revision") and request.source_revision != record["source_revision"]:
        raise HTTPException(status_code=409, detail="草稿已被更新，请刷新后再编辑。")
    record.update({
        "name_line": request.name_line or record.get("name_line", ""),
        "contact_line": request.contact_line or record.get("contact_line", ""),
        "objective": request.objective or record.get("objective", ""),
        "sections": request.sections or record.get("sections", []),
        "updated_at": datetime.now(UTC).isoformat(),
    })
    _resume_drafts[draft_id] = record
    return record


@app.post(f"{settings.api_prefix}/scenario-runs", status_code=202)
async def create_scenario_run(request: ScenarioRunCreateRequest) -> dict:
    scenario = ScenarioInput.model_validate(request.model_dump())
    fingerprint = hashlib.sha256(json.dumps(scenario.model_dump(exclude={"request_id"}), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    for key in list(_scenario_runs):
        record = _scenario_runs[key]
        if record.get("request_id") == scenario.request_id:
            if record.get("fingerprint") != fingerprint:
                raise HTTPException(status_code=409, detail="此 request_id 已用于其他场景，请核对原任务。")
            return {"run_id": key, "status": record.get("status", "queued"), "deduplicated": True}
    run_id = str(uuid4())
    record = {
        "run_id": run_id,
        "request_id": scenario.request_id,
        "fingerprint": fingerprint,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
        "scenario": scenario.model_dump(),
        "warnings": [],
    }
    _scenario_runs[run_id] = record
    import asyncio
    task = asyncio.create_task(run_scenario(run_id, scenario, model_settings(settings), _scenario_runs))
    def _on_done(done: asyncio.Task) -> None:
        if done.cancelled():
            return
        failure = done.exception()
        if failure is not None:
            logger.warning("scenario_run_failed run_id=%s error=%s", run_id, type(failure).__name__)
            current = _scenario_runs.get(run_id)
            if current is not None and current.get("status") not in {"completed", "failed", "needs_clarification"}:
                current.update(status="failed", error="场景攻略任务异常结束，请重试。")
                _scenario_runs[run_id] = current
    task.add_done_callback(_on_done)
    return {"run_id": run_id, "status": "queued", "deduplicated": False}


@app.get(f"{settings.api_prefix}/scenario-runs/{{run_id}}")
async def get_scenario_run(run_id: UUID) -> dict:
    record = _scenario_runs.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    return record
