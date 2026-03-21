"""Node 7a: Documentation Generator — 2 LLM calls.

Produces the 12-section interactive onboarding document.
Sections:
  1. Project Identity Card
  2. Quick Start (Time to Running)
  3. Directory Structure
  4. Configuration & Secrets
  5. Architecture Overview (Module Dependency Graph)
  6. Feature Flow Maps
  7. External Services / APIs (consumed + exposed)
  8. Testing
  9. Development Workflow (CI/CD, linting, formatting)
  10. Patterns & Conventions
  11. Known Issues & Gotchas
  12. Suggested First Tasks
"""

from __future__ import annotations

import json

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.models.types import Tree
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()


def _truncate_tree(tree: Tree, max_depth: int = 3, depth: int = 0) -> Tree:
    if depth >= max_depth:
        return {"...": "truncated"}
    result: Tree = {}
    for k, v in tree.items():
        if isinstance(v, dict):
            result[k] = _truncate_tree(v, max_depth, depth + 1)
        else:
            result[k] = v
    return result


def _safe_str(value: str | None, fallback: str = "") -> str:
    """Safely convert a value to string, avoiding 'None' display."""
    if value is None or value == "None" or value == "":
        return fallback
    return value


def _format_tech_field(label: str, value: str | None, version: str | None = None) -> str:
    """Format a tech stack field, handling None/empty gracefully."""
    val = _safe_str(value)
    if not val:
        return ""
    ver = _safe_str(version)
    if ver:
        return f"{val} {ver}"
    return val


# --- Deterministic sections (no LLM needed) ---


def _build_section1(state: CodebaseState) -> dict[str, object]:
    """Section 1: Project Identity Card."""
    tech = state.dependencies.tech_stack
    tree_2level = _truncate_tree(state.metadata.directory_tree, max_depth=2)
    license_info = state.metadata.license_info

    # Build clean tech stack dict, filtering out None/empty values
    tech_data: dict[str, object] = {}
    if tech:
        tech_data = {
            k: v for k, v in tech.model_dump().items()
            if v is not None and v != "" and v != []
        }

    return {
        "title": "Project Identity Card",
        "repo_url": state.metadata.repo_url,
        "commit_hash": state.metadata.commit_hash,
        "tech_stack": tech_data,
        "directory_tree_preview": tree_2level,
        "entry_points": state.metadata.entry_points,
        "config_files": [c.model_dump() for c in state.metadata.config_files],
        "license": license_info.model_dump() if license_info.is_present else {},
        "total_source_files": state.metadata.total_source_files,
        "total_lines_of_code": (
            state.patterns.code_quality.total_lines_of_code
            if state.patterns.code_quality
            else 0
        ),
    }


def _build_section2(state: CodebaseState) -> dict[str, object]:
    """Section 2: Quick Start (Time to Running)."""
    tech = state.dependencies.tech_stack
    env_vars = []
    for ev in state.dependencies.env_vars:
        env_vars.append(
            {
                "name": ev.name,
                "files_used_in": ev.files_used_in,
                "expected_format": ev.expected_format,
                "has_default": ev.has_default,
            }
        )

    # Build prerequisites
    prerequisites: list[dict[str, str]] = []
    if tech:
        lang = _safe_str(tech.primary_language)
        lang_ver = _safe_str(tech.language_version)
        if lang:
            prereq = f"{lang}"
            if lang_ver:
                prereq += f" {lang_ver}"
            prerequisites.append({"name": lang, "version": lang_ver})

    # Build required env vars (ones without defaults)
    required_env_vars = [ev for ev in state.dependencies.env_vars if not ev.has_default]

    # Determine package install command
    install_command = ""
    if tech:
        build_tool = _safe_str(tech.build_tool)
        if build_tool:
            if "pip" in build_tool.lower():
                install_command = "pip install -r requirements.txt"
            elif "uv" in build_tool.lower():
                install_command = "uv sync"
            elif "npm" in build_tool.lower():
                install_command = "npm install"
            elif "yarn" in build_tool.lower():
                install_command = "yarn install"
            elif "pnpm" in build_tool.lower():
                install_command = "pnpm install"

    # Determine run command from entry points
    run_command = ""
    entry_points = state.metadata.entry_points
    if entry_points:
        main_entry = entry_points[0]
        if main_entry.endswith(".py"):
            run_command = f"python {main_entry}"
        elif main_entry.endswith((".ts", ".js")):
            run_command = f"node {main_entry}"

    return {
        "title": "Quick Start",
        "prerequisites": prerequisites,
        "required_env_vars": [
            {"name": ev.name, "format": ev.expected_format}
            for ev in required_env_vars
        ],
        "install_command": install_command,
        "run_command": run_command,
        "packages_count": len(state.dependencies.packages),
        "packages": [
            {"name": p.name, "version": p.version}
            for p in state.dependencies.packages[:30]
        ],
    }


