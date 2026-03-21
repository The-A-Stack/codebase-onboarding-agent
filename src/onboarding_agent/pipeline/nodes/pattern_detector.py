"""Node 4: Pattern Detector — 1-2 LLM calls.

Analyzes accumulated module summaries to identify cross-cutting patterns,
conventions, inconsistencies, dead code, and complexity hotspots.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.models.types import CodeQualitySignals, Convention, Hotspot, Issue
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()


# --- Deterministic dead-code detection ---


def _detect_dead_code(state: CodebaseState) -> list[dict[str, str]]:
    """Find exports that nothing imports (deterministic, no LLM)."""
    dead: list[dict[str, str]] = []
    import_graph = state.dependencies.import_graph

    # Build set of all imported files
    all_imported: set[str] = set()
    for targets in import_graph.values():
        all_imported.update(targets)

    # Check each analyzed module's public interfaces
    for module in state.modules.analyzed:
        if module.file_path not in all_imported and module.public_interfaces:
            # File has exports but nothing imports it
            # Skip entry points (they're supposed to be top-level)
            name = Path(module.file_path).name
            if name in {
                "main.py",
                "app.py",
                "server.py",
                "index.ts",
                "index.js",
                "manage.py",
                "__main__.py",
                "wsgi.py",
                "asgi.py",
            }:
                continue
            dead.append(
                {
                    "file": module.file_path,
                    "export": ", ".join(i.name for i in module.public_interfaces[:5]),
                    "reason_flagged": (
                        "File exports public interfaces but is not imported by any other module"
                    ),
                }
            )

    return dead


# --- Deterministic complexity hotspots ---


def _detect_complexity_hotspots(state: CodebaseState) -> list[Hotspot]:
    """Flag large files and complex functions from analyzed modules."""
    hotspots: list[Hotspot] = []
    repo_path = Path(state.metadata.local_path)

    for module in state.modules.analyzed:
        full_path = repo_path / module.file_path
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        line_count = len(lines)

        # Flag files over 500 lines
        if line_count > 500:
            hotspots.append(
                Hotspot(
                    file=module.file_path,
                    function="(entire file)",
                    line_count=line_count,
                    description=f"Large file with {line_count} lines",
                )
            )

        # Estimate max nesting depth
        max_depth = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                # Rough heuristic: 4 spaces or 1 tab = 1 level
                depth = indent // 4 if "    " in line[:indent] else indent
                max_depth = max(max_depth, depth)

        if max_depth > 6:
            hotspots.append(
                Hotspot(
                    file=module.file_path,
                    nesting_depth=max_depth,
                    description=f"Deeply nested code (max depth ~{max_depth})",
                )
            )

    return hotspots


# --- Code quality signal detection ---

_PYTHON_TYPE_HINT_PATTERNS = [
    r"def\s+\w+\s*\([^)]*:\s*\w+",  # function params with type hints
    r"->\s*\w+",  # return type annotations
    r":\s*(?:str|int|float|bool|list|dict|tuple|set|Optional|Union|Any)\b",  # common type annotations
]

_PYTHON_DOCSTRING_PATTERN = r'(?:def|class)\s+\w+[^:]*:\s*\n\s+(?:"""|\'\'\')'


def _detect_code_quality(state: CodebaseState) -> CodeQualitySignals:
    """Detect code quality signals from analyzed modules."""
    import re

    repo_path = Path(state.metadata.local_path)
    total_loc = 0
    total_files = 0
    files_with_type_hints = 0
    files_with_docstrings = 0
    total_functions = 0
    typed_functions = 0
    functions_with_docstrings = 0

    for module in state.modules.analyzed:
        full_path = repo_path / module.file_path
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        non_empty_lines = [ln for ln in lines if ln.strip()]
        total_loc += len(non_empty_lines)
        total_files += 1

        # Check for type hints
        has_hints = False
        for pattern in _PYTHON_TYPE_HINT_PATTERNS:
            if re.search(pattern, content):
                has_hints = True
                break
        if has_hints:
            files_with_type_hints += 1

        # Count functions and typed functions
        func_defs = re.findall(r"def\s+\w+\s*\(", content)
        total_functions += len(func_defs)
        typed_funcs = re.findall(r"def\s+\w+\s*\([^)]*:\s*\w+", content)
        typed_functions += len(typed_funcs)

        # Check for docstrings
        if re.search(_PYTHON_DOCSTRING_PATTERN, content):
            files_with_docstrings += 1
            functions_with_docstrings += len(
                re.findall(r'def\s+\w+[^:]*:\s*\n\s+(?:"""|\'\'\')[^\n]*', content)
            )

    # Determine coverage levels
    type_hint_coverage = "none"
    if total_functions > 0:
        ratio = typed_functions / total_functions
        if ratio > 0.7:
            type_hint_coverage = "high"
        elif ratio > 0.3:
            type_hint_coverage = "medium"
        elif ratio > 0:
            type_hint_coverage = "low"

    docstring_coverage = "none"
    if total_functions > 0:
        ratio = functions_with_docstrings / total_functions
        if ratio > 0.5:
            docstring_coverage = "high"
        elif ratio > 0.2:
            docstring_coverage = "medium"
        elif ratio > 0:
            docstring_coverage = "low"

    # Check linter/formatter from tech stack
    tech = state.dependencies.tech_stack
    has_linter = bool(tech and tech.linter)
    linter_name = (tech.linter or "") if tech else ""
    has_formatter = bool(tech and tech.formatter)
    formatter_name = (tech.formatter or "") if tech else ""

    # Check for pre-commit hooks
    has_pre_commit = any(
        cf.name == ".pre-commit-config.yaml" for cf in state.metadata.config_files
    )

    return CodeQualitySignals(
        total_lines_of_code=total_loc,
        total_source_files=total_files,
        has_type_hints=files_with_type_hints > 0,
        type_hint_coverage=type_hint_coverage,
        has_docstrings=files_with_docstrings > 0,
        docstring_coverage=docstring_coverage,
        has_linter=has_linter,
        linter_name=linter_name,
        has_formatter=has_formatter,
        formatter_name=formatter_name,
        has_pre_commit_hooks=has_pre_commit,
    )


