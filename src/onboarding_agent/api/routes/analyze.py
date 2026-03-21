"""Analysis endpoints — POST /api/analyze, GET results, WebSocket progress."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, HttpUrl

from onboarding_agent.api.job_manager import (
    Job,
    JobManager,
    JobStatus,
    ProgressUpdate,
)
from onboarding_agent.models.state import CodebaseState, MetadataState
from onboarding_agent.pipeline.graph import build_graph

logger = structlog.get_logger()
router = APIRouter(tags=["analysis"])

# Hold references to background tasks to prevent GC
_background_tasks: set[asyncio.Task[None]] = set()


class AnalyzeRequest(BaseModel):
    repo_url: HttpUrl
    depth: str = "standard"
    agent_files: list[str] = Field(default_factory=lambda: ["claude", "copilot", "cline", "aider"])


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_node: str
    progress: list[dict[str, str]]
    result: dict[str, Any] | None = None
    error: str | None = None


async def _run_analysis(job: Job) -> None:
    """Run the pipeline in background, pushing progress updates."""
    job.status = JobStatus.RUNNING

    try:
        initial_state = CodebaseState(
            metadata=MetadataState(repo_url=str(job.repo_url)),
            analysis_depth=job.depth,
        )

        graph = build_graph()
        compiled = graph.compile()

        # Node names for progress tracking
        node_names = [
            "structure_scanner",
            "dependency_analyzer",
            "module_deep_diver",
            "pattern_detector",
            "ai_readiness_scorer",
            "output_router",
            "doc_generator",
            "agent_file_generator",
            "readiness_report",
            "final_assembler",
        ]

        node_descriptions = {
            "structure_scanner": "Scanning repository structure...",
            "dependency_analyzer": "Analyzing dependencies...",
            "module_deep_diver": "Deep-diving into modules...",
            "pattern_detector": "Detecting patterns...",
            "ai_readiness_scorer": "Scoring AI-readiness...",
            "output_router": "Routing outputs...",
            "doc_generator": "Generating documentation...",
            "agent_file_generator": "Generating agent files...",
            "readiness_report": "Building readiness report...",
            "final_assembler": "Assembling final results...",
        }

        # Stream events from LangGraph — each yielded value is the full state
        # after a node completes. The last value is the final result.
        current_idx = 0
        result = None
        async for state_snapshot in compiled.astream(
            initial_state,  # type: ignore[arg-type]
            stream_mode="values",
        ):
            result = state_snapshot

            # Extract current node for progress tracking
            if isinstance(state_snapshot, dict):
                node_name = state_snapshot.get("current_node", "")
            else:
                node_name = getattr(state_snapshot, "current_node", "")

            if node_name and node_name in node_descriptions:
                if node_name in node_names:
                    current_idx = node_names.index(node_name)

                job.push_progress(
                    ProgressUpdate(
                        node=node_name,
                        status="completed",
                        message=node_descriptions.get(node_name, f"Running {node_name}..."),
                        detail=f"Step {current_idx + 1}/{len(node_names)}",
                    )
                )

        if result is None:
            msg = "Pipeline produced no output"
            raise RuntimeError(msg)

        # Ensure result is fully serialized to plain dicts/lists
        if hasattr(result, "model_dump"):
            job.result = result.model_dump(mode="json")
        elif isinstance(result, dict):
            # stream_mode="values" may yield dicts with Pydantic sub-models
            job.result = CodebaseState(**result).model_dump(mode="json")
        else:
            job.result = dict(result)

        job.status = JobStatus.COMPLETED
        job.push_progress(
            ProgressUpdate(
                node="done",
                status="completed",
                message="Analysis complete!",
            )
        )
        logger.info("job_completed", job_id=job.job_id)

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.push_progress(
            ProgressUpdate(
                node="error",
                status="failed",
                message=f"Analysis failed: {exc}",
            )
        )
        logger.exception("job_failed", job_id=job.job_id)

    finally:
        job.notify_done()


@router.post("/analyze", response_model=AnalyzeResponse)
async def start_analysis(request: AnalyzeRequest) -> AnalyzeResponse:
    """Submit a repository for analysis."""
    manager = JobManager.get()
    job = manager.create_job(
        repo_url=str(request.repo_url),
        depth=request.depth,
        agent_files=request.agent_files,
    )

    # Run in background
    task = asyncio.create_task(_run_analysis(job))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return AnalyzeResponse(job_id=job.job_id, status=job.status)


@router.get("/analyze/{job_id}", response_model=JobStatusResponse)
async def get_analysis_status(job_id: str) -> JobStatusResponse:
    """Get the status and results of an analysis job."""
    manager = JobManager.get()
    job = manager.get_job(job_id)

    if not job:
        return JobStatusResponse(
            job_id=job_id,
            status="not_found",
            current_node="",
            progress=[],
            error="Job not found",
        )

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        current_node=job.current_node,
        progress=[{"node": p.node, "status": p.status, "message": p.message} for p in job.progress],
        result=job.result,
        error=job.error,
    )


@router.websocket("/ws/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint for live progress streaming."""
    await websocket.accept()

    manager = JobManager.get()
    job = manager.get_job(job_id)

    if not job:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close()
        return

    queue = job.subscribe()

    try:
        while True:
            update = await queue.get()
            if update is None:
                # Job is done
                await websocket.send_json(
                    {
                        "node": "done",
                        "status": job.status,
                        "message": "Analysis complete",
                    }
                )
                break

            await websocket.send_json(
                {
                    "node": update.node,
                    "status": update.status,
                    "message": update.message,
                    "detail": update.detail,
                }
            )
    except WebSocketDisconnect:
        logger.info("websocket_disconnected", job_id=job_id)
    finally:
        job.unsubscribe(queue)


@router.get("/jobs")
async def list_jobs() -> list[dict[str, str]]:
    """List all analysis jobs."""
    manager = JobManager.get()
    return manager.list_jobs()
