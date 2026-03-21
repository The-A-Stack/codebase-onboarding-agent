"""GitHub service for cloning repositories and fetching metadata."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import structlog
from git import Repo

from onboarding_agent.config import get_settings

logger = structlog.get_logger()

_GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def validate_github_url(url: str) -> tuple[str, str]:
    """Validate and extract owner/repo from a GitHub URL.

    Raises:
        ValueError: If the URL is not a valid GitHub repository URL.
    """
    match = _GITHUB_URL_PATTERN.match(url.strip())
    if not match:
        msg = f"Invalid GitHub URL: {url}"
        raise ValueError(msg)
    return match.group("owner"), match.group("repo")


class GitHubService:
    """Handles repository cloning and metadata extraction."""

    def __init__(self) -> None:
        settings = get_settings()
        self.clone_base_dir = settings.clone_dir
        self.token = settings.github_token.get_secret_value()

    def _build_clone_url(self, url: str) -> str:
        """Insert token into URL for private repo access."""
        if self.token:
            return url.replace("https://", f"https://{self.token}@")
        return url

    def clone_repo(self, url: str) -> tuple[Path, str]:
        """Clone a repository and return (local_path, commit_hash).

        If the repo is already cloned at the same commit, reuse it.
        """
        owner, repo_name = validate_github_url(url)
        clone_dir = self.clone_base_dir / f"{owner}__{repo_name}"

        if clone_dir.exists():
            try:
                existing_repo = Repo(clone_dir)
                commit_hash = existing_repo.head.commit.hexsha
                logger.info("repo_reused", path=str(clone_dir), commit=commit_hash[:8])
                return clone_dir, commit_hash
            except Exception:
                logger.warning("repo_corrupt_recloning", path=str(clone_dir))
                shutil.rmtree(clone_dir)

        self.clone_base_dir.mkdir(parents=True, exist_ok=True)
        clone_url = self._build_clone_url(url)
        logger.info("repo_cloning", url=url, dest=str(clone_dir))

        repo = Repo.clone_from(clone_url, clone_dir, depth=1)
        commit_hash = repo.head.commit.hexsha
        logger.info("repo_cloned", commit=commit_hash[:8])

        return clone_dir, commit_hash

    @staticmethod
    def cleanup(repo_path: Path) -> None:
        """Remove a cloned repository."""
        if repo_path.exists():
            shutil.rmtree(repo_path)
            logger.info("repo_cleaned", path=str(repo_path))
