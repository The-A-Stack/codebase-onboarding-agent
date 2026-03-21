"""Node 2: Dependency Analyzer — 1 LLM call.

Parses package manifests, builds the internal import graph, extracts env vars,
and makes one LLM call to synthesize the technology profile.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog

from onboarding_agent.models.state import CodebaseState
from onboarding_agent.models.types import EnvVar, ExternalAPI, Graph, Package, TechProfile
from onboarding_agent.parsers.base import BaseParser
from onboarding_agent.parsers.python_parser import PythonParser
from onboarding_agent.parsers.typescript_parser import TypeScriptParser
from onboarding_agent.services.llm import LLMService

logger = structlog.get_logger()

_PARSERS: list[BaseParser] = [PythonParser(), TypeScriptParser()]

# --- Package manifest parsing ---


def _parse_pyproject_toml(path: Path) -> list[Package]:
    """Extract dependencies from pyproject.toml."""
    packages: list[Package] = []
    content = path.read_text(encoding="utf-8", errors="replace")

    # Match lines under [project.dependencies] or [tool.poetry.dependencies]
    # Simple regex approach: find dependency specifiers like 'package>=version'
    dep_pattern = re.compile(r'^"?([a-zA-Z0-9_-]+)\s*(?:[><=!~]+\s*[\d.*]+)?(?:\[.*?\])?"?,?\s*$')

    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()

        # Detect dependency sections
        if stripped in (
            "[project]",
            "[tool.poetry]",
        ):
            continue

        if "dependencies" in stripped and "=" in stripped and "[" in stripped:
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if stripped == "]":
            in_deps = False
            continue

        if in_deps:
            match = dep_pattern.match(stripped)
            if match:
                name = match.group(1)
                # Extract version if present
                version = ""
                ver_match = re.search(r"[><=!~]+\s*([\d.*]+)", stripped)
                if ver_match:
                    version = ver_match.group(1)
                packages.append(Package(name=name, version=version))

    return packages


def _parse_requirements_txt(path: Path) -> list[Package]:
    """Extract dependencies from requirements.txt / requirements/*.txt."""
    packages: list[Package] = []
    content = path.read_text(encoding="utf-8", errors="replace")

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Handle 'package==version', 'package>=version', 'package'
        match = re.match(r"^([a-zA-Z0-9_.-]+)\s*(?:([><=!~]+)\s*([\d.*]+))?", line)
        if match:
            name = match.group(1)
            version = match.group(3) or ""
            packages.append(Package(name=name, version=version))

    return packages


def _parse_package_json(path: Path) -> list[Package]:
    """Extract dependencies from package.json."""
    packages: list[Package] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return packages

    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps: dict[str, str] = data.get(section, {})
        for name, version in deps.items():
            # Strip leading ^ ~ >= etc for cleaner version
            clean_ver = re.sub(r"^[^0-9]*", "", version)
            category = "dev" if section == "devDependencies" else ""
            packages.append(Package(name=name, version=clean_ver, category=category))

    return packages


def _parse_packages(repo_path: Path) -> list[Package]:
    """Parse all recognized package manifests in the repo root."""
    all_packages: list[Package] = []

    manifest_parsers: list[tuple[str, Any]] = [
        ("pyproject.toml", _parse_pyproject_toml),
        ("setup.cfg", _parse_requirements_txt),  # similar enough format for deps
        ("package.json", _parse_package_json),
    ]

    for filename, parser_fn in manifest_parsers:
        manifest = repo_path / filename
        if manifest.is_file():
            all_packages.extend(parser_fn(manifest))

    # Also check requirements.txt variants
    for req_file in repo_path.glob("requirements*.txt"):
        all_packages.extend(_parse_requirements_txt(req_file))

    # Deduplicate by name (keep first occurrence)
    seen: set[str] = set()
    deduped: list[Package] = []
    for pkg in all_packages:
        lower_name = pkg.name.lower()
        if lower_name not in seen:
            seen.add(lower_name)
            deduped.append(pkg)

    return deduped


# --- Import graph building ---

_SKIP_DIRS: set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".eggs",
    ".idea",
    ".vscode",
}

_SOURCE_EXTENSIONS: set[str] = {
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ipynb",
}


def _build_import_graph(repo_path: Path, source_files: list[str]) -> Graph:
    """Build a directed graph of file-to-file internal imports.

    Keys are source file paths (relative to repo root).
    Values are lists of internal files that key imports from.
    """
    graph: Graph = {}

    # Build a lookup: module name -> relative file path
    # For Python: 'onboarding_agent.models.state' -> 'src/onboarding_agent/models/state.py'
    # For JS/TS: './utils/helpers' -> 'src/utils/helpers.ts'
    file_set = set(source_files)

    for rel_path in source_files:
        full_path = repo_path / rel_path
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Pick the right parser
        parser: BaseParser | None = None
        for p in _PARSERS:
            if p.can_parse(full_path):
                parser = p
                break

        if parser is None:
            continue

        imports = parser.extract_imports(full_path, content)
        internal_deps: list[str] = []

        for imp in imports:
            resolved = _resolve_import(rel_path, imp.module, imp.is_relative, file_set)
            if resolved:
                internal_deps.append(resolved)

        if internal_deps:
            graph[rel_path] = sorted(set(internal_deps))

    return graph


def _resolve_import(
    source_file: str,
    module: str,
    is_relative: bool,
    file_set: set[str],
) -> str | None:
    """Try to resolve an import to an internal file path.

    Returns the relative file path if found in file_set, else None.
    """
    if not module:
        return None

    if is_relative or module.startswith("."):
        # Relative import — resolve relative to source file's directory
        source_dir = str(Path(source_file).parent)
        # Strip leading dots from module
        clean_module = module.lstrip(".")
        if clean_module:
            candidate_base = str(Path(source_dir) / clean_module.replace(".", "/"))
        else:
            candidate_base = source_dir
        return _find_file_match(candidate_base, file_set)

    # Absolute import — try to find it as a file path
    candidate_base = module.replace(".", "/")
    return _find_file_match(candidate_base, file_set)


def _find_file_match(candidate_base: str, file_set: set[str]) -> str | None:
    """Given a base path (without extension), find a matching file in the set."""
    # Try direct match with various extensions
    for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        candidate = candidate_base + ext
        if candidate in file_set:
            return candidate

    # Try as directory with index file
    for index in ("__init__.py", "index.ts", "index.js", "index.tsx", "index.jsx"):
        candidate = candidate_base + "/" + index
        if candidate in file_set:
            return candidate

    # Try matching within src/ or other common prefixes
    for prefix in ("src/", "lib/", "app/"):
        for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            candidate = prefix + candidate_base + ext
            if candidate in file_set:
                return candidate

    return None


# --- Env var extraction ---


def _extract_all_env_vars(repo_path: Path, source_files: list[str]) -> list[EnvVar]:
    """Scan all source files for environment variable references."""
    var_files: dict[str, list[str]] = {}  # var_name -> list of files

    for rel_path in source_files:
        full_path = repo_path / rel_path
        if not full_path.is_file():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for parser in _PARSERS:
            if parser.can_parse(full_path):
                vars_found = parser.extract_env_vars(content)
                for var_name in vars_found:
                    var_files.setdefault(var_name, []).append(rel_path)
                break

    # Also scan .env.example if it exists
    env_example = repo_path / ".env.example"
    defaults_set: set[str] = set()
    if env_example.is_file():
        for line in env_example.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                var_name = line.split("=", 1)[0].strip()
                var_files.setdefault(var_name, [])
                # If there's a non-empty value after =, it has a default
                value = line.split("=", 1)[1].strip()
                if value and value not in ('""', "''", '""', "''"):
                    defaults_set.add(var_name)

    env_vars: list[EnvVar] = []
    for var_name, files in sorted(var_files.items()):
        expected_format = _guess_env_format(var_name)
        env_vars.append(
            EnvVar(
                name=var_name,
                files_used_in=sorted(set(files)),
                expected_format=expected_format,
                has_default=var_name in defaults_set,
            )
        )

    return env_vars


def _guess_env_format(var_name: str) -> str:
    """Heuristic guess at the expected format based on variable name."""
    upper = var_name.upper()
    if any(k in upper for k in ("URL", "URI", "ENDPOINT", "HOST")):
        return "URL"
    if any(k in upper for k in ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")):
        return "API_KEY"
    if any(k in upper for k in ("PORT", "TIMEOUT", "RETRIES", "MAX", "MIN", "LIMIT", "COUNT")):
        return "number"
    if any(k in upper for k in ("DEBUG", "ENABLE", "DISABLE", "VERBOSE", "FLAG")):
        return "boolean"
    return ""


# --- External API consumption detection ---

# Patterns that indicate HTTP requests to external APIs
_HTTP_CALL_PATTERNS: list[re.Pattern[str]] = [
    # Python: requests library
    re.compile(r"""requests\.(get|post|put|delete|patch|head)\s*\(\s*[f"']([^"']+)"""),
    # Python: httpx
    re.compile(r"""httpx\.(get|post|put|delete|patch)\s*\(\s*[f"']([^"']+)"""),
    # Python: urllib
    re.compile(r"""urllib\.request\.urlopen\s*\(\s*[f"']([^"']+)"""),
    # Python: aiohttp
    re.compile(r"""session\.(get|post|put|delete|patch)\s*\(\s*[f"']([^"']+)"""),
    # JS/TS: fetch
    re.compile(r"""fetch\s*\(\s*[`"']([^`"']+)"""),
    # JS/TS: axios
    re.compile(r"""axios\.(get|post|put|delete|patch)\s*\(\s*[`"']([^`"']+)"""),
]

# Patterns for base URL variables
_BASE_URL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"""(?:base_?url|api_?url|endpoint|BASE_URL|API_URL)\s*=\s*[f"'`]([^"'`]+)""", re.IGNORECASE),
    re.compile(r"""(?:base_?url|api_?url|endpoint|BASE_URL|API_URL)\s*:\s*[f"'`]([^"'`]+)""", re.IGNORECASE),
]

# Known API services by URL pattern
_KNOWN_API_SERVICES: dict[str, dict[str, str]] = {
    "openweathermap.org": {
        "name": "OpenWeatherMap",
        "auth_method": "API key (query parameter)",
        "rate_limit_info": "Free tier: 60 calls/min, 1M calls/month",
    },
    "api.github.com": {
        "name": "GitHub API",
        "auth_method": "Bearer token or Personal Access Token",
        "rate_limit_info": "Authenticated: 5000 req/hour, Unauthenticated: 60 req/hour",
    },
    "api.stripe.com": {
        "name": "Stripe API",
        "auth_method": "Bearer token (Secret key)",
        "rate_limit_info": "100 read operations/sec, 100 write operations/sec",
    },
    "googleapis.com": {
        "name": "Google APIs",
        "auth_method": "API key or OAuth 2.0",
        "rate_limit_info": "Varies by service",
    },
    "api.openai.com": {
        "name": "OpenAI API",
        "auth_method": "Bearer token (API key)",
        "rate_limit_info": "Varies by model and tier",
    },
    "api.twilio.com": {
        "name": "Twilio API",
        "auth_method": "Basic auth (Account SID + Auth Token)",
        "rate_limit_info": "Varies by product",
    },
    "api.sendgrid.com": {
        "name": "SendGrid API",
        "auth_method": "Bearer token (API key)",
        "rate_limit_info": "Varies by plan",
    },
    "maps.googleapis.com": {
        "name": "Google Maps API",
        "auth_method": "API key",
        "rate_limit_info": "Varies by endpoint",
    },
    "graph.facebook.com": {
        "name": "Facebook Graph API",
        "auth_method": "OAuth 2.0 access token",
        "rate_limit_info": "200 calls/user/hour",
    },
    "api.spotify.com": {
        "name": "Spotify Web API",
        "auth_method": "OAuth 2.0 Bearer token",
        "rate_limit_info": "Rate limits apply per app",
    },
}


def _detect_external_apis(
    repo_path: Path,
    source_files: list[str],
    env_vars: list[EnvVar],
) -> list[ExternalAPI]:
    """Detect external APIs consumed by the codebase."""
    # Track: url_base -> {files, methods, env_var_candidates}
    api_signals: dict[str, dict[str, set[str]]] = {}

    for rel_path in source_files:
        full_path = repo_path / rel_path
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Scan for HTTP call patterns
        for pattern in _HTTP_CALL_PATTERNS:
            for match in pattern.finditer(content):
                groups = match.groups()
                # Extract URL - it could be in group 1 or 2 depending on pattern
                url = groups[-1] if len(groups) > 1 else groups[0]
                if not url:
                    continue

                # Extract domain/base from URL
                url_key = _extract_url_base(url)
                if not url_key:
                    continue

                if url_key not in api_signals:
                    api_signals[url_key] = {"files": set(), "methods": set()}
                api_signals[url_key]["files"].add(rel_path)
                if len(groups) > 1:
                    api_signals[url_key]["methods"].add(groups[0].upper())

        # Scan for base URL patterns
        for pattern in _BASE_URL_PATTERNS:
            for match in pattern.finditer(content):
                url = match.group(1)
                url_key = _extract_url_base(url)
                if url_key:
                    if url_key not in api_signals:
                        api_signals[url_key] = {"files": set(), "methods": set()}
                    api_signals[url_key]["files"].add(rel_path)

    # Build ExternalAPI objects
    external_apis: list[ExternalAPI] = []
    for url_base, signals in api_signals.items():
        # Look up known service info
        known_info: dict[str, str] = {}
        for domain_pattern, info in _KNOWN_API_SERVICES.items():
            if domain_pattern in url_base:
                known_info = info
                break

        # Try to find matching env var for auth
        auth_env = ""
        for ev in env_vars:
            if ev.expected_format == "API_KEY":
                # Heuristic: match env var name to API domain
                ev_lower = ev.name.lower()
                url_lower = url_base.lower()
                # Simple matching: if any part of the domain appears in the env var
                domain_parts = url_lower.replace(".", " ").replace("-", " ").split()
                if any(part in ev_lower for part in domain_parts if len(part) > 3):
                    auth_env = ev.name
                    break

        api = ExternalAPI(
            name=known_info.get("name", _infer_api_name(url_base)),
            base_url=url_base,
            auth_method=known_info.get("auth_method", ""),
            auth_env_var=auth_env,
            files_used_in=sorted(signals["files"]),
            http_methods=sorted(signals["methods"]) if signals["methods"] else [],
            rate_limit_info=known_info.get("rate_limit_info", ""),
        )
        external_apis.append(api)

    return external_apis


def _extract_url_base(url: str) -> str:
    """Extract a meaningful base URL from a URL string."""
    # Skip relative URLs, template variables, localhost
    if not url or url.startswith("/") or url.startswith("."):
        return ""
    if "localhost" in url or "127.0.0.1" in url or "0.0.0.0" in url:
        return ""
    if "{" in url and "}" in url and "http" not in url:
        return ""

    # Clean up f-string artifacts
    url = url.replace("{", "").replace("}", "")

    # Try to extract domain
    if "://" in url:
        parts = url.split("://", 1)
        if len(parts) > 1:
            domain_path = parts[1].split("/")[0]
            return f"{parts[0]}://{domain_path}"
    elif "." in url and " " not in url:
        # Might be just a domain
        domain = url.split("/")[0]
        if "." in domain:
            return f"https://{domain}"

    return ""


def _infer_api_name(url_base: str) -> str:
    """Infer an API name from its URL base."""
    # Remove protocol
    name = url_base.replace("https://", "").replace("http://", "")
    # Remove common prefixes
    name = name.replace("api.", "").replace("www.", "")
    # Take domain name
    name = name.split("/")[0].split(".")[0]
    return name.title() + " API" if name else "Unknown API"


# --- LLM call for tech profile ---

_TECH_PROFILE_SYSTEM_PROMPT = """\
You are a software analysis assistant. Given raw dependency data and config files from a \
repository, produce a structured technology profile.

Respond with valid JSON matching this exact schema:
{
  "primary_language": "string",
  "language_version": "string",
  "framework": "string",
  "framework_version": "string",
  "key_libraries": ["string"],
  "deployment_target": "string",
  "build_tool": "string",
  "test_framework": "string",
  "linter": "string or null",
  "formatter": "string or null"
}

- primary_language: The main programming language (e.g. "Python", "TypeScript")
- language_version: Version if detectable (e.g. "3.12", "ES2022")
- framework: Primary web/app framework (e.g. "FastAPI", "Next.js", "Django")
- framework_version: Version if detectable
- key_libraries: Up to 10 most important libraries (not dev tools)
- deployment_target: Best guess (e.g. "Docker", "Vercel", "AWS Lambda", "unknown")
- build_tool: e.g. "webpack", "vite", "setuptools", "uv", "npm"
- test_framework: e.g. "pytest", "jest", "vitest"
- linter/formatter: e.g. "ruff", "eslint", "prettier", null if not detected

Only respond with the JSON object, no other text."""


async def _synthesize_tech_profile(
    packages: list[Package],
    config_files: list[str],
) -> TechProfile:
    """Make one LLM call to synthesize a TechProfile from raw dependency data."""
    package_list = "\n".join(
        f"- {p.name} {p.version} ({p.category})" if p.category else f"- {p.name} {p.version}"
        for p in packages
    )

    user_prompt = f"""\
Analyze this repository's technology stack.

## Packages/Dependencies
{package_list or "(none detected)"}

## Config Files Found
{chr(10).join(f"- {c}" for c in config_files) or "(none detected)"}

Produce the technology profile JSON."""

    llm = LLMService()
    response = await llm.complete(
        system_prompt=_TECH_PROFILE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    content: str = response["content"]

    # Strip markdown code fences if the LLM wraps the JSON
    content = content.strip()
    if content.startswith("```"):
        # Remove first line (```json) and last line (```)
        lines = content.splitlines()
        content = "\n".join(lines[1:-1]).strip()

    try:
        data = json.loads(content)
        return TechProfile(**data)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("tech_profile_parse_failed", error=str(exc), raw=content[:200])
        return TechProfile()


# --- Main node function ---


def _collect_source_files(repo_path: Path) -> list[str]:
    """Collect all source files from the repo for import graph / env var analysis."""
    source_files: list[str] = []
    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in _SOURCE_EXTENSIONS:
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(repo_path).parts[:-1]):
            continue
        source_files.append(str(path.relative_to(repo_path)))
    return sorted(source_files)


async def dependency_analyzer(state: CodebaseState) -> dict[str, object]:
    """Analyze dependencies, build import graph, extract env vars.

    Reads from metadata (repo_url, local_path, config_files).
    Writes to dependencies (tech_stack, packages, import_graph, env_vars).
    """
    local_path = state.metadata.local_path
    if not local_path:
        msg = "metadata.local_path must be set (run structure_scanner first)"
        raise ValueError(msg)

    repo_path = Path(local_path)
    logger.info("dependency_analyzer_start", repo_path=local_path)

    # 1. Parse package manifests
    packages = _parse_packages(repo_path)
    logger.info("packages_parsed", count=len(packages))

    # 2. Collect all source files for graph and env var analysis
    all_source_files = _collect_source_files(repo_path)

    # 3. Build import graph
    import_graph = _build_import_graph(repo_path, all_source_files)
    logger.info("import_graph_built", nodes=len(import_graph))

    # 4. Extract env vars
    env_vars = _extract_all_env_vars(repo_path, all_source_files)
    logger.info("env_vars_extracted", count=len(env_vars))

    # 5. Detect external APIs consumed by the codebase
    external_apis = _detect_external_apis(repo_path, all_source_files, env_vars)
    logger.info("external_apis_detected", count=len(external_apis))

    # 6. LLM call: synthesize tech profile
    config_file_names = [c.path for c in state.metadata.config_files]
    tech_stack = await _synthesize_tech_profile(packages, config_file_names)
    logger.info(
        "tech_profile_synthesized",
        language=tech_stack.primary_language,
        framework=tech_stack.framework,
    )

    return {
        "dependencies": {
            "tech_stack": tech_stack,
            "packages": packages,
            "import_graph": import_graph,
            "env_vars": env_vars,
            "external_apis": external_apis,
        },
        "current_node": "dependency_analyzer",
    }
