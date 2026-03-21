"""Node 6: Output Router — no LLM.

Decision node that prepares configuration for the output generators.
In the current graph wiring, generators run sequentially after this node.
"""

from __future__ import annotations

import structlog

from onboarding_agent.models.state import CodebaseState

logger = structlog.get_logger()


async def output_router(state: CodebaseState) -> dict[str, object]:
    """Prepare routing config and pass through to generators.

    Currently a lightweight pass-through that logs analysis summary
    before output generation begins.
    """
    logger.info(
        "output_router",
        analyzed=len(state.modules.analyzed),
        conventions=len(state.patterns.conventions),
        overall_score=state.scores.overall_score,
    )

    return {
        "current_node": "output_router",
    }
