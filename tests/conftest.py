"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from onboarding_agent.config.settings import Settings
from onboarding_agent.models.state import CodebaseState

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def test_settings() -> Settings:
    """Settings with test defaults — no real API keys needed."""
    return Settings(
        gemini_api_key="test-key",  # type: ignore[arg-type]
        github_token="test-token",  # type: ignore[arg-type]
        log_level="DEBUG",
        clone_dir=Path("/tmp/test-onboarding-agent"),
    )


@pytest.fixture
def empty_state() -> CodebaseState:
    """A fresh CodebaseState with no data populated."""
    return CodebaseState()


@pytest.fixture
def sample_python_file() -> str:
    return (FIXTURES_DIR / "sample_repos" / "python_app" / "main.py").read_text()


@pytest.fixture
def sample_ts_file() -> str:
    return (FIXTURES_DIR / "sample_repos" / "ts_app" / "index.ts").read_text()
