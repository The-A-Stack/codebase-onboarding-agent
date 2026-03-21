"""Tests for Pydantic state models."""

from __future__ import annotations

import pytest

from onboarding_agent.models.state import CodebaseState, MetadataState
from onboarding_agent.models.types import ConfigFile, ModuleSummary, TechProfile


@pytest.mark.unit
class TestCodebaseState:
    def test_default_state_is_empty(self, empty_state: CodebaseState) -> None:
        assert empty_state.metadata.repo_url == ""
        assert empty_state.modules.pending == []
        assert empty_state.scores.overall_score == 0.0
        assert empty_state.errors == []

    def test_metadata_population(self) -> None:
        metadata = MetadataState(
            repo_url="https://github.com/owner/repo",
            commit_hash="abc123",
            entry_points=["src/main.py"],
            config_files=[
                ConfigFile(
                    path="pyproject.toml", file_type="package_manifest", name="pyproject.toml"
                )
            ],
        )
        state = CodebaseState(metadata=metadata)
        assert state.metadata.repo_url == "https://github.com/owner/repo"
        assert len(state.metadata.config_files) == 1

    def test_tech_profile(self) -> None:
        profile = TechProfile(
            primary_language="Python",
            language_version="3.12",
            framework="FastAPI",
            framework_version="0.115.0",
            key_libraries=["langgraph", "pydantic"],
            build_tool="uv",
            test_framework="pytest",
        )
        assert profile.primary_language == "Python"
        assert "langgraph" in profile.key_libraries

    def test_module_summary(self) -> None:
        summary = ModuleSummary(
            file_path="src/main.py",
            purpose="Application entry point",
            internal_deps=["src/config.py"],
            external_deps=["fastapi"],
            compressed_summary="Entry point that initializes the FastAPI app.",
        )
        assert summary.file_path == "src/main.py"
        assert len(summary.internal_deps) == 1
