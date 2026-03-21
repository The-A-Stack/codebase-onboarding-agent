"""Tests for service layer."""

from __future__ import annotations

import pytest

from onboarding_agent.services.github import validate_github_url


@pytest.mark.unit
class TestGitHubService:
    def test_valid_github_url(self) -> None:
        owner, repo = validate_github_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_valid_github_url_with_git_suffix(self) -> None:
        owner, repo = validate_github_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"

    def test_valid_github_url_with_trailing_slash(self) -> None:
        owner, repo = validate_github_url("https://github.com/owner/repo/")
        assert owner == "owner"
        assert repo == "repo"

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            validate_github_url("https://gitlab.com/owner/repo")

    def test_empty_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            validate_github_url("")

    def test_non_github_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            validate_github_url("https://example.com/something")
