"""Node 5: AI-Readiness Scorer — 1 LLM call + deterministic metrics.

Evaluates codebase across 6 dimensions for AI assistant compatibility.

Dimensions (and weights):
  1. Discoverability (15%) — README, AI context files, structure clarity
  2. Type Safety (25%) — typed functions ratio, strict config
  3. Consistency (25%) — convention adherence from N4
  4. Modularity (15%) — circular deps, file sizes, interfaces
  5. Test Coverage (10%) — test file presence, CI, commands
  6. Dependency Hygiene (10%) — pinned versions, duplicates
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.models.types import Action
from onboarding_agent.parsers.python_parser import PythonParser
from onboarding_agent.parsers.typescript_parser import TypeScriptParser
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()

_DIMENSION_WEIGHTS: dict[str, float] = {
    "discoverability": 0.15,
    "type_safety": 0.25,
    "consistency": 0.25,
    "modularity": 0.15,
    "test_coverage": 0.10,
    "dependency_hygiene": 0.10,
}

_PY_PARSER = PythonParser()
_TS_PARSER = TypeScriptParser()


# --- Dimension 1: Discoverability (deterministic) ---


def _score_discoverability(state: CodebaseState) -> tuple[float, list[str]]:
    """Score based on README, AI context files, entry point clarity."""
    score = 0.0
    findings: list[str] = []
    repo = Path(state.metadata.local_path)

    # README exists and is substantive
    readme = None
    for name in ("README.md", "README.rst", "README.txt", "README"):
        candidate = repo / name
        if candidate.is_file():
            readme = candidate
            break

    if readme:
        size = readme.stat().st_size
        if size > 2000:
            score += 3.0
            findings.append("README is substantive")
        elif size > 200:
            score += 1.5
            findings.append("README exists but is brief")
        else:
            score += 0.5
            findings.append("README exists but is minimal/template")
    else:
        findings.append("No README found")

    # AI context files
    ai_files = ["CLAUDE.md", ".github/copilot-instructions.md", ".clinerules"]
    found_ai = sum(1 for f in ai_files if (repo / f).is_file())
    score += min(found_ai * 1.5, 3.0)
    if found_ai:
        findings.append(f"{found_ai} AI context file(s) found")
    else:
        findings.append("No AI context files found")

    # Entry points identifiable
    if state.metadata.entry_points:
        score += 2.0
        findings.append(f"{len(state.metadata.entry_points)} entry points identified")
    else:
        findings.append("No clear entry points found")

    # Config files present (shows project is well-structured)
    if len(state.metadata.config_files) >= 3:
        score += 2.0
    elif state.metadata.config_files:
        score += 1.0

    return min(score, 10.0), findings


# --- Dimension 2: Type Safety (deterministic) ---


def _score_type_safety(state: CodebaseState) -> tuple[float, list[str]]:
    """Score based on typed function ratio across the codebase."""
    repo = Path(state.metadata.local_path)
    total_funcs = 0
    typed_funcs = 0
    findings: list[str] = []

    for module in state.modules.analyzed:
        full_path = repo / module.file_path
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        parser: PythonParser | TypeScriptParser | None = None
        if _PY_PARSER.can_parse(full_path):
            parser = _PY_PARSER
        elif _TS_PARSER.can_parse(full_path):
            parser = _TS_PARSER

        if parser:
            typed, total = parser.count_typed_functions(full_path, content)
            typed_funcs += typed
            total_funcs += total

    if total_funcs == 0:
        findings.append("No functions found to evaluate")
        return 5.0, findings

    ratio = typed_funcs / total_funcs
    score = ratio * 8.0  # Max 8 from ratio

    # Check for strict mode configs
    tsconfig = repo / "tsconfig.json"
    if tsconfig.is_file():
        try:
            data = json.loads(tsconfig.read_text())
            strict = data.get("compilerOptions", {}).get("strict", False)
            if strict:
                score += 2.0
                findings.append("TypeScript strict mode enabled")
        except (json.JSONDecodeError, OSError):
            pass

    # Check for mypy config
    pyproject = repo / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text()
            if "strict = true" in content.lower() and "mypy" in content.lower():
                score += 2.0
                findings.append("mypy strict mode enabled")
        except OSError:
            pass

    pct = round(ratio * 100)
    findings.append(f"{typed_funcs}/{total_funcs} functions typed ({pct}%)")

    return min(score, 10.0), findings


# --- Dimension 3: Consistency (from N4 patterns) ---


def _score_consistency(state: CodebaseState) -> tuple[float, list[str]]:
    """Score from pattern detector results: conventions vs inconsistencies."""
    conventions = len(state.patterns.conventions)
    inconsistencies = len(state.patterns.inconsistencies)
    findings: list[str] = []

    # Base score from having detected conventions
    score = min(conventions * 1.5, 6.0)
    findings.append(f"{conventions} conventions detected")

    # Penalize inconsistencies
    penalty = 0.0
    for issue in state.patterns.inconsistencies:
        if issue.severity == "high":
            penalty += 1.5
        elif issue.severity == "medium":
            penalty += 1.0
        else:
            penalty += 0.5

    score = max(score - penalty, 0.0)
    if inconsistencies:
        findings.append(f"{inconsistencies} inconsistencies found")

    # Bonus for linter/formatter
    tech = state.dependencies.tech_stack
    if tech:
        if tech.linter:
            score += 2.0
            findings.append(f"Linter configured: {tech.linter}")
        if tech.formatter:
            score += 2.0
            findings.append(f"Formatter configured: {tech.formatter}")

    return min(score, 10.0), findings


# --- Dimension 4: Modularity (deterministic) ---


def _score_modularity(state: CodebaseState) -> tuple[float, list[str]]:
    """Score based on circular deps, file sizes, interfaces."""
    findings: list[str] = []
    score = 7.0  # Start optimistic, deduct for issues

    # Check for circular dependencies
    graph = state.dependencies.import_graph
    circular_count = _count_circular_deps(graph)
    if circular_count > 0:
        score -= min(circular_count * 1.0, 3.0)
        findings.append(f"{circular_count} circular dependency chain(s)")
    else:
        findings.append("No circular dependencies detected")

    # Check file size distribution from hotspots
    large_files = [h for h in state.patterns.complexity_hotspots if h.line_count > 500]
    if large_files:
        score -= min(len(large_files) * 0.5, 2.0)
        findings.append(f"{len(large_files)} files over 500 lines")

    # Check for clear public interfaces (modules with defined exports)
    modules_with_interfaces = sum(1 for m in state.modules.analyzed if m.public_interfaces)
    total_modules = len(state.modules.analyzed)
    if total_modules > 0:
        interface_ratio = modules_with_interfaces / total_modules
        score += interface_ratio * 3.0
        pct = round(interface_ratio * 100)
        findings.append(f"{pct}% of modules have clear public interfaces")

    return min(max(score, 0.0), 10.0), findings


def _count_circular_deps(graph: dict[str, list[str]]) -> int:
    """Count circular dependency chains using simple DFS."""
    visited: set[str] = set()
    in_stack: set[str] = set()
    cycles = 0

    def dfs(node: str) -> None:
        nonlocal cycles
        if node in in_stack:
            cycles += 1
            return
        if node in visited:
            return
        visited.add(node)
        in_stack.add(node)
        for neighbor in graph.get(node, []):
            dfs(neighbor)
        in_stack.discard(node)

    for node in graph:
        dfs(node)

    return cycles


# --- Dimension 5: Test Coverage (deterministic) ---


def _score_test_coverage(state: CodebaseState) -> tuple[float, list[str]]:
    """Score based on test presence, CI, and discoverability."""
    findings: list[str] = []
    score = 0.0
    repo = Path(state.metadata.local_path)

    # Count test files
    test_count = 0
    source_count = 0
    for module in state.modules.analyzed:
        lower = module.file_path.lower()
        if any(ind in lower for ind in ("test_", "tests/", "__tests__", ".test.", ".spec.")):
            test_count += 1
        else:
            source_count += 1

    # Also check for test directories
    for test_dir in ("tests", "test", "__tests__", "spec"):
        if (repo / test_dir).is_dir():
            test_count = max(test_count, 1)
            break

    if test_count > 0:
        ratio = test_count / max(source_count, 1)
        score += min(ratio * 10, 4.0)
        findings.append(f"{test_count} test files found")
    else:
        findings.append("No test files found")

    # CI config present
    ci_configs = [c for c in state.metadata.config_files if c.file_type == "ci_config"]
    if ci_configs:
        score += 3.0
        findings.append(f"CI config found: {ci_configs[0].name}")
    else:
        findings.append("No CI configuration found")

    # Test framework detected
    tech = state.dependencies.tech_stack
    if tech and tech.test_framework:
        score += 2.0
        findings.append(f"Test framework: {tech.test_framework}")

    # Test commands discoverable (from config files)
    config_names = {c.name for c in state.metadata.config_files}
    if "Makefile" in config_names or "package.json" in config_names:
        score += 1.0

    return min(score, 10.0), findings


# --- Dimension 6: Dependency Hygiene (deterministic) ---


def _score_dependency_hygiene(state: CodebaseState) -> tuple[float, list[str]]:
    """Score based on pinned versions, duplicate detection."""
    findings: list[str] = []
    packages = state.dependencies.packages
    score = 7.0  # Start optimistic

    if not packages:
        findings.append("No dependencies detected")
        return 5.0, findings

    # Check pinned versions
    pinned = sum(1 for p in packages if p.version)
    total = len(packages)
    if total > 0:
        pin_ratio = pinned / total
        if pin_ratio < 0.5:
            score -= 2.0
            findings.append(f"Only {round(pin_ratio * 100)}% of deps have versions pinned")
        else:
            findings.append(f"{round(pin_ratio * 100)}% of deps have versions")

    # Check for common duplicates
    duplicate_groups = [
        {"axios", "got", "node-fetch", "undici", "superagent"},
        {"moment", "dayjs", "date-fns", "luxon"},
        {"lodash", "underscore", "ramda"},
        {"express", "fastify", "koa", "hapi"},
        {"mocha", "jest", "vitest", "ava"},
    ]

    pkg_names = {p.name.lower() for p in packages}
    for group in duplicate_groups:
        overlap = pkg_names & group
        if len(overlap) > 1:
            score -= 1.5
            findings.append(f"Duplicate libs: {', '.join(sorted(overlap))}")

    # Bonus for lock file
    repo = Path(state.metadata.local_path)
    lock_files = [
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    ]
    has_lock = any((repo / lf).is_file() for lf in lock_files)
    if has_lock:
        score += 2.0
        findings.append("Lock file present")
    else:
        score -= 1.0
        findings.append("No lock file found")

    return min(max(score, 0.0), 10.0), findings


# --- LLM call for recommendations ---

_RECO_SYSTEM_PROMPT = (
    "You are an AI-readiness consultant. Given dimension scores and "
    "findings for a codebase, produce a prioritized action plan.\n\n"
    "Respond with valid JSON:\n"
    "{\n"
    '  "recommendations": [\n'
    "    {\n"
    '      "description": "specific action to take",\n'
    '      "impact": "high|medium|low",\n'
    '      "effort": "high|medium|low",\n'
    '      "affected_dimension": "dimension name",\n'
    '      "score_improvement_estimate": "e.g. 5.0 -> 7.5",\n'
    '      "specific_files": ["files to modify"]\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Max 8 recommendations, ordered by impact/effort ratio.\n"
    "- Be specific: name exact files, counts, actions.\n"
    "- Only respond with the JSON object."
)


async def _generate_recommendations(
    scores: dict[str, float],
    all_findings: dict[str, list[str]],
    state: CodebaseState,
) -> list[Action]:
    """LLM call to generate prioritized improvement recommendations."""
    findings_text = ""
    for dim, findings in all_findings.items():
        findings_text += f"\n### {dim} (score: {scores[dim]:.1f}/10)\n"
        for f in findings:
            findings_text += f"- {f}\n"

    overall = sum(scores[d] * w for d, w in _DIMENSION_WEIGHTS.items())

    user_prompt = (
        f"## AI-Readiness Assessment\n"
        f"Overall score: {overall:.1f}/10\n"
        f"{findings_text}\n"
        f"Total analyzed files: {len(state.modules.analyzed)}\n"
        f"Generate a prioritized action plan."
    )

    llm = LLMService()
    response = await llm.complete(
        system_prompt=_RECO_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    raw: str = response["content"].strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    actions: list[Action] = []
    try:
        data = json.loads(raw)
        for rec in data.get("recommendations", []):
            actions.append(
                Action(
                    description=rec.get("description", ""),
                    impact=rec.get("impact", "medium"),
                    effort=rec.get("effort", "medium"),
                    affected_dimension=rec.get("affected_dimension", ""),
                    score_improvement_estimate=rec.get("score_improvement_estimate", ""),
                    specific_files=rec.get("specific_files", []),
                )
            )
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("recommendations_parse_failed", error=str(exc))

    return actions


# --- Main node function ---


async def ai_readiness_scorer(state: CodebaseState) -> dict[str, object]:
    """Score the codebase across 6 AI-readiness dimensions.

    4 dimensions are computed deterministically, 1 uses N4 output,
    and 1 LLM call generates the recommendation action plan.
    """
    logger.info("ai_readiness_scorer_start")

    scores: dict[str, float] = {}
    all_findings: dict[str, list[str]] = {}

    # Compute each dimension
    scorers: list[tuple[str, tuple[float, list[str]]]] = [
        ("discoverability", _score_discoverability(state)),
        ("type_safety", _score_type_safety(state)),
        ("consistency", _score_consistency(state)),
        ("modularity", _score_modularity(state)),
        ("test_coverage", _score_test_coverage(state)),
        ("dependency_hygiene", _score_dependency_hygiene(state)),
    ]

    for name, (score, findings) in scorers:
        scores[name] = round(score, 1)
        all_findings[name] = findings
        logger.info(
            "dimension_scored",
            dimension=name,
            score=round(score, 1),
        )

    # Overall weighted score
    overall = sum(scores[d] * w for d, w in _DIMENSION_WEIGHTS.items())
    overall = round(overall, 1)

    # LLM call for recommendations
    recommendations = await _generate_recommendations(
        scores,
        all_findings,
        state,
    )

    logger.info(
        "ai_readiness_scorer_complete",
        overall=overall,
        recommendations=len(recommendations),
    )

    return {
        "scores": {
            "dimension_scores": scores,
            "overall_score": overall,
            "recommendations": recommendations,
            "agent_file_config": {
                "scores": scores,
                "findings": all_findings,
                "overall": overall,
            },
        },
        "current_node": "ai_readiness_scorer",
    }
