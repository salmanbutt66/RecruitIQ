import json

from crewai import Agent, Crew, Process, Task

from app.agents import pydantic_agents
from app.agents.schemas import JDAnalysis, ScoringCriteriaSchema, ScreeningScore
from app.core.enums import DesignationTier
import asyncio
from pydantic_ai.exceptions import ModelHTTPError


async def _run_with_retry(agent, prompt: str, max_attempts: int = 3):
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await agent.run(prompt)
        except ModelHTTPError as e:
            last_exc = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
            continue
    raise last_exc

def _run_sync(coro):
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def analyze_jd(jd_text: str) -> JDAnalysis:
    result = await _run_with_retry(
        pydantic_agents.jd_analyzer, f"Analyze this job description:\n\n{jd_text}"
    )
    return result.output


from app.core.enums import DesignationTier

DESIGNATION_CRITERIA_GUIDANCE: dict[str, str] = {
    DesignationTier.DIRECTOR: (
        "This is a DIRECTOR-level position. Weight criteria heavily toward:\n"
        "- Total years of relevant experience (favor more years)\n"
        "- Managerial/leadership experience (team size led, budget/P&L ownership, org-level impact)\n"
        "- Direct relevance of past projects and roles to this specific JD — not just keyword overlap, "
        "but whether their prior scope and seniority match what this role demands\n"
        "- Strategic/decision-making track record over raw technical execution\n"
        "Education should carry low weight relative to experience and leadership scope.\n\n"
        "TIE-BREAKER: If two candidates have similar years of experience and similar leadership scope, "
        "do NOT score them the same. Differentiate using secondary factors: relevant certifications "
        "(e.g. PMP, executive education, industry-specific credentials) and formal education. Give "
        "meaningfully more weight to certifications as a differentiator than education in this case."
    ),
    DesignationTier.MANAGER: (
        "This is a MANAGER-level position. Weight criteria heavily toward:\n"
        "- Years of relevant experience (favor more years)\n"
        "- People/team management experience (even informal leads, mentoring, cross-functional coordination)\n"
        "- How closely their past projects and responsibilities relate to this specific JD\n"
        "Education should carry low weight relative to experience and project relevance.\n\n"
        "TIE-BREAKER: If two candidates have similar years of experience and similar management scope, "
        "do NOT score them the same. Differentiate using secondary factors: relevant certifications "
        "(e.g. PMP, Scrum/Agile certifications, domain-specific credentials) and formal education. Give "
        "meaningfully more weight to certifications as a differentiator than education in this case."
    ),
    DesignationTier.EXECUTIVE: (
        "This is an EXECUTIVE-level (individual contributor) position. Weight criteria toward:\n"
        "- Relevant educational background and qualifications matching the role's domain\n"
        "- Demonstrated hands-on skills and relevant project/work experience in the specific domain\n"
        "- Do NOT require managerial or leadership experience — this is not a people-management role\n\n"
        "TIE-BREAKER: If two candidates have similar educational background and field relevance, "
        "do NOT score them the same. Differentiate using secondary factors: relevant work experience "
        "and professional certifications in the specific domain. Give meaningful weight to both as "
        "differentiators in this case."
    ),
    DesignationTier.INTERN_TRAINEE: (
        "This is an INTERN/TRAINEE-level position. Weight criteria heavily toward:\n"
        "- Field-of-study relevance to the role's specific domain — a degree or coursework directly "
        "matching the role's field should score much higher than an adjacent-but-different field "
        "(e.g. for an AI Engineer intern role, a candidate studying AI/Data Science/ML should score "
        "meaningfully higher than a general Computer Science candidate, even if the CS candidate has "
        "more generic programming exposure)\n"
        "- Academic performance, relevant coursework, and any personal/academic projects in the specific domain\n"
        "- Do NOT penalize for lack of professional work experience — this is expected at this level\n"
        "- Do NOT weight years of experience or managerial exposure at all\n\n"
        "TIE-BREAKER: If two candidates have similar field-of-study relevance, do NOT score them the same. "
        "Differentiate using secondary factors: any internship/project experience and relevant "
        "certifications (e.g. online courses, bootcamps, domain-specific certifications) in the specific "
        "domain. Give meaningful weight to both as differentiators in this case."
    ),
}


