from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str
    quote: str = Field(min_length=1, max_length=500)


class ScoredDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["教育描述", "技能证据", "项目表达", "实践经历", "求职目标"]
    score: float = Field(ge=0, le=100)
    evidence: list[Evidence] = Field(default_factory=list, max_length=5)
    note: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_source(self):
        if self.score > 0 and not self.evidence:
            raise ValueError("Nonzero scores require source evidence")
        return self


class ScoringResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimensions: list[ScoredDimension] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def unique_dimensions(self):
        if len({dimension.name for dimension in self.dimensions}) != 5:
            raise ValueError("Five different dimensions required")
        return self


class MatchAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_index: int = Field(ge=0, le=19)
    skill_coverage: float = Field(ge=0, le=100)
    education_match: float = Field(ge=0, le=100)
    preference_fit: float = Field(ge=0, le=100)
    evidence: list[Evidence] = Field(default_factory=list, max_length=5)
    reason: str = Field(min_length=1, max_length=1000)


class MatchAssessments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[MatchAssessment] = Field(min_length=1, max_length=20)


class Review(BaseModel):
    approved: bool
    issues: list[str] = Field(default_factory=list, max_length=8)


class Summary(BaseModel):
    summary: list[str] = Field(min_length=1, max_length=8)


class ReportContent(BaseModel):
    strengths: list[str] = Field(default_factory=list, max_length=8)
    must_fix: list[str] = Field(default_factory=list, max_length=8)
    optional_improve: list[str] = Field(default_factory=list, max_length=8)
    ats_keywords: list[str] = Field(default_factory=list, max_length=30)
    checklist: list[str] = Field(default_factory=list, max_length=8)


class MediaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["image", "video"]
    prompt: str = Field(min_length=5, max_length=2000)
    consent: Literal[True]
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{16,64}$")
