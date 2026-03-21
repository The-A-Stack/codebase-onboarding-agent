"""LangGraph pipeline definition — the core 8-node analysis graph."""

from __future__ import annotations

from langgraph.graph import StateGraph

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.pipeline.nodes.agent_file_generator import agent_file_generator
from onboarding_agent.pipeline.nodes.ai_readiness_scorer import ai_readiness_scorer
from onboarding_agent.pipeline.nodes.dependency_analyzer import dependency_analyzer
from onboarding_agent.pipeline.nodes.doc_generator import doc_generator
from onboarding_agent.pipeline.nodes.final_assembler import final_assembler
from onboarding_agent.pipeline.nodes.module_deep_diver import module_deep_diver
from onboarding_agent.pipeline.nodes.output_router import output_router
from onboarding_agent.pipeline.nodes.pattern_detector import pattern_detector
from onboarding_agent.pipeline.nodes.readiness_report import readiness_report
from onboarding_agent.pipeline.nodes.structure_scanner import structure_scanner


def _should_continue_deep_dive(state: CodebaseState) -> str:
    """Conditional edge: loop back to deep-diver or proceed to pattern detector."""
    if state.modules.pending:
        return "module_deep_diver"
    return "pattern_detector"


def build_graph() -> StateGraph[CodebaseState]:
    """Construct the full analysis pipeline graph.

    N1 → N2 → N3 (cycle) → N4 → N5 → N6 → 7a → 7b → 7c → N8 → END
    """
    graph = StateGraph[CodebaseState](CodebaseState)

    # Add all nodes
    graph.add_node("structure_scanner", structure_scanner)
    graph.add_node("dependency_analyzer", dependency_analyzer)
    graph.add_node("module_deep_diver", module_deep_diver)
    graph.add_node("pattern_detector", pattern_detector)
    graph.add_node("ai_readiness_scorer", ai_readiness_scorer)
    graph.add_node("output_router", output_router)
    graph.add_node("doc_generator", doc_generator)
    graph.add_node("agent_file_generator", agent_file_generator)
    graph.add_node("readiness_report", readiness_report)
    graph.add_node("final_assembler", final_assembler)

    # Linear edges: N1 → N2 → N3
    graph.set_entry_point("structure_scanner")
    graph.add_edge("structure_scanner", "dependency_analyzer")
    graph.add_edge("dependency_analyzer", "module_deep_diver")

    # Cyclic edge — deep-diver loops while pending modules exist
    graph.add_conditional_edges(
        "module_deep_diver",
        _should_continue_deep_dive,
        {
            "module_deep_diver": "module_deep_diver",
            "pattern_detector": "pattern_detector",
        },
    )

    # N4 → N5 → N6 → generators → N8
    graph.add_edge("pattern_detector", "ai_readiness_scorer")
    graph.add_edge("ai_readiness_scorer", "output_router")
    graph.add_edge("output_router", "doc_generator")
    graph.add_edge("doc_generator", "agent_file_generator")
    graph.add_edge("agent_file_generator", "readiness_report")
    graph.add_edge("readiness_report", "final_assembler")
    graph.add_edge("final_assembler", "__end__")

    return graph


def _should_continue_deep_dive_or_end(state: CodebaseState) -> str:
    """Conditional edge for Sprint 2: loop back to deep-diver or end."""
    if state.modules.pending:
        return "module_deep_diver"
    return "__end__"


def build_sprint1_graph() -> StateGraph[CodebaseState]:
    """Construct a partial graph for Sprint 1: N1 → N2 only."""
    graph = StateGraph[CodebaseState](CodebaseState)

    graph.add_node("structure_scanner", structure_scanner)
    graph.add_node("dependency_analyzer", dependency_analyzer)

    graph.set_entry_point("structure_scanner")
    graph.add_edge("structure_scanner", "dependency_analyzer")
    graph.add_edge("dependency_analyzer", "__end__")

    return graph


def build_sprint2_graph() -> StateGraph[CodebaseState]:
    """Construct Sprint 2 graph: N1 → N2 → N3 (cyclic) → END."""
    graph = StateGraph[CodebaseState](CodebaseState)

    graph.add_node("structure_scanner", structure_scanner)
    graph.add_node("dependency_analyzer", dependency_analyzer)
    graph.add_node("module_deep_diver", module_deep_diver)

    graph.set_entry_point("structure_scanner")
    graph.add_edge("structure_scanner", "dependency_analyzer")
    graph.add_edge("dependency_analyzer", "module_deep_diver")

    graph.add_conditional_edges(
        "module_deep_diver",
        _should_continue_deep_dive_or_end,
        {
            "module_deep_diver": "module_deep_diver",
            "__end__": "__end__",
        },
    )

    return graph


def build_sprint3_graph() -> StateGraph[CodebaseState]:
    """Sprint 3 graph: N1 → N2 → N3 (cycle) → N4 → N5 → END."""
    graph = StateGraph[CodebaseState](CodebaseState)

    graph.add_node("structure_scanner", structure_scanner)
    graph.add_node("dependency_analyzer", dependency_analyzer)
    graph.add_node("module_deep_diver", module_deep_diver)
    graph.add_node("pattern_detector", pattern_detector)
    graph.add_node("ai_readiness_scorer", ai_readiness_scorer)

    graph.set_entry_point("structure_scanner")
    graph.add_edge("structure_scanner", "dependency_analyzer")
    graph.add_edge("dependency_analyzer", "module_deep_diver")

    # N3 cycles, then proceeds to N4
    graph.add_conditional_edges(
        "module_deep_diver",
        _should_continue_deep_dive,
        {
            "module_deep_diver": "module_deep_diver",
            "pattern_detector": "pattern_detector",
        },
    )

    graph.add_edge("pattern_detector", "ai_readiness_scorer")
    graph.add_edge("ai_readiness_scorer", "__end__")

    return graph
