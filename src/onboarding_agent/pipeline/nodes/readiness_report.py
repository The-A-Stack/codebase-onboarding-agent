"""Node 7c: AI-Readiness Report Generator — 1 LLM call.

Produces the visual readiness report with radar chart data,
one-line verdict, and formatted action plan.
"""

from __future__ import annotations

import json

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()

_VERDICT_SYSTEM_PROMPT = (
    "You are an AI-readiness consultant. Given dimension scores, "
    "produce a one-line verdict and a brief narrative summary.\n\n"
    "Respond with valid JSON:\n"
    "{\n"
    '  "verdict": "one-line overall assessment",\n'
    '  "narrative": "2-3 paragraph summary of the assessment",\n'
    '  "top_strength": "the strongest dimension and why",\n'
    '  "top_weakness": "the weakest dimension and what to do"\n'
    "}\n\n"
    "- Verdict should be actionable (e.g. 'Good foundation — "
    "add type annotations to unlock AI potential').\n"
    "- Only respond with the JSON object."
)


async def readiness_report(state: CodebaseState) -> dict[str, object]:
    """Generate the AI-readiness visual report.

    Transforms dimension scores into radar chart data,
    formats the action plan, and generates a narrative verdict.
    """
    logger.info("readiness_report_start")

    scores = state.scores.dimension_scores
    overall = state.scores.overall_score

    # Build radar chart data (for D3.js frontend)
    radar_data = [{"dimension": dim, "score": score, "max": 10.0} for dim, score in scores.items()]

    # Format action plan
    action_plan = []
    for rec in state.scores.recommendations:
        action_plan.append(
            {
                "description": rec.description,
                "impact": rec.impact,
                "effort": rec.effort,
                "dimension": rec.affected_dimension,
                "improvement": rec.score_improvement_estimate,
                "files": rec.specific_files,
            }
        )

    # LLM call for narrative verdict
    score_summary = "\n".join(f"- {dim}: {score}/10" for dim, score in scores.items())
    user_prompt = (
        f"Overall AI-Readiness Score: {overall}/10\n\n"
        f"Dimension Scores:\n{score_summary}\n\n"
        f"Recommendations: {len(state.scores.recommendations)}\n"
        "Generate a verdict and narrative."
    )

    verdict = ""
    narrative = ""
    top_strength = ""
    top_weakness = ""

    llm = LLMService()
    response = await llm.complete(
        system_prompt=_VERDICT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    raw: str = response["content"].strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(raw)
        verdict = data.get("verdict", "")
        narrative = data.get("narrative", "")
        top_strength = data.get("top_strength", "")
        top_weakness = data.get("top_weakness", "")
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("verdict_parse_failed", error=str(exc))

    readiness_data: dict[str, object] = {
        "overall_score": overall,
        "verdict": verdict,
        "narrative": narrative,
        "top_strength": top_strength,
        "top_weakness": top_weakness,
        "radar_chart": radar_data,
        "dimension_scores": scores,
        "action_plan": action_plan,
    }

    logger.info(
        "readiness_report_complete",
        overall=overall,
        verdict=verdict[:60] if verdict else "",
    )

    return {
        "outputs": {
            "readiness_report": readiness_data,
        },
        "current_node": "readiness_report",
    }
