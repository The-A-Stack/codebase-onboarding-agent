"""Node 8: Final Assembler — no LLM.

Collects outputs from all generators, validates completeness,
and caches the result in SQLite.
"""

from __future__ import annotations

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.services.cache import AnalysisCache

logger = structlog.get_logger()


async def final_assembler(state: CodebaseState) -> dict[str, object]:
    """Assemble final outputs from all generators and cache results.

    - Validates that all expected outputs are present
    - Stores result in SQLite cache keyed by repo_url + commit_hash
    - Logs final summary
    """
    logger.info("final_assembler_start")

    # Validate outputs
    has_report = bool(state.outputs.report_json)
    has_markdown = bool(state.outputs.report_markdown)
    has_readiness = bool(state.outputs.readiness_report)

    logger.info(
        "outputs_check",
        report_json=has_report,
        report_markdown=has_markdown,
        agent_files=len(state.outputs.agent_files),
        readiness_report=has_readiness,
    )

    # Cache the result
    try:
        cache = AnalysisCache()
        await cache.init_db()

        result_to_cache: dict[str, object] = {
            "report_json": state.outputs.report_json,
            "report_markdown": state.outputs.report_markdown,
            "agent_files": state.outputs.agent_files,
            "readiness_report": state.outputs.readiness_report,
        }

        await cache.put(
            repo_url=state.metadata.repo_url,
            commit_hash=state.metadata.commit_hash,
            depth=state.analysis_depth,
            result=result_to_cache,
        )
        logger.info("results_cached")
    except Exception as exc:
        logger.warning("cache_write_failed", error=str(exc))

    logger.info(
        "final_assembler_complete",
        repo=state.metadata.repo_url,
        commit=state.metadata.commit_hash[:8],
        analyzed_files=len(state.modules.analyzed),
        agent_files=list(state.outputs.agent_files.keys()),
    )

    return {
        "current_node": "final_assembler",
    }
