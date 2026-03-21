"""Node 3: Module Deep-Diver — 1 LLM call per file, CYCLIC.

Iteratively analyzes individual modules, building understanding incrementally.
Uses LangGraph's cyclic execution (conditional edge loops back while pending modules exist).

Each cycle:
1. Re-rank pending files by import-graph hub score
2. Pop the highest-priority file
3. Read its content, send to LLM with context (prior summaries, tree, import slice)
4. Parse the structured ModuleSummary response
5. Compress and update state (analyzed += 1, pending -= 1)
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.models.types import (
    Endpoint,
    Graph,
    Interface,
    ModuleSummary,
    Tree,
)
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()

# --- Priority ranking ---


def _compute_hub_scores(import_graph: Graph, pending: list[str]) -> dict[str, int]:
    """Compute how many files import each file (in-degree = hub score)."""
    in_degree: dict[str, int] = {f: 0 for f in pending}
    for _source, targets in import_graph.items():
        for target in targets:
            if target in in_degree:
                in_degree[target] += 1
    return in_degree


_ENTRY_POINT_NAMES: set[str] = {
    "main.py",
    "app.py",
    "server.py",
    "index.ts",
    "index.js",
    "index.tsx",
    "main.ts",
    "main.js",
    "app.ts",
    "app.js",
    "server.ts",
    "server.js",
    "__main__.py",
    "wsgi.py",
    "asgi.py",
}

_TEST_INDICATORS: set[str] = {"test_", "tests", "__tests__", "spec.", ".test.", ".spec."}


def _is_test_file(file_path: str) -> bool:
    """Check if a file is a test file (should be skipped during deep-dive)."""
    lower = file_path.lower()
    return any(ind in lower for ind in _TEST_INDICATORS)


def _rank_pending(pending: list[str], import_graph: Graph) -> list[str]:
    """Re-rank pending files: hub score desc, entry points first, tests last."""
    hub_scores = _compute_hub_scores(import_graph, pending)

    def sort_key(file_path: str) -> tuple[int, int, int, str]:
        name = Path(file_path).name
        is_test = 1 if _is_test_file(file_path) else 0
        is_entry = 0 if name in _ENTRY_POINT_NAMES else 1
        hub = -hub_scores.get(file_path, 0)  # negative for descending
        return (is_test, is_entry, hub, file_path)

    return sorted(pending, key=sort_key)


# --- Directory tree truncation ---


def _truncate_tree(tree: Tree, max_depth: int = 2, current_depth: int = 0) -> Tree:
    """Truncate directory tree to max_depth levels for LLM context."""
    if current_depth >= max_depth:
        return {"...": "truncated"}

    truncated: Tree = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            truncated[key] = _truncate_tree(value, max_depth, current_depth + 1)
        else:
            truncated[key] = value
    return truncated


# --- Import graph slice ---


def _get_import_slice(file_path: str, import_graph: Graph) -> dict[str, list[str]]:
    """Get the relevant import graph slice for a file.

    Returns what this file imports AND what imports this file.
    """
    slice_graph: dict[str, list[str]] = {}

    # What this file imports
    if file_path in import_graph:
        slice_graph[f"{file_path} imports"] = import_graph[file_path]

    # What imports this file
    imported_by: list[str] = []
    for source, targets in import_graph.items():
        if file_path in targets:
            imported_by.append(source)
    if imported_by:
        slice_graph[f"{file_path} imported by"] = imported_by

    return slice_graph


# --- LLM prompts ---

_SYSTEM_PROMPT = (
    "You are a code analysis assistant. Analyze the given source file "
    "and produce a structured JSON summary.\n\n"
    "Respond with valid JSON matching this exact schema:\n"
    "{\n"
    '  "purpose": "one-line description of what this module does",\n'
    '  "public_interfaces": [\n'
    '    {"name": "str", "signature": "str", "description": "str"}\n'
    "  ],\n"
    '  "internal_deps": ["internal module paths this file imports"],\n'
    '  "external_deps": ["external library names this file uses"],\n'
    '  "patterns_observed": ["coding patterns detected"],\n'
    '  "compressed_summary": "2-3 sentence summary (100-150 words)",\n'
    '  "endpoints": [\n'
    "    {\n"
    '      "method": "GET|POST|PUT|DELETE|PATCH",\n'
    '      "path": "/api/...",\n'
    '      "handler_function": "string",\n'
    '      "middleware": ["string"],\n'
    '      "downstream_calls": ["internal functions called"]\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- purpose: Be specific. 'Handles user auth via JWT' not 'auth'.\n"
    "- public_interfaces: Only exported/public. Include signatures.\n"
    "- internal_deps: Only project imports, not stdlib or packages.\n"
    "- external_deps: Library names only, not import paths.\n"
    "- patterns_observed: Name concretely (singleton, factory, etc).\n"
    "- compressed_summary: Replaces full file in future context. "
    "Make it information-dense.\n"
    "- endpoints: Only if file defines route handlers. Else [].\n"
    "- Only respond with the JSON object, no other text."
)


def _build_user_prompt(
    file_path: str,
    content: str,
    prior_summaries: list[ModuleSummary],
    tree_skeleton: Tree,
    import_slice: dict[str, list[str]],
) -> str:
    """Build the user prompt with full file + compressed context."""
    # Prior summaries (100-200 tokens each)
    summaries_text = ""
    if prior_summaries:
        summary_lines = []
        for s in prior_summaries:
            summary_lines.append(f"- **{s.file_path}**: {s.compressed_summary}")
        summaries_text = "\n".join(summary_lines)

    # Tree skeleton (truncated to 2 levels)
    tree_text = json.dumps(tree_skeleton, indent=1, default=str)

    # Import slice
    import_text = ""
    if import_slice:
        import_lines = []
        for label, files in import_slice.items():
            import_lines.append(f"  {label}: {', '.join(files)}")
        import_text = "\n".join(import_lines)

    return f"""\