def _build_section3(state: CodebaseState) -> dict[str, object]:
    """Section 3: Directory Structure."""
    tree_full = _truncate_tree(state.metadata.directory_tree, max_depth=4)

    return {
        "title": "Directory Structure",
        "directory_tree": tree_full,
        "total_source_files": state.metadata.total_source_files,
        "entry_points": state.metadata.entry_points,
        "config_files": [
            {"name": c.name, "type": c.file_type, "path": c.path}
            for c in state.metadata.config_files
        ],
    }


def _build_section4(state: CodebaseState) -> dict[str, object]:
    """Section 4: Configuration & Secrets."""
    env_vars = []
    for ev in state.dependencies.env_vars:
        env_vars.append(
            {
                "name": ev.name,
                "files_used_in": ev.files_used_in,
                "expected_format": ev.expected_format,
                "has_default": ev.has_default,
            }
        )

    # Check for .env.example
    has_env_example = any(
        c.name in (".env.example", ".env.sample")
        for c in state.metadata.config_files
    )

    # Separate API keys from other env vars
    api_keys = [ev for ev in env_vars if ev.get("expected_format") == "API_KEY"]
    urls = [ev for ev in env_vars if ev.get("expected_format") == "URL"]
    other_vars = [
        ev for ev in env_vars
        if ev.get("expected_format") not in ("API_KEY", "URL")
    ]

    return {
        "title": "Configuration & Secrets",
        "env_vars": env_vars,
        "api_keys": api_keys,
        "urls": urls,
        "other_config_vars": other_vars,
        "has_env_example": has_env_example,
        "config_files": [
            {"name": c.name, "type": c.file_type}
            for c in state.metadata.config_files
            if c.file_type in ("env", "config")
        ],
    }


def _build_section5(state: CodebaseState) -> dict[str, object]:
    """Section 5: Architecture Overview (Module Dependency Graph)."""
    return {
        "title": "Architecture Overview",
        "import_graph": state.dependencies.import_graph,
        "module_connections": state.modules.module_connections,
        "analyzed_modules": [
            {
                "file": m.file_path,
                "purpose": m.purpose,
                "interfaces": [i.name for i in m.public_interfaces],
                "internal_deps": m.internal_deps[:5],
                "external_deps": m.external_deps[:5],
            }
            for m in state.modules.analyzed
        ],
        "total_modules": len(state.modules.analyzed),
    }


def _build_section7(state: CodebaseState) -> dict[str, object]:
    """Section 7: External Services / APIs."""
    # Exposed endpoints (APIs this repo provides)
    exposed_endpoints = [ep.model_dump() for ep in state.modules.api_endpoints]

    # Consumed external APIs
    consumed_apis = [api.model_dump() for api in state.dependencies.external_apis]

    return {
        "title": "External Services & APIs",
        "exposed_endpoints": exposed_endpoints,
        "exposed_count": len(exposed_endpoints),
        "consumed_apis": consumed_apis,
        "consumed_count": len(consumed_apis),
    }


def _build_section8(state: CodebaseState) -> dict[str, object]:
    """Section 8: Testing."""
    testing = state.metadata.testing_info

    return {
        "title": "Testing",
        "has_tests": testing.has_tests,
        "test_framework": testing.test_framework or "None found",
        "test_file_count": testing.test_file_count,
        "test_files": testing.test_files[:10],
        "test_directories": testing.test_directories,
        "has_ci": testing.has_ci,
        "ci_config_files": testing.ci_config_files,
        "coverage_configured": testing.coverage_configured,
    }


