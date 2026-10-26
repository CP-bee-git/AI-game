from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

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
    ModelPingResponse,
    ProfileConfirmRequest,
    ProfileDraft,
    ResumeResponse,
    TaskStatus,
)
from app.services.llm import OpenAICompatibleProvider, model_config
from app.services.diagnosis import build_diagnosis
from app.services.exporter import render_export
from app.services.interview import build_questions, evaluate_answer
from app.services.matching import match_jobs
from app.services.profile import extract_profile
from app.services.resume import initial_resume_blocks
from app.services.storage import LocalStorage

settings = get_settings()
storage = LocalStorage(settings.local_storage_dir)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

_resume_blocks: dict[UUID, list[dict]] = {}
_profiles: dict[UUID, dict] = {}
_jobsets: dict[UUID, dict] = {}
_interviews: dict[UUID, dict] = {}
_reports: dict[UUID, dict] = {}
_exports: dict[UUID, dict] = {}


def _validate_file(extension: str, content: bytes) -> None:
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="File content is not a PDF")
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="File content is not a PNG image")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="File content is not a JPEG image")
    if extension == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                valid_docx = "word/document.xml" in archive.namelist()
        except BadZipFile:
            valid_docx = False
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
    return ModelConfigResponse(**model_config(settings))


@app.post(f"{settings.api_prefix}/model/ping", response_model=ModelPingResponse)
async def model_ping() -> ModelPingResponse:
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    try:
        models = await OpenAICompatibleProvider(settings).list_models()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Cloud model provider is unreachable") from exc
    return ModelPingResponse(
        status="ok",
        provider=settings.model_provider,
        model=settings.openai_model,
        models=models,
    )


@app.post(f"{settings.api_prefix}/resumes/upload", response_model=ResumeResponse, status_code=201)
async def upload_resume(file: UploadFile = File(...)) -> ResumeResponse:
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
    _resume_blocks[resume_id] = initial_resume_blocks(destination, file.content_type or "")
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
    if not any(block.get("text") and block.get("block_id") != "ocr_pending" for block in blocks):
        raise HTTPException(status_code=422, detail="Resume has no extractable text; OCR is required")
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    try:
        payload = await extract_profile(resume_id, blocks, OpenAICompatibleProvider(settings))
        _profiles[resume_id] = payload
        return ProfileDraft.model_validate(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Cloud model returned an invalid profile response") from exc


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
    }
    _profiles[resume_id] = profile
    return ProfileDraft.model_validate(profile)


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
    results = [MatchResult.model_validate(item) for item in match_jobs(profile, jobset["jobs"])]
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
    result = next(item for item in match_jobs(profile, [job]))
    report = build_diagnosis(uuid4(), job, result)
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
    questions = build_questions(job)
    session_id = uuid4()
    _interviews[session_id] = {
        "job_title": job["title"],
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
        session["summary"] = ["回答已按相关性、证据、结构和量化结果完成基础评分。", "请优先补充低分回答中的项目职责和结果数据。"]
    return _interview_response(session_id)


@app.post(f"{settings.api_prefix}/exports", response_model=ExportArtifactResponse, status_code=201)
async def create_export(request: ExportRequest) -> ExportArtifactResponse:
    if request.type == "diagnosis":
        report = _reports.get(request.resource_id)
        data = DiagnosticReport.model_validate(report).model_dump(mode="json") if report else None
    else:
        data = _interview_response(request.resource_id).model_dump(mode="json") if request.resource_id in _interviews else None
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

