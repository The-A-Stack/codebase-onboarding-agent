"""Node 7b: Agent File Generator — 1 LLM call per agent file.

Generates AI assistant context files (CLAUDE.md, copilot-instructions.md, etc.)
using common knowledge extractor → per-tool formatter pattern.
"""

from __future__ import annotations

import json

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()


# --- Common Knowledge Extractor ---


def _extract_common_knowledge(state: CodebaseState) -> dict[str, object]:
    """Pull universal facts from state for all agent file formatters."""
    tech = state.dependencies.tech_stack
    tech_info: dict[str, str] = {}
    if tech:
        tech_info = {
            "language": f"{tech.primary_language} {tech.language_version}".strip(),
            "framework": f"{tech.framework} {tech.framework_version}".strip(),
            "build_tool": tech.build_tool,
            "test_framework": tech.test_framework,
            "linter": tech.linter or "",
            "formatter": tech.formatter or "",
            "key_libraries": ", ".join(tech.key_libraries[:10]),
        }

    # Commands
    commands: dict[str, str] = {}
    for c in state.metadata.config_files:
        if c.name == "Makefile":
            commands["task_runner"] = "make"
        if c.name == "package.json":
            commands["package_manager"] = "npm"

    # Conventions
    conventions = [f"{c.name}: {c.description}" for c in state.patterns.conventions]

    # Architecture
    modules = [f"{m.file_path}: {m.purpose}" for m in state.modules.analyzed[:15]]

    # Gotchas
    gotchas: list[str] = []
    for issue in state.patterns.inconsistencies:
        gotchas.append(f"{issue.description} ({', '.join(issue.files_involved[:3])})")
    for dc in state.patterns.dead_code[:5]:
        gotchas.append(f"Unused exports in {dc.get('file', 'unknown')}")

    return {
        "tech": tech_info,
        "commands": commands,
        "conventions": conventions,
        "modules": modules,
        "entry_points": state.metadata.entry_points,
        "gotchas": gotchas,
        "env_vars": [ev.name for ev in state.dependencies.env_vars],
    }


# --- Per-tool formatters ---

_AGENT_SYSTEM_PROMPT = (
    "You are a developer tools expert. Given codebase analysis data, "
    "generate an AI assistant context file.\n\n"
    "Rules:\n"
    "- Be dense, precise, and actionable.\n"
    "- Use bullet points and commands, not prose.\n"
    "- Mark uncertain items with '# VERIFY: [reason]'.\n"
    "- Only output the file content, no wrapping or explanation."
)


def _build_claude_prompt(knowledge: dict[str, object]) -> str:
    return (
        "Generate a CLAUDE.md file for Claude Code.\n\n"
        "Format: Dense briefing document with these sections:\n"
        "- ## What This Is (1-2 lines)\n"
        "- ## Tech Stack\n"
        "- ## Commands (build, test, lint, format — exact commands)\n"
        "- ## Architecture (where things live)\n"
        "- ## Conventions (coding patterns to follow)\n"
        "- ## Key Constraints (what NOT to do)\n"
        "- ## Common Gotchas\n\n"
        f"Data:\n{json.dumps(knowledge, indent=2, default=str)}"
    )


def _build_copilot_prompt(knowledge: dict[str, object]) -> str:
    return (
        "Generate a copilot-instructions.md for GitHub Copilot.\n\n"
        "Format: Short, directive rules (not explanations).\n"
        "Sections:\n"
        "- Coding conventions and style\n"
        "- Preferred libraries\n"
        "- Patterns for common tasks\n"
        "- Things to avoid\n\n"
        f"Data:\n{json.dumps(knowledge, indent=2, default=str)}"
    )


def _build_cline_prompt(knowledge: dict[str, object]) -> str:
    return (
        "Generate a .clinerules file for Cline.\n\n"
        "Format: Constraint-oriented guardrails.\n"
        "Sections:\n"
        "- Project structure (where to create files)\n"
        "- Testing requirements\n"
        "- Architecture boundaries\n"
        "- Approval gates (what needs review)\n\n"
        f"Data:\n{json.dumps(knowledge, indent=2, default=str)}"
    )


def _build_aider_prompt(knowledge: dict[str, object]) -> str:
    return (
        "Generate a .aider.conf.yml for Aider.\n\n"
        "Format: YAML configuration.\n"
        "Include:\n"
        "- Convention notes\n"
        "- Test command\n"
        "- Lint command\n"
        "- File patterns to ignore\n\n"
        f"Data:\n{json.dumps(knowledge, indent=2, default=str)}"
    )


_FORMATTERS: dict[str, object] = {
    "claude": _build_claude_prompt,
    "copilot": _build_copilot_prompt,
    "cline": _build_cline_prompt,
    "aider": _build_aider_prompt,
}

_FILE_NAMES: dict[str, str] = {
    "claude": "CLAUDE.md",
    "copilot": ".github/copilot-instructions.md",
    "cline": ".clinerules",
    "aider": ".aider.conf.yml",
}


async def agent_file_generator(state: CodebaseState) -> dict[str, object]:
    """Generate AI assistant context files for selected tools.

    Uses common knowledge extractor + per-tool LLM formatter.
    """
    logger.info("agent_file_generator_start")

    knowledge = _extract_common_knowledge(state)
    llm = LLMService()
    agent_files: dict[str, str] = {}

    # Generate all 4 agent files
    for tool_name, prompt_builder in _FORMATTERS.items():
        logger.info("generating_agent_file", tool=tool_name)

        user_prompt = prompt_builder(knowledge)  # type: ignore[operator]
        response = await llm.complete(
            system_prompt=_AGENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        content: str = response["content"].strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]).strip()

        file_name = _FILE_NAMES[tool_name]
        agent_files[file_name] = content

    logger.info("agent_file_generator_complete", files=len(agent_files))

    return {
        "outputs": {
            "agent_files": agent_files,
        },
        "current_node": "agent_file_generator",
    }