def _build_section9(state: CodebaseState) -> dict[str, object]:
    """Section 9: Development Workflow."""
    tech = state.dependencies.tech_stack
    quality = state.patterns.code_quality
    testing = state.metadata.testing_info

    return {
        "title": "Development Workflow",
        "linter": _safe_str(tech.linter if tech else None, "None configured"),
        "formatter": _safe_str(tech.formatter if tech else None, "None configured"),
        "has_pre_commit_hooks": quality.has_pre_commit_hooks if quality else False,
        "has_ci": testing.has_ci,
        "ci_config_files": testing.ci_config_files,
        "build_tool": _safe_str(tech.build_tool if tech else None, "None detected"),
        "code_quality": quality.model_dump() if quality else {},
    }


def _build_section10(state: CodebaseState) -> dict[str, object]:
    """Section 10: Patterns & Conventions."""
    return {
        "title": "Patterns & Conventions",
        "conventions": [c.model_dump() for c in state.patterns.conventions],
        "inconsistencies": [i.model_dump() for i in state.patterns.inconsistencies],
        "dead_code": state.patterns.dead_code,
        "complexity_hotspots": [h.model_dump() for h in state.patterns.complexity_hotspots],
    }


# --- LLM-generated sections ---

_NARRATIVE_SYSTEM_PROMPT = (
    "You are a technical writer creating onboarding documentation for a developer "
    "who has never seen this codebase before. Your goal is to help them understand "
    "the codebase and start contributing quickly.\n\n"
    "Respond with valid JSON matching this schema:\n"
    "{\n"
    '  "section6_feature_flows": [\n'
    "    {\n"
    '      "name": "feature name (user-facing action, e.g. \'Fetch Weather Data\')",\n'
    '      "steps": [\n'
    '        {"step_number": 1, "file": "str", "function": "str", '
    '"action": "concise description", "external_calls": ["str"]}\n'
    "      ]\n"
    "    }\n"
    "  ],\n"
    '  "section11_known_issues": [\n'
    "    {\n"
    '      "issue": "description of the gotcha or known issue",\n'
    '      "category": "setup|platform|runtime|dependency",\n'
    '      "workaround": "how to fix or work around it"\n'
    "    }\n"
    "  ],\n"
    '  "section12_first_tasks": [\n'
    "    {\n"
    '      "task": "actionable task description (a goal, not a file to stare at)",\n'
    '      "difficulty": "beginner|intermediate|advanced",\n'
    '      "files_involved": ["file paths"],\n'
    '      "why": "why this is a good first task"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Feature flows: trace 3-5 major USER-FACING features through the codebase. "
    "Use sequential step_number (1, 2, 3...) to show progression.\n"
    "- Known issues: identify 3-5 gotchas a new developer would likely hit "
    "(platform quirks, missing deps, common config mistakes, env-specific issues). "
    "Be specific and practical.\n"
    "- First tasks: suggest 5-7 ACTIONABLE tasks (not just files to read). "
    'Each task should be a goal like "Add error handling for API timeouts" or '
    '"Get the app running locally with your own API key", NOT '
    '"Read main.py to understand the structure".\n'
    "- Be specific with file paths and function names.\n"
    "- Only respond with the JSON object."
)


def _build_narrative_prompt(state: CodebaseState) -> str:
    """Build prompt for LLM-generated narrative sections."""
    modules_text = "\n".join(
        f"- **{m.file_path}**: {m.purpose} "
        f"(interfaces: {', '.join(i.name for i in m.public_interfaces[:3])})"
        for m in state.modules.analyzed
    )

    endpoints_text = "\n".join(
        f"- {ep.method} {ep.path} -> {ep.handler_file}:{ep.handler_function}"
        for ep in state.modules.api_endpoints
    )

    external_apis_text = "\n".join(
        f"- {api.name}: {api.base_url} (auth: {api.auth_method or 'unknown'})"
        for api in state.dependencies.external_apis
    )

    tech = state.dependencies.tech_stack
    tech_text = ""
    if tech:
        tech_text = (
            f"\n## Tech Stack\n"
            f"- Language: {_safe_str(tech.primary_language, 'unknown')}"
            f" {_safe_str(tech.language_version)}\n"
            f"- Framework: {_safe_str(tech.framework, 'none')}\n"
            f"- Key libs: {', '.join(tech.key_libraries[:8])}\n"
        )

    env_vars_text = "\n".join(
        f"- {ev.name} ({ev.expected_format or 'string'})"
        f"{' — required' if not ev.has_default else ''}"
        for ev in state.dependencies.env_vars
    )

    # Testing info
    testing = state.metadata.testing_info
    testing_text = f"\n## Testing\n- Has tests: {testing.has_tests}\n"
    if testing.test_framework:
        testing_text += f"- Framework: {testing.test_framework}\n"
    testing_text += f"- Test files: {testing.test_file_count}\n"

    return (
        f"## Analyzed Modules\n{modules_text}\n\n"
        f"## API Endpoints (exposed by this repo)\n{endpoints_text or '(none)'}\n\n"
        f"## External APIs Consumed\n{external_apis_text or '(none detected)'}\n\n"
        f"## Environment Variables\n{env_vars_text or '(none)'}\n\n"
        f"## Import Graph\n{json.dumps(state.dependencies.import_graph, indent=1)}\n\n"
        f"## Entry Points\n{', '.join(state.metadata.entry_points)}\n"
        f"{tech_text}"
        f"{testing_text}\n"
        "Generate feature flow maps, known issues/gotchas, and suggested first tasks."
    )


