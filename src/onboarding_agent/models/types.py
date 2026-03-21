"""Pydantic models for all domain types used across the pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

# --- Type aliases for graph structures ---

Tree = dict[str, object]
Graph = dict[str, list[str]]


# --- Domain models ---


class ConfigFile(BaseModel):
    path: str
    file_type: str  # e.g. "package_manifest", "ci_config", "docker", "env"
    name: str


class Package(BaseModel):
    name: str
    version: str = ""
    category: str = ""  # e.g. "framework", "testing", "utility", "database"


class EnvVar(BaseModel):
    name: str
    files_used_in: list[str] = Field(default_factory=list)
    expected_format: str = ""  # e.g. "URL", "API_KEY", "boolean", "number"
    has_default: bool = False


class TechProfile(BaseModel):
    primary_language: str = ""
    language_version: str = ""
    framework: str = ""
    framework_version: str = ""
    key_libraries: list[str] = Field(default_factory=list)
    deployment_target: str = ""
    build_tool: str = ""
    test_framework: str = ""
    linter: str | None = None
    formatter: str | None = None


class Interface(BaseModel):
    name: str
    signature: str = ""
    description: str = ""


class ModuleSummary(BaseModel):
    file_path: str
    purpose: str
    public_interfaces: list[Interface] = Field(default_factory=list)
    internal_deps: list[str] = Field(default_factory=list)
    external_deps: list[str] = Field(default_factory=list)
    patterns_observed: list[str] = Field(default_factory=list)
    compressed_summary: str = ""


class Endpoint(BaseModel):
    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str
    handler_file: str = ""
    handler_function: str = ""
    middleware: list[str] = Field(default_factory=list)
    request_shape: dict[str, object] = Field(default_factory=dict)
    response_shape: dict[str, object] = Field(default_factory=dict)
    downstream_calls: list[str] = Field(default_factory=list)


class FlowTrace(BaseModel):
    name: str
    steps: list[FlowStep] = Field(default_factory=list)


class FlowStep(BaseModel):
    file: str
    function: str = ""
    action: str = ""
    external_calls: list[str] = Field(default_factory=list)


class Convention(BaseModel):
    name: str
    description: str = ""
    example_files: list[str] = Field(default_factory=list)
    pattern_type: str = ""  # error_handling, data_access, naming, file_org, testing, imports


class Issue(BaseModel):
    description: str
    files_involved: list[str] = Field(default_factory=list)
    severity: str = "medium"  # low, medium, high
    possible_explanation: str = ""


class Hotspot(BaseModel):
    file: str
    function: str = ""
    line_count: int = 0
    nesting_depth: int = 0
    description: str = ""


class Action(BaseModel):
    description: str
    impact: str = "medium"  # high, medium, low
    effort: str = "medium"  # high, medium, low
    affected_dimension: str = ""
    score_improvement_estimate: str = ""
    specific_files: list[str] = Field(default_factory=list)


class ExternalAPI(BaseModel):
    """An external API consumed by the codebase (not exposed by it)."""

    name: str  # e.g. "OpenWeatherMap", "Stripe", "GitHub API"
    base_url: str = ""  # e.g. "https://api.openweathermap.org"
    auth_method: str = ""  # e.g. "API key query param", "Bearer token", "Basic auth"
    auth_env_var: str = ""  # e.g. "OPENWEATHER_API_KEY"
    files_used_in: list[str] = Field(default_factory=list)
    http_methods: list[str] = Field(default_factory=list)  # GET, POST, etc.
    description: str = ""  # e.g. "Fetches current weather and 5-day forecast"
    rate_limit_info: str = ""  # e.g. "Free tier: 60 calls/min"


class LicenseInfo(BaseModel):
    """License information detected from the repository."""

    license_type: str = ""  # e.g. "MIT", "Apache-2.0", "GPL-3.0", "unknown", ""
    license_file: str = ""  # e.g. "LICENSE", "LICENSE.md"
    is_present: bool = False


class TestingInfo(BaseModel):
    """Testing infrastructure information."""

    has_tests: bool = False
    test_framework: str = ""  # e.g. "pytest", "jest", "unittest"
    test_file_count: int = 0
    test_files: list[str] = Field(default_factory=list)
    test_directories: list[str] = Field(default_factory=list)
    ci_config_files: list[str] = Field(default_factory=list)
    has_ci: bool = False
    coverage_configured: bool = False


class CodeQualitySignals(BaseModel):
    """Signals about code quality practices in the codebase."""

    total_lines_of_code: int = 0
    total_source_files: int = 0
    has_type_hints: bool = False
    type_hint_coverage: str = ""  # e.g. "high", "medium", "low", "none"
    has_docstrings: bool = False
    docstring_coverage: str = ""  # e.g. "high", "medium", "low", "none"
    has_linter: bool = False
    linter_name: str = ""
    has_formatter: bool = False
    formatter_name: str = ""
    has_pre_commit_hooks: bool = False
