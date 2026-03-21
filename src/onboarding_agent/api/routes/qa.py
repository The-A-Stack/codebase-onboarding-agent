"""Q&A endpoint — answer questions about analyzed codebases."""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from onboarding_agent.api.job_manager import JobManager, JobStatus
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()
router = APIRouter(tags=["qa"])

_QA_SYSTEM_PROMPT = (
    "You are a codebase expert assistant. You have access to detailed analysis "
    "of a codebase including its architecture, modules, patterns, dependencies, "
    "and conventions.\n\n"
    "Answer the user's question based ONLY on the provided analysis data. "
    "Be specific — reference file paths, function names, and patterns from "
    "the analysis. If you're unsure, say so.\n\n"
    "Keep answers concise and actionable."
)


class QARequest(BaseModel):
    job_id: str
    question: str


class QAResponse(BaseModel):
    answer: str
    error: str | None = None


@router.post("/qa", response_model=QAResponse)
async def ask_question(request: QARequest) -> QAResponse:
    """Answer a question about an analyzed codebase."""
    manager = JobManager.get()
    job = manager.get_job(request.job_id)

    if not job:
        return QAResponse(answer="", error="Job not found")

    if job.status != JobStatus.COMPLETED or not job.result:
        return QAResponse(answer="", error="Analysis not yet complete")

    # Build context from result
    result = job.result
    context_parts = []

    # Modules
    modules = result.get("modules", {})
    analyzed = modules.get("analyzed", [])
    if analyzed:
        mod_lines = []
        for m in analyzed[:20]:
            mod_lines.append(f"- {m.get('file_path', '')}: {m.get('purpose', '')}")
        context_parts.append("## Modules\n" + "\n".join(mod_lines))

    # Endpoints
    endpoints = modules.get("api_endpoints", [])
    if endpoints:
        ep_lines = []
        for ep in endpoints:
            ep_lines.append(
                f"- {ep.get('method', '')} {ep.get('path', '')} -> {ep.get('handler_file', '')}"
            )
        context_parts.append("## API Endpoints\n" + "\n".join(ep_lines))

    # Patterns
    patterns = result.get("patterns", {})
    conventions = patterns.get("conventions", [])
    if conventions:
        conv_lines = []
        for c in conventions:
            conv_lines.append(f"- {c.get('name', '')}: {c.get('description', '')}")
        context_parts.append("## Conventions\n" + "\n".join(conv_lines))

    # Dependencies
    deps = result.get("dependencies", {})
    tech = deps.get("tech_stack", {})
    if tech:
        context_parts.append(f"## Tech Stack\n{json.dumps(tech, indent=1)}")

    # Scores
    scores = result.get("scores", {})
    if scores:
        context_parts.append(f"## AI-Readiness\nOverall: {scores.get('overall_score', 'N/A')}/10")

    context = "\n\n".join(context_parts)

    user_prompt = f"## Codebase Analysis Context\n{context}\n\n## Question\n{request.question}"

    llm = LLMService()
    response = await llm.complete(
        system_prompt=_QA_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    answer: str = response["content"].strip()
    return QAResponse(answer=answer)