_OVERVIEW_SYSTEM_PROMPT = (
    "You are a technical writer. Given codebase analysis data, write "
    "a concise, ACCURATE project overview and step-by-step setup instructions.\n\n"
    "Respond with valid JSON:\n"
    "{\n"
    '  "project_description": "1-2 sentence description of WHAT the project actually does '
    '(be specific — name the UI framework, the API it consumes, the user-facing purpose). '
    "Do NOT describe it generically as 'data processing' just because pandas is in "
    "requirements. Look at the actual module names and entry points to understand "
    'the real purpose.",\n'
    '  "setup_steps": [\n'
    '    {"step": 1, "command": "copy-paste-ready shell command", '
    '"explanation": "what this step does"}\n'
    "  ],\n"
    '  "run_command": "the exact command to run the application"\n'
    "}\n\n"
    "Rules:\n"
    "- project_description: Be accurate and specific. If it's a weather app, "
    'say "weather app", not "data processing tool". If it uses Tkinter, say '
    '"Tkinter desktop application", not "framework: None".\n'
    "- setup_steps: Include ALL steps from clone to running. Must include:\n"
    "  1. Clone command\n"
    "  2. Virtual environment / node_modules setup (if applicable)\n"
    "  3. Dependency installation (the exact command)\n"
    "  4. Environment variable configuration (if any required)\n"
    "  5. Run command\n"
    "- All commands must be copy-paste-ready.\n"
    "- run_command: The exact command to start the application.\n"
    "- Only respond with the JSON object."
)


def _build_overview_prompt(state: CodebaseState) -> str:
    tech = state.dependencies.tech_stack
    tech_text = ""
    if tech:
        tech_text = (
            f"Language: {_safe_str(tech.primary_language, 'unknown')}"
            f" {_safe_str(tech.language_version)}\n"
            f"Framework: {_safe_str(tech.framework, 'none')}"
            f" {_safe_str(tech.framework_version)}\n"
            f"Build: {_safe_str(tech.build_tool, 'unknown')}\n"
            f"Test: {_safe_str(tech.test_framework, 'none found')}\n"
            f"Key libs: {', '.join(tech.key_libraries[:8])}\n"
        )

    configs = ", ".join(c.name for c in state.metadata.config_files[:10])
    entry_pts = ", ".join(state.metadata.entry_points[:5])

    # Module purposes for better project understanding
    module_purposes = "\n".join(
        f"- {m.file_path}: {m.purpose}"
        for m in state.modules.analyzed[:10]
    )

    # External APIs consumed
    ext_apis = "\n".join(
        f"- {api.name} ({api.base_url})"
        for api in state.dependencies.external_apis
    )

    # Required env vars
    required_vars = ", ".join(
        ev.name for ev in state.dependencies.env_vars if not ev.has_default
    )

    return (
        f"## Tech Stack\n{tech_text}\n"
        f"## Config Files\n{configs}\n"
        f"## Entry Points\n{entry_pts}\n"
        f"## Module Purposes\n{module_purposes}\n"
        f"## External APIs Consumed\n{ext_apis or '(none)'}\n"
        f"## Required Environment Variables\n{required_vars or '(none)'}\n"
        f"## Packages\n{len(state.dependencies.packages)} dependencies\n\n"
        "Write an accurate project description and complete setup steps."
    )


