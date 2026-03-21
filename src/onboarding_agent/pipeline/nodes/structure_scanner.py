"""Node 1: Structure Scanner — deterministic, no LLM.

Builds the initial structural skeleton: directory tree, entry points, config files.
Clones the repo via GitHubService, walks the file system, and populates MetadataState.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from onboarding_agent.config import get_settings
from onboarding_agent.config.settings import AnalysisDepth
from onboarding_agent.models.state import CodebaseState
from onboarding_agent.models.types import ConfigFile, LicenseInfo, TestingInfo, Tree
from onboarding_agent.services.github import GitHubService

logger = structlog.get_logger()

# --- Constants ---

_ENTRY_POINT_NAMES: set[str] = {
    # Python
    "main.py",
    "app.py",
    "server.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "__main__.py",
    # JS/TS
    "index.ts",
    "index.js",
    "index.tsx",
    "index.jsx",
    "main.ts",
    "main.js",
    "app.ts",
    "app.js",
    "server.ts",
    "server.js",
}

_ENTRY_POINT_DIRS: set[str] = {
    "routes",
    "api",
    "pages",
    "endpoints",
    "views",
    "controllers",
}

_CONFIG_FILE_MAP: dict[str, str] = {
    # Package manifests
    "package.json": "package_manifest",
    "pyproject.toml": "package_manifest",
    "setup.py": "package_manifest",
    "setup.cfg": "package_manifest",
    "requirements.txt": "package_manifest",
    "Pipfile": "package_manifest",
    "Cargo.toml": "package_manifest",
    "go.mod": "package_manifest",
    "pom.xml": "package_manifest",
    "build.gradle": "package_manifest",
    # CI/CD
    "Jenkinsfile": "ci_config",
    ".travis.yml": "ci_config",
    "azure-pipelines.yml": "ci_config",
    "bitbucket-pipelines.yml": "ci_config",
    # Docker
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
    ".dockerignore": "docker",
    # Env
    ".env": "env",
    ".env.example": "env",
    ".env.local": "env",
    ".env.development": "env",
    ".env.production": "env",
    # Config
    "tsconfig.json": "config",
    ".eslintrc.json": "config",
    ".eslintrc.js": "config",
    ".prettierrc": "config",
    "jest.config.js": "config",
    "jest.config.ts": "config",
    "vite.config.ts": "config",
    "webpack.config.js": "config",
    "next.config.js": "config",
    "next.config.mjs": "config",
    "tailwind.config.js": "config",
    "tailwind.config.ts": "config",
    "Makefile": "config",
    "tox.ini": "config",
    "mypy.ini": "config",
    "ruff.toml": "config",
    ".pre-commit-config.yaml": "config",
}

_CI_DIR_NAMES: dict[str, str] = {
    ".github": "ci_config",
    ".circleci": "ci_config",
    ".gitlab": "ci_config",
}

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
    "*.egg-info",
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


def _should_skip(dir_name: str) -> bool:
    """Check if a directory should be skipped during traversal."""
    return dir_name in _SKIP_DIRS or dir_name.endswith(".egg-info")


def _build_directory_tree(root: Path, max_depth: int = 50) -> Tree:
    """Build a nested dictionary representing the directory structure.

    Each directory maps to a dict of its children.
    Files are represented as leaf nodes with their size in bytes.
    """

    def _walk(current: Path, depth: int) -> Tree:
        tree: Tree = {}
        if depth > max_depth:
            return tree

        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return tree

        for entry in entries:
            if entry.is_dir():
                if _should_skip(entry.name):
                    continue
                tree[entry.name] = _walk(entry, depth + 1)
            elif entry.is_file():
                tree[entry.name] = entry.stat().st_size

        return tree

    return _walk(root, 0)


def _find_entry_points(root: Path) -> list[str]:
    """Identify likely entry point files in the repository."""
    entry_points: list[str] = []

    for path in root.rglob("*"):
        if path.is_dir() and _should_skip(path.name):
            continue
        if not path.is_file():
            continue

        rel = str(path.relative_to(root))

        # Skip files inside skipped directories
        if any(_should_skip(part) for part in path.relative_to(root).parts[:-1]):
            continue

        # Direct entry point names
        if path.name in _ENTRY_POINT_NAMES:
            entry_points.append(rel)
            continue

        # Files directly inside entry-point directories (e.g. routes/users.py)
        if len(path.relative_to(root).parts) >= 2:
            parent_dir = path.relative_to(root).parts[-2]
            if parent_dir in _ENTRY_POINT_DIRS and path.suffix in _SOURCE_EXTENSIONS:
                entry_points.append(rel)

    return sorted(set(entry_points))


def _find_config_files(root: Path) -> list[ConfigFile]:
    """Identify configuration files in the repository."""
    configs: list[ConfigFile] = []

    # Check top-level files against the config map
    for path in root.iterdir():
        if path.is_file() and path.name in _CONFIG_FILE_MAP:
            configs.append(
                ConfigFile(
                    path=path.name,
                    file_type=_CONFIG_FILE_MAP[path.name],
                    name=path.name,
                )
            )

    # Check CI directories (e.g. .github/workflows/*.yml)
    for dir_name, file_type in _CI_DIR_NAMES.items():
        ci_dir = root / dir_name
        if ci_dir.is_dir():
            for yml_path in ci_dir.rglob("*.yml"):
                rel = str(yml_path.relative_to(root))
                configs.append(ConfigFile(path=rel, file_type=file_type, name=yml_path.name))
            for yaml_path in ci_dir.rglob("*.yaml"):
                rel = str(yaml_path.relative_to(root))
                configs.append(ConfigFile(path=rel, file_type=file_type, name=yaml_path.name))

    return sorted(configs, key=lambda c: c.path)


def _collect_source_files(root: Path) -> list[str]:
    """Collect all source files, sorted by likely importance (entry points first)."""
    source_files: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in _SOURCE_EXTENSIONS:
            continue
        if any(_should_skip(part) for part in path.relative_to(root).parts[:-1]):
            continue
        source_files.append(str(path.relative_to(root)))

    # Prioritize: entry points and shorter paths first (top-level files are more important)
    entry_point_names = _ENTRY_POINT_NAMES
    entry_point_dirs = _ENTRY_POINT_DIRS

    def _priority(file_path: str) -> tuple[int, int, str]:
        parts = Path(file_path).parts
        name = Path(file_path).name
        depth = len(parts)

        if name in entry_point_names:
            return (0, depth, file_path)
        if len(parts) >= 2 and parts[-2] in entry_point_dirs:
            return (1, depth, file_path)
        return (2, depth, file_path)

    return sorted(source_files, key=_priority)


_LICENSE_FILE_NAMES: set[str] = {
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "LICENCE",
    "LICENCE.md",
    "LICENCE.txt",
    "COPYING",
    "COPYING.md",
}

_LICENSE_PATTERNS: dict[str, str] = {
    "MIT License": "MIT",
    "Apache License": "Apache-2.0",
    "GNU GENERAL PUBLIC LICENSE": "GPL-3.0",
    "GNU LESSER GENERAL PUBLIC LICENSE": "LGPL-3.0",
    "BSD 2-Clause": "BSD-2-Clause",
    "BSD 3-Clause": "BSD-3-Clause",
    "ISC License": "ISC",
    "Mozilla Public License": "MPL-2.0",
    "The Unlicense": "Unlicense",
}

_TEST_FILE_PATTERNS: set[str] = {
    "test_",
    "_test.",
    ".test.",
    ".spec.",
    "tests/",
    "__tests__/",
    "test/",
    "spec/",
}

_TEST_DIR_NAMES: set[str] = {
    "tests",
    "test",
    "__tests__",
    "spec",
    "specs",
}

_TEST_FRAMEWORKS: dict[str, str] = {
    "pytest": "pytest",
    "unittest": "unittest",
    "jest": "jest",
    "vitest": "vitest",
    "mocha": "mocha",
    "jasmine": "jasmine",
}

_COVERAGE_INDICATORS: set[str] = {
    ".coveragerc",
    "coverage",
    "codecov.yml",
    ".nycrc",
    "jest.config",
}


def _detect_license(root: Path) -> LicenseInfo:
    """Detect license file and type in the repository."""
    for name in _LICENSE_FILE_NAMES:
        license_path = root / name
        if license_path.is_file():
            try:
                content = license_path.read_text(encoding="utf-8", errors="replace")[:2000]
                license_type = "unknown"
                for pattern, spdx_id in _LICENSE_PATTERNS.items():
                    if pattern.lower() in content.lower():
                        license_type = spdx_id
                        break
                return LicenseInfo(
                    license_type=license_type,
                    license_file=name,
                    is_present=True,
                )
            except OSError:
                return LicenseInfo(license_file=name, is_present=True)
    return LicenseInfo()


def _detect_testing_info(root: Path, config_files: list[ConfigFile]) -> TestingInfo:
    """Detect test files, test framework, CI configuration, and coverage setup."""
    test_files: list[str] = []
    test_dirs: set[str] = set()
    ci_configs: list[str] = []
    has_coverage = False

    # Find test files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in _SOURCE_EXTENSIONS:
            continue
        if any(_should_skip(part) for part in path.relative_to(root).parts[:-1]):
            continue

        rel = str(path.relative_to(root))
        lower = rel.lower()

        # Check if it's a test file
        if any(p in lower for p in _TEST_FILE_PATTERNS):
            test_files.append(rel)

        # Check if it's in a test directory
        parts = path.relative_to(root).parts
        for part in parts[:-1]:
            if part.lower() in _TEST_DIR_NAMES:
                test_dirs.add(part)

    # Detect CI config files
    for cf in config_files:
        if cf.file_type == "ci_config":
            ci_configs.append(cf.path)

    # Check for .github/workflows if not already found
    gh_dir = root / ".github" / "workflows"
    if gh_dir.is_dir() and not ci_configs:
        for yml in gh_dir.iterdir():
            if yml.suffix in (".yml", ".yaml"):
                ci_configs.append(str(yml.relative_to(root)))

    # Detect test framework from config files
    test_framework = ""
    for cf in config_files:
        full_path = root / cf.path
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")[:5000]
            for fw_key, fw_name in _TEST_FRAMEWORKS.items():
                if fw_key in content.lower():
                    test_framework = fw_name
                    break
        except OSError:
            continue
        if test_framework:
            break

    # Check for coverage configuration
    for name in _COVERAGE_INDICATORS:
        if (root / name).exists():
            has_coverage = True
            break
    # Also check pyproject.toml for coverage config
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            if "coverage" in content.lower() or "cov" in content.lower():
                has_coverage = True
        except OSError:
            pass

    return TestingInfo(
        has_tests=len(test_files) > 0,
        test_framework=test_framework,
        test_file_count=len(test_files),
        test_files=sorted(test_files)[:20],  # Cap at 20 for state size
        test_directories=sorted(test_dirs),
        ci_config_files=ci_configs,
        has_ci=len(ci_configs) > 0,
        coverage_configured=has_coverage,
    )


def _detect_python_version(root: Path) -> str:
    """Detect Python version from various config files."""
    # Check .python-version
    pv_file = root / ".python-version"
    if pv_file.is_file():
        try:
            version = pv_file.read_text(encoding="utf-8").strip()
            if version:
                return version
        except OSError:
            pass

    # Check runtime.txt (Heroku-style)
    rt_file = root / "runtime.txt"
    if rt_file.is_file():
        try:
            content = rt_file.read_text(encoding="utf-8").strip()
            if "python-" in content.lower():
                return content.split("-", 1)[1].strip()
        except OSError:
            pass

    # Check pyproject.toml for requires-python
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            import re

            content = pyproject.read_text(encoding="utf-8", errors="replace")
            match = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
            # Also check python_requires in setup style
            match = re.search(r'python_requires\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
        except OSError:
            pass

    # Check setup.cfg
    setup_cfg = root / "setup.cfg"
    if setup_cfg.is_file():
        try:
            import re

            content = setup_cfg.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"python_requires\s*=\s*(.+)", content)
            if match:
                return match.group(1).strip()
        except OSError:
            pass

    return ""


async def structure_scanner(state: CodebaseState) -> dict[str, object]:
    """Scan repository structure and populate metadata.

    - Clones the repo (or reuses existing clone)
    - Builds full directory tree
    - Identifies entry points and config files
    - Populates modules.pending with prioritized source files
    """
    repo_url = state.metadata.repo_url
    if not repo_url:
        msg = "metadata.repo_url must be set before running structure_scanner"
        raise ValueError(msg)

    logger.info("structure_scanner_start", repo_url=repo_url)

    # Clone
    github = GitHubService()
    repo_path, commit_hash = github.clone_repo(repo_url)

    # Build tree
    directory_tree = _build_directory_tree(repo_path)

    # Find entry points and config files
    entry_points = _find_entry_points(repo_path)
    config_files = _find_config_files(repo_path)

    # Collect source files for downstream analysis, capped by depth
    settings = get_settings()
    depth_enum = AnalysisDepth(state.analysis_depth)
    max_files = min(depth_enum.max_files, settings.analysis_max_files)
    source_files = _collect_source_files(repo_path)[:max_files]

    # Detect license
    license_info = _detect_license(repo_path)

    # Detect testing info
    testing_info = _detect_testing_info(repo_path, config_files)

    # Detect Python version (if applicable)
    python_version = _detect_python_version(repo_path)

    # Count all source files (not just capped)
    all_source_files = _collect_source_files(repo_path)
    total_source_files = len(all_source_files)

    logger.info(
        "structure_scanner_complete",
        commit=commit_hash[:8],
        entry_points=len(entry_points),
        config_files=len(config_files),
        source_files=len(source_files),
        tree_keys=len(directory_tree),
        license=license_info.license_type,
        test_files=testing_info.test_file_count,
        has_ci=testing_info.has_ci,
        python_version=python_version,
    )

    return {
        "metadata": {
            "repo_url": repo_url,
            "commit_hash": commit_hash,
            "local_path": str(repo_path),
            "directory_tree": directory_tree,
            "entry_points": entry_points,
            "config_files": config_files,
            "license_info": license_info,
            "testing_info": testing_info,
            "total_source_files": total_source_files,
        },
        "modules": {
            "pending": source_files,
        },
        "current_node": "structure_scanner",
    }
