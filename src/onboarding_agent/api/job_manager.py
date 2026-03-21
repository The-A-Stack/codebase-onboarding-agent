"""In-memory job manager for tracking analysis tasks."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger()


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProgressUpdate:
    node: str
    status: str
    message: str = ""
    detail: str = ""


@dataclass
class Job:
    job_id: str
    repo_url: str
    depth: str
    agent_files: list[str]
    status: JobStatus = JobStatus.QUEUED
    progress: list[ProgressUpdate] = field(default_factory=list)
    current_node: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    _subscribers: list[asyncio.Queue[ProgressUpdate | None]] = field(default_factory=list)

    def subscribe(self) -> asyncio.Queue[ProgressUpdate | None]:
        q: asyncio.Queue[ProgressUpdate | None] = asyncio.Queue()
        # Send existing progress
        for p in self.progress:
            q.put_nowait(p)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[ProgressUpdate | None]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def push_progress(self, update: ProgressUpdate) -> None:
        self.progress.append(update)
        self.current_node = update.node
        for q in self._subscribers:
            q.put_nowait(update)

    def notify_done(self) -> None:
        for q in self._subscribers:
            q.put_nowait(None)


class JobManager:
    """Singleton job manager — stores jobs in memory."""

    _instance: JobManager | None = None

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    @classmethod
    def get(cls) -> JobManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_job(self, repo_url: str, depth: str, agent_files: list[str]) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(
            job_id=job_id,
            repo_url=repo_url,
            depth=depth,
            agent_files=agent_files,
        )
        self._jobs[job_id] = job
        logger.info("job_created", job_id=job_id, repo_url=repo_url)
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, str]]:
        return [
            {"job_id": j.job_id, "status": j.status, "repo_url": j.repo_url}
            for j in self._jobs.values()
        ]