async def doc_generator(state: CodebaseState) -> dict[str, object]:
    """Generate the 12-section onboarding report.

    Sections 1-5, 7-10 are built deterministically from state.
    Sections 6, 11, 12 use 1 LLM call for narrative content.
    Section 1 is enriched with 1 LLM call for project description.
    Section 2 is enriched with LLM-generated setup steps.
    """
    logger.info("doc_generator_start")

    llm = LLMService()

    # Deterministic sections
    section1 = _build_section1(state)
    section2 = _build_section2(state)
    section3 = _build_section3(state)
    section4 = _build_section4(state)
    section5 = _build_section5(state)
    section7 = _build_section7(state)
    section8 = _build_section8(state)
    section9 = _build_section9(state)
    section10 = _build_section10(state)

    # LLM call 1: project overview + setup steps + run command
    overview_response = await llm.complete(
        system_prompt=_OVERVIEW_SYSTEM_PROMPT,
        user_prompt=_build_overview_prompt(state),
    )

    raw = overview_response["content"].strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    try:
        overview_data = json.loads(raw)
        section1["project_description"] = overview_data.get("project_description", "")
        section2["setup_steps"] = overview_data.get("setup_steps", [])
        # Prefer LLM-inferred run command over heuristic
        llm_run_cmd = overview_data.get("run_command", "")
        if llm_run_cmd:
            section2["run_command"] = llm_run_cmd
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("overview_parse_failed", error=str(exc))

    # LLM call 2: feature flows + known issues + first tasks
    narrative_response = await llm.complete(
        system_prompt=_NARRATIVE_SYSTEM_PROMPT,
        user_prompt=_build_narrative_prompt(state),
    )

    raw = narrative_response["content"].strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]).strip()

    section6: dict[str, object] = {
        "title": "Feature Flow Maps",
        "flows": [],
    }
    section11: dict[str, object] = {
        "title": "Known Issues & Gotchas",
        "issues": [],
    }
    section12: dict[str, object] = {
        "title": "Suggested First Tasks",
        "tasks": [],
    }

    try:
        narrative_data = json.loads(raw)
        section6["flows"] = narrative_data.get("section6_feature_flows", [])
        section11["issues"] = narrative_data.get("section11_known_issues", [])
        section12["tasks"] = narrative_data.get("section12_first_tasks", [])
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("narrative_parse_failed", error=str(exc))

    # Assemble report
    report_json: dict[str, object] = {
        "section1_identity": section1,
        "section2_quickstart": section2,
        "section3_directory": section3,
        "section4_config": section4,
        "section5_architecture": section5,
        "section6_flows": section6,
        "section7_external_services": section7,
        "section8_testing": section8,
        "section9_dev_workflow": section9,
        "section10_patterns": section10,
        "section11_known_issues": section11,
        "section12_first_tasks": section12,
    }

    # Generate markdown version
    report_md = _render_markdown(report_json, state)

    logger.info("doc_generator_complete", sections=12)

    return {
        "outputs": {
            "report_json": report_json,
            "report_markdown": report_md,
        },
        "current_node": "doc_generator",
    }