async def build_criteria(
    jd_text: str, analysis: JDAnalysis, designation: str | None = None
) -> ScoringCriteriaSchema:
    tier_guidance = DESIGNATION_CRITERIA_GUIDANCE.get(designation, "")
    result = await _run_with_retry(
        pydantic_agents.criteria_builder, f"Job description:\n{jd_text}\n\nAnalysis:\n{analysis.model_dump_json()}\n\n"
        + (f"Designation level: {designation}\n{tier_guidance}\n\n" if tier_guidance else "")
        + "Create a scoring rubric with criteria weights summing to 50."
    )
    output = result.output
    total = sum(c.weight for c in output.criteria)
    if total != 50:
        factor = 50 / total if total else 1
        adjusted = []
        running = 0
        for i, c in enumerate(output.criteria):
            if i == len(output.criteria) - 1:
                weight = 50 - running
            else:
                weight = max(1, round(c.weight * factor))
                running += weight
            adjusted.append(c.model_copy(update={"weight": weight}))
        output = ScoringCriteriaSchema(criteria=adjusted, total_points=50)
    return output


async def run_jd_criteria_pipeline(
    jd_text: str, designation: str | None = None
) -> tuple[JDAnalysis, ScoringCriteriaSchema, str]:
    analysis = await analyze_jd(jd_text)
    criteria = await build_criteria(jd_text, analysis, designation)
    return analysis, criteria, "groq-fast"


async def parse_resume(resume_text: str) -> dict:
    result = await _run_with_retry(
        pydantic_agents.resume_parser, f"Extract candidate info from this resume:\n\n{resume_text[:12000]}"
    )
    return result.output.model_dump()


async def score_resume(
    resume_text: str,
    jd_text: str,
    criteria: list[dict],
    parsed: dict,
) -> ScreeningScore:
    prompt = (
        f"Job Description:\n{jd_text[:4000]}\n\n"
        f"Scoring Criteria:\n{json.dumps(criteria, indent=2)}\n\n"
        f"Parsed Resume:\n{json.dumps(parsed, indent=2)}\n\n"
        f"Full Resume Text:\n{resume_text[:10000]}"
    )
    result = await _run_with_retry(pydantic_agents.resume_scorer, prompt)
    return result.output


async def review_borderline(
    resume_text: str,
    jd_text: str,
    criteria: list[dict],
    initial_score: ScreeningScore,
) -> ScreeningScore:
    prompt = (
        f"This candidate scored {initial_score.total_score}/50 (borderline).\n"
        f"Initial decision: {initial_score.decision}\n"
        f"Initial reason: {initial_score.reason}\n\n"
        f"JD:\n{jd_text[:4000]}\n\n"
        f"Criteria:\n{json.dumps(criteria, indent=2)}\n\n"
        f"Resume:\n{resume_text[:10000]}"
    )
    result = await _run_with_retry(pydantic_agents.quality_reviewer, prompt)
    return result.output


async def generate_rejection_feedback(
    *,
    candidate_name: str,
    jd_text: str,
    screening_summary: str,
    screening_reason: str,
    total_score: int,
    interview_notes: str | None = None,
) -> str:
    prompt = (
        f"Candidate: {candidate_name}\n"
        f"Screening score: {total_score}/50\n"
        f"Summary: {screening_summary}\n"
        f"Reason: {screening_reason}\n"
        f"Interview notes: {interview_notes or 'N/A'}\n\n"
        f"Job Description:\n{jd_text[:3000]}"
    )
    result = await _run_with_retry(pydantic_agents.rejection_writer, prompt)
    return result.output.paragraph


def build_jd_criteria_crew(jd_text: str) -> Crew:
    """CrewAI wrapper for JD criteria generation pipeline."""
    analyst = Agent(
        role="JD Analyst",
        goal="Extract structured requirements from job descriptions",
        backstory="Expert HR analyst specializing in requirement extraction",
        verbose=False,
        allow_delegation=False,
    )
    rubric_designer = Agent(
        role="Rubric Designer",
        goal="Create fair scoring rubrics totaling 50 points",
        backstory="Talent acquisition specialist who designs unbiased scoring criteria",
        verbose=False,
        allow_delegation=False,
    )

    analyze_task = Task(
        description=f"Analyze this JD and prepare requirements summary:\n{jd_text[:5000]}",
        expected_output="Structured JD analysis with skills and seniority",
        agent=analyst,
    )
    criteria_task = Task(
        description="Design scoring criteria weights summing to 50 based on the analysis",
        expected_output="Scoring rubric with weighted criteria",
        agent=rubric_designer,
        context=[analyze_task],
    )

    return Crew(
        agents=[analyst, rubric_designer],
        tasks=[analyze_task, criteria_task],
        process=Process.sequential,
        verbose=False,
    )

