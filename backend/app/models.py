from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


JSONType = JSONB


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(150))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    blocks: Mapped[list["ResumeBlock"]] = relationship(back_populates="resume", cascade="all, delete-orphan")


class ResumeBlock(Base):
    __tablename__ = "resume_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    block_id: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    block_type: Mapped[str] = mapped_column(String(40), default="unknown")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    resume: Mapped[Resume] = relationship(back_populates="blocks")


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    resume_id: Mapped[str] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="awaiting_confirmation")
    data: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobSet(Base):
    __tablename__ = "job_sets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    jobs: Mapped[list["Job"]] = relationship(back_populates="jobset", cascade="all, delete-orphan")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    jobset_id: Mapped[str] = mapped_column(ForeignKey("job_sets.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200), default="未填写")
    location: Mapped[str] = mapped_column(String(100), default="不限")
    data: Mapped[dict] = mapped_column(JSONType)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    jobset: Mapped[JobSet] = relationship(back_populates="jobs")


class MatchResultRecord(Base):
    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    resume_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(40), default="rules-v1")
    eligible: Mapped[bool] = mapped_column(default=False)
    total_score: Mapped[float] = mapped_column()
    data: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiagnosticReportRecord(Base):
    __tablename__ = "diagnostic_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    resume_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    model_version: Mapped[str] = mapped_column(String(100), default="rules-v1")
    data: Mapped[dict] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