# --- LLM prompt for pattern detection ---

_PATTERN_SYSTEM_PROMPT = (
    "You are a code analysis assistant specializing in detecting "
    "cross-cutting patterns and conventions in codebases.\n\n"
    "Given compressed summaries of analyzed modules, identify:\n"
    "1. Recurring conventions (error handling, data access, naming, "
    "file org, testing, imports)\n"
    "2. Inconsistencies (deviations from the codebase's own patterns)\n"
    "3. Complexity concerns (overly complex areas noted in summaries)\n\n"
    "Respond with valid JSON matching this schema:\n"
    "{\n"
    '  "conventions": [\n'
    "    {\n"
    '      "name": "string",\n'
    '      "description": "string",\n'
    '      "example_files": ["string"],\n'
    '      "pattern_type": "error_handling|data_access|naming|'
    'file_org|testing|imports"\n'
    "    }\n"
    "  ],\n"
    '  "inconsistencies": [\n'
    "    {\n"
    '      "description": "string",\n'
    '      "files_involved": ["string"],\n'
    '      "severity": "low|medium|high",\n'
    '      "possible_explanation": "string"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Only report conventions you see in 2+ files.\n"
    "- Be specific: name the exact pattern, not 'uses best practices'.\n"
    "- Inconsistencies: only flag genuine deviations, not style choices.\n"
    "- Only respond with the JSON object, no other text."
)


def _build_pattern_prompt(state: CodebaseState) -> str:
    """Build user prompt with all module summaries + import graph."""
    summaries = []
    for m in state.modules.analyzed:
        interfaces = ", ".join(i.name for i in m.public_interfaces[:5])
        patterns = ", ".join(m.patterns_observed[:5])
        summaries.append(
            f"**{m.file_path}** — {m.purpose}\n"
            f"  Interfaces: {interfaces or '(none)'}\n"
            f"  Patterns: {patterns or '(none)'}\n"
            f"  Internal deps: {', '.join(m.internal_deps[:5]) or '(none)'}\n"
            f"  External deps: {', '.join(m.external_deps[:5]) or '(none)'}\n"
            f"  Summary: {m.compressed_summary}"
        )

    tech = state.dependencies.tech_stack
    tech_info = ""
    if tech:
        tech_info = (
            f"\n## Tech Stack\n"
            f"- Language: {tech.primary_language}\n"
            f"- Framework: {tech.framework}\n"
            f"- Linter: {tech.linter or 'none'}\n"
            f"- Formatter: {tech.formatter or 'none'}\n"
        )

    return (
        f"## Analyzed Modules ({len(state.modules.analyzed)} files)\n\n"
        + "\n\n".join(summaries)
        + tech_info
        + "\n\nIdentify conventions and inconsistencies."
    )


async def pattern_detector(state: CodebaseState) -> dict[str, object]:
    """Detect patterns and conventions from analyzed modules.

    Combines deterministic checks (dead code, complexity) with
    1 LLM call for convention/inconsistency detection.
    """
    logger.info(
        "pattern_detector_start",
        analyzed_modules=len(state.modules.analyzed),
    )

    # Deterministic: dead code + complexity hotspots + code quality
    dead_code = _detect_dead_code(state)
    hotspots = _detect_complexity_hotspots(state)
    code_quality = _detect_code_quality(state)

    logger.info(
        "deterministic_patterns",
        dead_code=len(dead_code),
        hotspots=len(hotspots),
        loc=code_quality.total_lines_of_code,
        type_hints=code_quality.type_hint_coverage,
    )

    # LLM call: conventions + inconsistencies
    conventions: list[Convention] = []
    inconsistencies: list[Issue] = []

    if state.modules.analyzed:
        llm = LLMService()
        user_prompt = _build_pattern_prompt(state)

        response = await llm.complete(
            system_prompt=_PATTERN_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        raw: str = response["content"].strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1]).strip()

        try:
            data = json.loads(raw)

            for conv in data.get("conventions", []):
                conventions.append(
                    Convention(
                        name=conv.get("name", ""),
                        description=conv.get("description", ""),
                        example_files=conv.get("example_files", []),
                        pattern_type=conv.get("pattern_type", ""),
                    )
                )

            for inc in data.get("inconsistencies", []):
                inconsistencies.append(
                    Issue(
                        description=inc.get("description", ""),
                        files_involved=inc.get("files_involved", []),
                        severity=inc.get("severity", "medium"),
                        possible_explanation=inc.get("possible_explanation", ""),
                    )
                )

        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("pattern_detector_parse_failed", error=str(exc))

    logger.info(
        "pattern_detector_complete",
        conventions=len(conventions),
        inconsistencies=len(inconsistencies),
    )

    return {
        "patterns": {
            "conventions": conventions,
            "inconsistencies": inconsistencies,
            "dead_code": dead_code,
            "complexity_hotspots": hotspots,
            "code_quality": code_quality,
        },
        "current_node": "pattern_detector",
    }
