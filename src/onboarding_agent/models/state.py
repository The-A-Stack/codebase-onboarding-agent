"""Central state schema for the LangGraph pipeline.

Every node reads from and writes to specific sections of CodebaseState.
State is append-only — nodes never overwrite previous sections.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, TypeVar

from pydantic import BaseModel, Field

from onboarding_agent.models.types import (
    Action,
    CodeQualitySignals,
    ConfigFile,
    Convention,
    Endpoint,
    EnvVar,
    ExternalAPI,
    FlowTrace,
    Graph,
    Hotspot,
    Issue,
    LicenseInfo,
    ModuleSummary,
    Package,
    TechProfile,
    TestingInfo,
    Tree,
)

# --- State sub-sections ---


class MetadataState(BaseModel):
    repo_url: str = ""
    commit_hash: str = ""
    local_path: str = ""  # filesystem path to cloned repo
    directory_tree: Tree = Field(default_factory=dict)
    entry_points: list[str] = Field(default_factory=list)
    config_files: list[ConfigFile] = Field(default_factory=list)
    license_info: LicenseInfo = Field(default_factory=LicenseInfo)
    testing_info: TestingInfo = Field(default_factory=TestingInfo)
    total_source_files: int = 0


class DependencyState(BaseModel):
    tech_stack: TechProfile | None = None
    packages: list[Package] = Field(default_factory=list)
    import_graph: Graph = Field(default_factory=dict)
    env_vars: list[EnvVar] = Field(default_factory=list)
    external_apis: list[ExternalAPI] = Field(default_factory=list)


class ModuleState(BaseModel):
    analyzed: list[ModuleSummary] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    module_connections: Graph = Field(default_factory=dict)
    api_endpoints: list[Endpoint] = Field(default_factory=list)
    feature_flows: list[FlowTrace] = Field(default_factory=list)


class PatternState(BaseModel):
    conventions: list[Convention] = Field(default_factory=list)
    inconsistencies: list[Issue] = Field(default_factory=list)
    dead_code: list[dict[str, str]] = Field(default_factory=list)
    complexity_hotspots: list[Hotspot] = Field(default_factory=list)
    code_quality: CodeQualitySignals = Field(default_factory=CodeQualitySignals)


class ScoreState(BaseModel):
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    overall_score: float = 0.0
    recommendations: list[Action] = Field(default_factory=list)
    agent_file_config: dict[str, object] = Field(default_factory=dict)


class OutputState(BaseModel):
    report_json: dict[str, object] = Field(default_factory=dict)
    report_markdown: str = ""
    agent_files: dict[str, str] = Field(default_factory=dict)
    readiness_report: dict[str, object] = Field(default_factory=dict)


# --- Top-level graph state ---


def _merge_list(existing: list[object], new: list[object]) -> list[object]:
    """Reducer for append-only list fields in LangGraph state."""
    return [*existing, *new]


_T = TypeVar("_T", bound=BaseModel)


def _is_all_default(instance: BaseModel) -> bool:
    """Check if all fields in a Pydantic model are at their default values."""
    # Compare against a fresh default instance
    default_instance = type(instance)()
    for field_name in instance.model_fields:
        if getattr(instance, field_name) != getattr(default_instance, field_name):
            return False
    return True


def _make_sub_state_reducer(model_cls: type[_T]) -> Callable[[_T | dict, _T | dict], _T]:
    """Create a reducer that merges Pydantic sub-state models.

    Strategy: if the new sub-state is entirely at default values, the node
    didn't write to this section — keep the existing value. Otherwise, the
    node explicitly wrote to it — take the new value wholesale.

    This handles cyclic nodes (deep_diver) that set pending=[] intentionally,
    while preventing nodes that don't touch a section from wiping it out.
    """

    def reducer(existing: _T | dict, new: _T | dict) -> _T:  # type: ignore[type-var]
        if isinstance(existing, dict):
            existing = model_cls(**existing)
        if isinstance(new, dict):
            new = model_cls(**new)

        # If new is entirely defaults, the node didn't touch this section
        if _is_all_default(new):
            return existing
        return new

    return reducer


def _merge_outputs(
    existing: OutputState | dict[str, object],
    new: OutputState | dict[str, object],
) -> OutputState:
    """Special reducer for OutputState: merge non-empty fields.

    Multiple generator nodes (doc_generator, agent_file_generator, readiness_report)
    each write to different fields of OutputState. Without field-level merging,
    the last writer would overwrite the others' outputs with defaults.
    """
    if isinstance(existing, dict):
        existing = OutputState(**existing)
    if isinstance(new, dict):
        new = OutputState(**new)

    return OutputState(
        report_json=new.report_json if new.report_json else existing.report_json,
        report_markdown=new.report_markdown if new.report_markdown else existing.report_markdown,
        agent_files=new.agent_files if new.agent_files else existing.agent_files,
        readiness_report=new.readiness_report if new.readiness_report else existing.readiness_report,
    )


_merge_metadata = _make_sub_state_reducer(MetadataState)
_merge_dependencies = _make_sub_state_reducer(DependencyState)
_merge_modules = _make_sub_state_reducer(ModuleState)
_merge_patterns = _make_sub_state_reducer(PatternState)
_merge_scores = _make_sub_state_reducer(ScoreState)


class CodebaseState(BaseModel):
    """Central state flowing through the entire LangGraph pipeline."""

    metadata: Annotated[MetadataState, _merge_metadata] = Field(default_factory=MetadataState)
    dependencies: Annotated[DependencyState, _merge_dependencies] = Field(
        default_factory=DependencyState
    )
    modules: Annotated[ModuleState, _merge_modules] = Field(default_factory=ModuleState)
    patterns: Annotated[PatternState, _merge_patterns] = Field(default_factory=PatternState)
    scores: Annotated[ScoreState, _merge_scores] = Field(default_factory=ScoreState)
    outputs: Annotated[OutputState, _merge_outputs] = Field(default_factory=OutputState)

    # Pipeline control
    analysis_depth: str = "standard"
    current_node: str = ""
    errors: Annotated[list[str], _merge_list] = Field(default_factory=list)
