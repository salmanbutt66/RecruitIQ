from pydantic import BaseModel, Field


class Criterion(BaseModel):
    name: str
    weight: int = Field(ge=1, le=50)
    description: str


class JDAnalysis(BaseModel):
    title: str
    seniority: str
    required_skills: list[str]
    nice_to_have: list[str] = Field(default_factory=list)
    location: str | None = None
    experience_years: int | None = None


class ScoringCriteriaSchema(BaseModel):
    criteria: list[Criterion] = Field(min_length=3)
    total_points: int = 50


class ParsedResume(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    designation: str | None = None
    summary: str = ""
    skills: list[str] = Field(default_factory=list)


class ScoreBreakdownItem(BaseModel):
    criterion_name: str
    score: int
    max_score: int
    rationale: str


class ScreeningScore(BaseModel):
    total_score: int = Field(ge=0, le=50)
    breakdown: list[ScoreBreakdownItem]
    decision: str
    summary: str
    reason: str


class RejectionFeedback(BaseModel):
    paragraph: str = Field(min_length=100, max_length=2000)