def _render_markdown(report: dict[str, object], state: CodebaseState) -> str:
    """Render the report as a Markdown document."""
    lines: list[str] = []
    lines.append("# Codebase Onboarding Report\n")
    lines.append(f"**Repository:** {state.metadata.repo_url}")
    lines.append(f"**Commit:** {state.metadata.commit_hash[:8]}\n")

    # Section 1: Project Identity Card
    s1 = report.get("section1_identity", {})
    lines.append("## 1. Project Identity Card\n")
    desc = s1.get("project_description", "") if isinstance(s1, dict) else ""
    if desc:
        lines.append(f"{desc}\n")

    tech = state.dependencies.tech_stack
    if tech:
        lang = _format_tech_field("Language", tech.primary_language, tech.language_version)
        fw = _format_tech_field("Framework", tech.framework, tech.framework_version)
        build = _safe_str(tech.build_tool)
        test = _safe_str(tech.test_framework)
        if lang:
            lines.append(f"- **Language:** {lang}")
        if fw:
            lines.append(f"- **Framework:** {fw}")
        if build:
            lines.append(f"- **Build:** {build}")
        if test:
            lines.append(f"- **Test:** {test}")
        if tech.linter:
            lines.append(f"- **Linter:** {tech.linter}")
        if tech.formatter:
            lines.append(f"- **Formatter:** {tech.formatter}")
        lines.append("")

    license_info = state.metadata.license_info
    if license_info.is_present:
        lines.append(f"- **License:** {license_info.license_type} ({license_info.license_file})")

    lines.append(f"- **Source Files:** {state.metadata.total_source_files}")
    quality = state.patterns.code_quality
    if quality and quality.total_lines_of_code:
        lines.append(f"- **Lines of Code:** ~{quality.total_lines_of_code}")
    lines.append("")

    # Section 2: Quick Start
    s2 = report.get("section2_quickstart", {})
    lines.append("## 2. Quick Start\n")
    setup_steps = s2.get("setup_steps", []) if isinstance(s2, dict) else []
    if setup_steps:
        for step in setup_steps:
            if isinstance(step, dict):
                cmd = step.get("command", "")
                explanation = step.get("explanation", "")
                step_num = step.get("step", "")
                lines.append(f"{step_num}. {explanation}")
                if cmd:
                    lines.append(f"   ```bash\n   {cmd}\n   ```")
        lines.append("")
    run_cmd = s2.get("run_command", "") if isinstance(s2, dict) else ""
    if run_cmd:
        lines.append(f"**Run command:** `{run_cmd}`\n")

    # Required env vars
    req_vars = s2.get("required_env_vars", []) if isinstance(s2, dict) else []
    if req_vars:
        lines.append("**Required environment variables:**")
        for ev in req_vars:
            if isinstance(ev, dict):
                lines.append(f"- `{ev.get('name', '')}` ({ev.get('format', 'string')})")
        lines.append("")

    # Section 3: Directory Structure
    lines.append("## 3. Directory Structure\n")
    lines.append(f"```")
    tree_data = report.get("section3_directory", {})
    if isinstance(tree_data, dict):
        tree = tree_data.get("directory_tree", {})
        lines.append(_tree_to_text(tree if isinstance(tree, dict) else {}))
    lines.append("```\n")

    # Section 4: Configuration & Secrets
    lines.append("## 4. Configuration & Secrets\n")
    if state.dependencies.env_vars:
        lines.append("| Variable | Format | Required | Used In |")
        lines.append("|----------|--------|----------|---------|")
        for ev in state.dependencies.env_vars:
            required = "Yes" if not ev.has_default else "No"
            files = ", ".join(ev.files_used_in[:3])
            lines.append(
                f"| `{ev.name}` | {ev.expected_format or 'string'} | {required} | {files} |"
            )
    else:
        lines.append("No environment variables detected.\n")
    lines.append("")

    # Section 5: Architecture Overview
    lines.append("## 5. Architecture Overview\n")
    lines.append(
        f"{len(state.dependencies.import_graph)} modules with import relationships.\n"
    )
    for m in state.modules.analyzed[:10]:
        lines.append(f"- **`{m.file_path}`**: {m.purpose}")
    lines.append("")

    # Section 6: Feature Flows
    s6 = report.get("section6_flows", {})
    lines.append("## 6. Feature Flows\n")
    flows = s6.get("flows", []) if isinstance(s6, dict) else []
    if flows:
        for flow in flows:
            if isinstance(flow, dict):
                lines.append(f"### {flow.get('name', 'Flow')}\n")
                for i, step in enumerate(flow.get("steps", []), 1):
                    if isinstance(step, dict):
                        fn = step.get("function", "")
                        fn_str = f".{fn}()" if fn else ""
                        lines.append(
                            f"{i}. `{step.get('file', '')}`{fn_str}"
                            f" — {step.get('action', '')}"
                        )
                lines.append("")
    else:
        lines.append("No feature flows traced.\n")

    # Section 7: External Services / APIs
    lines.append("## 7. External Services & APIs\n")
    if state.modules.api_endpoints:
        lines.append("### Exposed Endpoints\n")
        lines.append("| Method | Path | Handler |")
        lines.append("|--------|------|---------|")
        for ep in state.modules.api_endpoints:
            lines.append(f"| {ep.method} | {ep.path} | `{ep.handler_file}` |")
        lines.append("")

    if state.dependencies.external_apis:
        lines.append("### Consumed External APIs\n")
        for api in state.dependencies.external_apis:
            lines.append(f"- **{api.name}** (`{api.base_url}`)")
            if api.auth_method:
                lines.append(f"  - Auth: {api.auth_method}")
            if api.auth_env_var:
                lines.append(f"  - Env var: `{api.auth_env_var}`")
            if api.rate_limit_info:
                lines.append(f"  - Rate limit: {api.rate_limit_info}")
        lines.append("")

    if not state.modules.api_endpoints and not state.dependencies.external_apis:
        lines.append("No API endpoints or external services detected.\n")

    # Section 8: Testing
    lines.append("## 8. Testing\n")
    testing = state.metadata.testing_info
    if testing.has_tests:
        lines.append(f"- **Framework:** {testing.test_framework or 'unknown'}")
        lines.append(f"- **Test files:** {testing.test_file_count}")
        if testing.test_directories:
            lines.append(f"- **Test directories:** {', '.join(testing.test_directories)}")
        if testing.coverage_configured:
            lines.append("- **Coverage:** Configured")
    else:
        lines.append(
            "No test suite found. Consider adding tests with "
            f"{_safe_str(testing.test_framework, 'pytest/jest')}.\n"
        )

    if testing.has_ci:
        lines.append(f"\n**CI/CD:** {', '.join(testing.ci_config_files)}")
    lines.append("")

    # Section 9: Development Workflow
    lines.append("## 9. Development Workflow\n")
    if tech:
        if tech.linter:
            lines.append(f"- **Linter:** {tech.linter}")
        if tech.formatter:
            lines.append(f"- **Formatter:** {tech.formatter}")
    if quality and quality.has_pre_commit_hooks:
        lines.append("- **Pre-commit hooks:** Configured")
    if not (tech and (tech.linter or tech.formatter)) and not (
        quality and quality.has_pre_commit_hooks
    ):
        lines.append("No linter, formatter, or pre-commit hooks detected.\n")
    lines.append("")

    # Section 10: Patterns & Conventions
    lines.append("## 10. Patterns & Conventions\n")
    for conv in state.patterns.conventions:
        lines.append(f"- **{conv.name}**: {conv.description}")
        if conv.example_files:
            lines.append(f"  - Files: {', '.join(conv.example_files[:3])}")
    lines.append("")

    # Code quality signals
    if quality:
        lines.append("### Code Quality Signals\n")
        lines.append(f"- Type hints: {quality.type_hint_coverage}")
        lines.append(f"- Docstrings: {quality.docstring_coverage}")
        lines.append("")

    # Section 11: Known Issues & Gotchas
    s11 = report.get("section11_known_issues", {})
    lines.append("## 11. Known Issues & Gotchas\n")
    issues = s11.get("issues", []) if isinstance(s11, dict) else []
    if issues:
        for issue in issues:
            if isinstance(issue, dict):
                cat = issue.get("category", "")
                cat_str = f" [{cat}]" if cat else ""
                lines.append(f"- **{issue.get('issue', '')}**{cat_str}")
                workaround = issue.get("workaround", "")
                if workaround:
                    lines.append(f"  - Workaround: {workaround}")
    else:
        lines.append("No known issues identified.\n")
    lines.append("")

    # Section 12: Suggested First Tasks
    s12 = report.get("section12_first_tasks", {})
    lines.append("## 12. Suggested First Tasks\n")
    tasks = s12.get("tasks", []) if isinstance(s12, dict) else []
    if tasks:
        for i, task in enumerate(tasks, 1):
            if isinstance(task, dict):
                difficulty = task.get("difficulty", "")
                diff_str = f" [{difficulty}]" if difficulty else ""
                lines.append(f"{i}. **{task.get('task', '')}**{diff_str}")
                why = task.get("why", "")
                if why:
                    lines.append(f"   - {why}")
                files = task.get("files_involved", [])
                if files:
                    lines.append(f"   - Files: {', '.join(files)}")
    else:
        lines.append("No tasks generated.\n")
    lines.append("")

    return "\n".join(lines)


def _tree_to_text(tree: dict, prefix: str = "", is_last: bool = True) -> str:
    """Convert a directory tree dict to a text-based tree view."""
    lines: list[str] = []
    items = list(tree.items())

    for i, (name, value) in enumerate(items):
        is_last_item = i == len(items) - 1
        connector = "└── " if is_last_item else "├── "
        extension = "    " if is_last_item else "│   "

        if isinstance(value, dict):
            if name == "..." and value == "truncated":
                lines.append(f"{prefix}{connector}...")
            else:
                lines.append(f"{prefix}{connector}{name}/")
                subtree = _tree_to_text(value, prefix + extension, is_last_item)
                if subtree:
                    lines.append(subtree)
        else:
            lines.append(f"{prefix}{connector}{name}")

    return "\n".join(lines)
