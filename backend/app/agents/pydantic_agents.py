from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel

from app.agents.schemas import (
    JDAnalysis,
    ParsedResume,
    RejectionFeedback,
    ScoringCriteriaSchema,
    ScreeningScore,
)
from app.core.config import get_settings

settings = get_settings()


def _litellm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=f"{settings.litellm_base_url.rstrip('/')}/v1",
        api_key=settings.litellm_master_key,
    )


def _model(name: str) -> OpenAIChatModel:
    return OpenAIChatModel(
    name,
    provider=OpenAIProvider(openai_client=_litellm_client())
)


jd_analyzer = Agent(
    _model("groq-fast"),
    output_type=JDAnalysis,
    retries=3,
    system_prompt=(
        "You analyze job descriptions and extract structured hiring requirements. "
        "Be precise and only include information present or clearly implied in the JD."
    ),
)

criteria_builder = Agent(
    _model("groq-fast"),
    output_type=ScoringCriteriaSchema,
    retries=3,
    system_prompt=(
        "You create scoring rubrics for resume screening. "
        "Criteria weights MUST sum to exactly 50 points. "
        "Provide 5-8 criteria covering skills, experience, education, and role fit."
    ),
)

resume_parser = Agent(
    _model("groq-parser"),
    output_type=ParsedResume,
    retries=3,
    system_prompt=(
        "Extract structured candidate information from resume text. "
        "If a field is missing, leave it null. Extract skills as a list."
    ),
)

resume_scorer = Agent(
    _model("groq-fast"),
    output_type=ScreeningScore,
    retries=3,
    system_prompt=(
        "Score the resume against the provided criteria rubric. "
        "Total score must be out of 50. Decision is 'shortlist' if score >= 30 else 'reject'. "
        "Provide detailed breakdown with rationale per criterion."
    ),
)

quality_reviewer = Agent(
    _model("openai-quality"),
    output_type=ScreeningScore,
    retries=3,
    system_prompt=(
        "Re-evaluate this borderline candidate carefully. "
        "Provide a fair, consistent score out of 50 with detailed rationale."
    ),
)

rejection_writer = Agent(
    _model("openai-quality"),
    output_type=RejectionFeedback,
    retries=3,
    system_prompt=(
        "Write a warm, professional 4-5 sentence rejection paragraph. "
        "Reference specific scores and JD requirements. Be constructive, not generic."
    ),
)
