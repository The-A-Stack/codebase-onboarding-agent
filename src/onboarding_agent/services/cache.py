"""SQLite-based analysis result cache."""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
import structlog

logger = structlog.get_logger()

_DB_PATH = Path("onboarding_agent_cache.db")

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS analysis_cache (
    cache_key TEXT PRIMARY KEY,
    repo_url TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    depth TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class AnalysisCache:
    """Cache analysis results keyed by repo_url + commit_hash + depth."""

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path

    @staticmethod
    def _make_key(repo_url: str, commit_hash: str, depth: str) -> str:
        return f"{repo_url}::{commit_hash}::{depth}"

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_INIT_SQL)

    async def get(self, repo_url: str, commit_hash: str, depth: str) -> dict[str, object] | None:
        key = self._make_key(repo_url, commit_hash, depth)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT result_json FROM analysis_cache WHERE cache_key = ?", (key,)
            )
            row = await cursor.fetchone()
            if row:
                logger.info("cache_hit", repo_url=repo_url, commit=commit_hash[:8])
                return json.loads(row[0])  # type: ignore[no-any-return]
        return None

    async def put(
        self,
        repo_url: str,
        commit_hash: str,
        depth: str,
        result: dict[str, object],
    ) -> None:
        key = self._make_key(repo_url, commit_hash, depth)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO analysis_cache
                   (cache_key, repo_url, commit_hash, depth, result_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, repo_url, commit_hash, depth, json.dumps(result)),
            )
            await db.commit()
            logger.info("cache_stored", repo_url=repo_url, commit=commit_hash[:8])
