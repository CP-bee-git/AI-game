from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    environment: str
    model_config = ConfigDict(extra="forbid")


class ModelConfigResponse(BaseModel):
    provider: str
    base_url: str
    model: str
    embedding_model: str
    embedding_dimensions: int


class TaskStatus(BaseModel):
    task_id: UUID
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: int = Field(ge=0, le=100)
    message: str | None = None


class ResumeResponse(BaseModel):
    resume_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    status: Literal["uploaded", "rejected"]
    task: TaskStatus | None = None
    created_at: datetime


class ResumeBlock(BaseModel):
    block_id: str
    text: str
    page: int | None = None
    block_type: str = "unknown"
    confidence: float | None = Field(default=None, ge=0, le=1)


class ProfileDraft(BaseModel):
    resume_id: UUID
    status: Literal["awaiting_confirmation", "confirmed"] = "awaiting_confirmation"
    education: list[dict] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    experiences: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ProfileConfirmRequest(BaseModel):
    education: list[dict] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    experiences: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)


class JobInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(default="未填写", max_length=200)
    location: str = Field(default="不限", max_length=100)
    education_required: str | None = Field(default=None, max_length=100)
    experience_required: str | None = Field(default=None, max_length=100)
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    preferred_skills: list[str] = Field(default_factory=list, max_length=50)
    responsibilities: list[str] = Field(default_factory=list, max_length=50)
    raw_text: str | None = Field(default=None, max_length=20000)


class JobSetCreate(BaseModel):
    name: str = Field(default="我的岗位清单", min_length=1, max_length=100)


class JobSetResponse(BaseModel):
    jobset_id: UUID
    name: str
    jobs: list[JobInput] = Field(default_factory=list)


class JobImportRequest(BaseModel):
    jobs: list[JobInput] = Field(min_length=1, max_length=20)


class MatchResult(BaseModel):
    job_title: str
    company: str
    location: str
    eligible: bool
    hard_fail_reasons: list[str] = Field(default_factory=list)
    total_score: float = Field(ge=0, le=100)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    matched_skills: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class MatchRunRequest(BaseModel):
    resume_id: UUID
    jobset_id: UUID


class MatchRunResponse(BaseModel):
    resume_id: UUID
    jobset_id: UUID
    results: list[MatchResult]


class DiagnosisRequest(BaseModel):
    resume_id: UUID
    jobset_id: UUID
    job_title: str = Field(min_length=1, max_length=200)


class DiagnosticReport(BaseModel):
    report_id: UUID
    job_title: str
    company: str
    strengths: list[str] = Field(default_factory=list)
    must_fix: list[str] = Field(default_factory=list)
    optional_improve: list[str] = Field(default_factory=list)
    ats_keywords: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)


class InterviewCreateRequest(BaseModel):
    resume_id: UUID
    jobset_id: UUID
    job_title: str = Field(min_length=1, max_length=200)


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=10000)


class InterviewTurn(BaseModel):
    sequence: int
    question: str
    answer: str | None = None
    score: float | None = Field(default=None, ge=0, le=5)
    feedback: str | None = None


class InterviewSessionResponse(BaseModel):
    session_id: UUID
    job_title: str
    status: Literal["active", "completed"]
    current_question: str | None = None
    turns: list[InterviewTurn] = Field(default_factory=list)
    overall_score: float | None = Field(default=None, ge=0, le=5)
    summary: list[str] = Field(default_factory=list)


class ModelPingResponse(BaseModel):
    status: Literal["ok"]
    provider: str
    model: str
    models: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    type: Literal["diagnosis", "interview"]
    resource_id: UUID
    format: Literal["json", "html"] = "html"


class ExportArtifactResponse(BaseModel):
    export_id: UUID
    filename: str
    content_type: str
    content: str

