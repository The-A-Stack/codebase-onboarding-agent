"""Integration tests for the LangGraph pipeline."""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestPipelineIntegration:
    """Pipeline integration tests — implemented in Sprint 2+."""

    @pytest.mark.skip(reason="Pipeline not yet implemented")
    async def test_full_pipeline_execution(self) -> None:
        """End-to-end pipeline test against a sample repo."""