## File Under Analysis
**Path:** `{file_path}`

```
{content}
```

## Previously Analyzed Modules
{summaries_text or "(none yet — this is the first file)"}

## Directory Structure (top 2 levels)
```
{tree_text}
```

## Import Relationships
{import_text or "(no imports detected for this file)"}

Analyze this file and produce the JSON summary."""


# --- Main node function ---


async def module_deep_diver(state: CodebaseState) -> dict[str, object]:
    """Analyze the next pending module and update state.

    Each invocation processes exactly ONE file, then returns.
    The conditional edge in graph.py loops back if more files remain.
    """
    pending = list(state.modules.pending)
    if not pending:
        return {"current_node": "module_deep_diver"}

    # Get repo path
    repo_path = Path(state.metadata.local_path)
    import_graph = state.dependencies.import_graph

    # Re-rank pending files by priority
    ranked = _rank_pending(pending, import_graph)

    # Filter out test files
    ranked = [f for f in ranked if not _is_test_file(f)]
    if not ranked:
        # Only test files left — clear pending and exit
        return {
            "modules": {
                "pending": [],
            },
            "current_node": "module_deep_diver",
        }

    # Pop highest-priority file
    current_file = ranked[0]
    remaining = [f for f in pending if f != current_file]

    logger.info(
        "deep_diver_analyzing",
        file=current_file,
        remaining=len(remaining),
        analyzed_so_far=len(state.modules.analyzed),
    )

    # Read file content
    full_path = repo_path / current_file
    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("deep_diver_read_failed", file=current_file, error=str(exc))
        return {
            "modules": {
                "pending": remaining,
            },
            "current_node": "module_deep_diver",
            "errors": [f"Failed to read {current_file}: {exc}"],
        }

    # Truncate very large files to avoid blowing the context window
    max_chars = 15_000  # ~4k tokens
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n... (truncated — file too large)"

    # Build context
    tree_skeleton = _truncate_tree(state.metadata.directory_tree)
    import_slice = _get_import_slice(current_file, import_graph)
    prior_summaries = list(state.modules.analyzed)

    user_prompt = _build_user_prompt(
        current_file,
        content,
        prior_summaries,
        tree_skeleton,
        import_slice,
    )

    # LLM call
    llm = LLMService()
    response = await llm.complete(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # Parse response
    raw_content: str = response["content"].strip()
    if raw_content.startswith("```"):
        lines = raw_content.splitlines()
        raw_content = "\n".join(lines[1:-1]).strip()

    summary: ModuleSummary
    endpoints: list[Endpoint] = []

    try:
        data = json.loads(raw_content)

        summary = ModuleSummary(
            file_path=current_file,
            purpose=data.get("purpose", ""),
            public_interfaces=[Interface(**iface) for iface in data.get("public_interfaces", [])],
            internal_deps=data.get("internal_deps", []),
            external_deps=data.get("external_deps", []),
            patterns_observed=data.get("patterns_observed", []),
            compressed_summary=data.get("compressed_summary", ""),
        )

        # Extract endpoints if present
        for ep in data.get("endpoints", []):
            if ep.get("method") and ep.get("path"):
                endpoints.append(
                    Endpoint(
                        method=ep["method"],
                        path=ep["path"],
                        handler_file=current_file,
                        handler_function=ep.get("handler_function", ""),
                        middleware=ep.get("middleware", []),
                        downstream_calls=ep.get("downstream_calls", []),
                    )
                )

    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("deep_diver_parse_failed", file=current_file, error=str(exc))
        summary = ModuleSummary(
            file_path=current_file,
            purpose="(LLM response could not be parsed)",
            compressed_summary=content[:200],
        )

    # Update module connections from the summary's internal deps
    connections: Graph = dict(state.modules.module_connections)
    if summary.internal_deps:
        connections[current_file] = summary.internal_deps

    logger.info(
        "deep_diver_complete",
        file=current_file,
        purpose=summary.purpose[:80],
        endpoints=len(endpoints),
    )

    # Build the return dict
    result: dict[str, object] = {
        "modules": {
            "analyzed": [*state.modules.analyzed, summary],
            "pending": remaining,
            "module_connections": connections,
            "api_endpoints": [*state.modules.api_endpoints, *endpoints],
            "feature_flows": list(state.modules.feature_flows),
        },
        "current_node": "module_deep_diver",
    }

    return result
