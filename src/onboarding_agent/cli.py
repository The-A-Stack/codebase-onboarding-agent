"""CLI entry point for running analysis from the command line."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from onboarding_agent.utils.logging import setup_logging


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="onboarding-agent",
        description="Analyze a codebase and generate onboarding documentation",
    )
    parser.add_argument("repo_url", help="GitHub repository URL to analyze")
    parser.add_argument(
        "--depth",
        choices=["quick", "standard", "deep"],
        default="standard",
        help="Analysis depth (default: standard)",
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Directory for generated files (default: ./output)",
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        default=["claude", "copilot", "cline", "aider"],
        help="Agent files to generate",
    )
    return parser.parse_args(argv)


def _write_results(result_data: dict[str, Any], output_dir: str) -> Path:
    """Write pipeline results to disk (sync — no pathlib in async context)."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Main JSON result
    output_file = out_path / "analysis_result.json"
    output_file.write_text(json.dumps(result_data, indent=2, default=str))

    # Write markdown report if present
    outputs = result_data.get("outputs", {})
    md = outputs.get("report_markdown", "")
    if md:
        (out_path / "onboarding_report.md").write_text(md)

    # Write agent files if present
    agent_files = outputs.get("agent_files", {})
    if agent_files:
        agent_dir = out_path / "agent_files"
        agent_dir.mkdir(exist_ok=True)
        for filename, content in agent_files.items():
            # Flatten paths like .github/copilot-instructions.md
            safe_name = filename.replace("/", "__")
            (agent_dir / safe_name).write_text(str(content))

    return output_file


def _print_summary(result_data: dict[str, Any], output_file: Path) -> None:
    """Print a human-readable summary of the analysis."""
    meta = result_data.get("metadata", {})
    deps = result_data.get("dependencies", {})
    modules = result_data.get("modules", {})

    print("\n=== Analysis Complete ===")  # noqa: T201
    print(f"  Repo:         {meta.get('repo_url', 'N/A')}")  # noqa: T201
    commit = str(meta.get("commit_hash", "N/A"))
    print(f"  Commit:       {commit[:8]}")  # noqa: T201
    print(f"  Entry points: {len(meta.get('entry_points', []))}")  # noqa: T201
    print(f"  Config files: {len(meta.get('config_files', []))}")  # noqa: T201
    print(f"  Packages:     {len(deps.get('packages', []))}")  # noqa: T201
    print(f"  Import graph: {len(deps.get('import_graph', {}))} nodes")  # noqa: T201
    print(f"  Env vars:     {len(deps.get('env_vars', []))}")  # noqa: T201
    print(f"  Analyzed:     {len(modules.get('analyzed', []))}")  # noqa: T201
    print(f"  Pending:      {len(modules.get('pending', []))}")  # noqa: T201
    print(f"  Endpoints:    {len(modules.get('api_endpoints', []))}")  # noqa: T201

    tech = deps.get("tech_stack")
    if tech:
        print(f"  Language:     {tech.get('primary_language', 'unknown')}")  # noqa: T201
        print(f"  Framework:    {tech.get('framework', 'unknown')}")  # noqa: T201

    patterns = result_data.get("patterns", {})
    if patterns:
        print(f"  Conventions:  {len(patterns.get('conventions', []))}")  # noqa: T201
        print(f"  Issues:       {len(patterns.get('inconsistencies', []))}")  # noqa: T201
        print(f"  Dead code:    {len(patterns.get('dead_code', []))}")  # noqa: T201
        print(f"  Hotspots:     {len(patterns.get('complexity_hotspots', []))}")  # noqa: T201

    scores_data = result_data.get("scores", {})
    if scores_data:
        overall = scores_data.get("overall_score", 0)
        print(f"\n  AI-Readiness: {overall}/10")  # noqa: T201
        dim_scores = scores_data.get("dimension_scores", {})
        for dim, val in dim_scores.items():
            print(f"    {dim:20s} {val}/10")  # noqa: T201
        recos = scores_data.get("recommendations", [])
        print(f"  Actions:      {len(recos)} recommendations")  # noqa: T201

    outputs = result_data.get("outputs", {})
    agent_files = outputs.get("agent_files", {})
    if agent_files:
        print(f"\n  Agent files:  {', '.join(agent_files.keys())}")  # noqa: T201

    readiness = outputs.get("readiness_report", {})
    if readiness and isinstance(readiness, dict):
        verdict = readiness.get("verdict", "")
        if verdict:
            print(f"  Verdict:      {verdict}")  # noqa: T201

    print(f"\n  Full results: {output_file}")  # noqa: T201


async def _run_pipeline(repo_url: str, depth: str, output_dir: str) -> None:
    """Execute the analysis pipeline (N1 → N2 → N3 cycle) and write results."""
    import structlog

    from onboarding_agent.models.state import CodebaseState, MetadataState
    from onboarding_agent.pipeline.graph import build_graph

    logger = structlog.get_logger()

    # Build initial state
    initial_state = CodebaseState(
        metadata=MetadataState(repo_url=repo_url),
        analysis_depth=depth,
    )

    # Build and compile the graph
    graph = build_graph()
    compiled = graph.compile()

    logger.info("pipeline_start", repo_url=repo_url, depth=depth)

    # Run the pipeline
    result = await compiled.ainvoke(initial_state)  # type: ignore[arg-type]

    logger.info("pipeline_complete")

    # Serialize result
    if hasattr(result, "model_dump"):
        result_data: dict[str, Any] = result.model_dump(mode="json")
    elif isinstance(result, dict):
        result_data = result
    else:
        result_data = dict(result)

    # Write and summarize (sync helpers)
    output_file = _write_results(result_data, output_dir)
    logger.info("output_written", path=str(output_file))
    _print_summary(result_data, output_file)


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = parse_args(argv)

    import structlog

    logger = structlog.get_logger()
    logger.info(
        "analysis_start",
        repo_url=args.repo_url,
        depth=args.depth,
        agents=args.agents,
    )

    try:
        asyncio.run(_run_pipeline(args.repo_url, args.depth, args.output_dir))
    except KeyboardInterrupt:
        logger.info("analysis_interrupted")
        sys.exit(130)
    except Exception:
        logger.exception("analysis_failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
