export interface AnalyzeRequest {
  repo_url: string;
  depth: "quick" | "standard" | "deep";
  agent_files: string[];
}

export interface AnalyzeResponse {
  job_id: string;
  status: string;
}

export interface ProgressUpdate {
  node: string;
  status: string;
  message: string;
  detail?: string;
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  current_node: string;
  progress: ProgressUpdate[];
  result: AnalysisResult | null;
  error: string | null;
}

export interface TechStack {
  primary_language: string;
  language_version: string;
  framework: string;
  framework_version: string;
  build_tool: string;
  test_framework: string;
  linter: string | null;
  formatter: string | null;
  key_libraries: string[];
  deployment_target: string;
}

export interface EnvVar {
  name: string;
  files_used_in: string[];
  expected_format: string;
  has_default: boolean;
}

export interface ExternalAPI {
  name: string;
  base_url: string;
  auth_method: string;
  auth_env_var: string;
  files_used_in: string[];
  http_methods: string[];
  description: string;
  rate_limit_info: string;
}

export interface LicenseInfo {
  license_type: string;
  license_file: string;
  is_present: boolean;
}

export interface TestingInfo {
  has_tests: boolean;
  test_framework: string;
  test_file_count: number;
  test_files: string[];
  test_directories: string[];
  ci_config_files: string[];
  has_ci: boolean;
  coverage_configured: boolean;
}

export interface CodeQualitySignals {
  total_lines_of_code: number;
  total_source_files: number;
  has_type_hints: boolean;
  type_hint_coverage: string;
  has_docstrings: boolean;
  docstring_coverage: string;
  has_linter: boolean;
  linter_name: string;
  has_formatter: boolean;
  formatter_name: string;
  has_pre_commit_hooks: boolean;
}

export interface ModuleSummary {
  file_path: string;
  purpose: string;
  public_interfaces: { name: string; kind: string; signature: string }[];
  internal_dependencies: string[];
  external_dependencies: string[];
  patterns_detected: string[];
  compressed_summary: string;
}

export interface Endpoint {
  method: string;
  path: string;
  handler_file: string;
  handler_function: string;
  middleware: string[];
  auth_required: boolean;
}

export interface Convention {
  name: string;
  description: string;
  example_files: string[];
  pattern_type: string;
}

export interface Issue {
  description: string;
  files_involved: string[];
  severity: string;
  possible_explanation: string;
}

export interface Hotspot {
  file: string;
  function: string;
  line_count: number;
  nesting_depth: number;
  description: string;
}

export interface KnownIssue {
  issue: string;
  category: string;
  workaround: string;
}

export interface FirstTask {
  task: string;
  difficulty: string;
  files_involved: string[];
  why: string;
}

export interface SetupStep {
  step: number;
  command: string;
  explanation: string;
}

export interface Recommendation {
  description: string;
  impact: string;
  effort: string;
  affected_dimension: string;
  score_improvement_estimate: number;
  specific_files: string[];
}

export interface AnalysisResult {
  metadata: {
    repo_url: string;
    commit_hash: string;
    entry_points: string[];
    config_files: { name: string; file_type: string; path: string }[];
    directory_tree: Record<string, unknown>;
    license_info: LicenseInfo;
    testing_info: TestingInfo;
    total_source_files: number;
  };
  dependencies: {
    packages: { name: string; version: string; category: string }[];
    import_graph: Record<string, string[]>;
    env_vars: EnvVar[];
    tech_stack: TechStack | null;
    external_apis: ExternalAPI[];
  };
  modules: {
    analyzed: ModuleSummary[];
    pending: string[];
    api_endpoints: Endpoint[];
    module_connections: Record<string, string[]>;
  };
  patterns: {
    conventions: Convention[];
    inconsistencies: Issue[];
    dead_code: Record<string, unknown>[];
    complexity_hotspots: Hotspot[];
    code_quality: CodeQualitySignals;
  };
  scores: {
    overall_score: number;
    dimension_scores: Record<string, number>;
    recommendations: Recommendation[];
  };
  outputs: {
    report_json: Record<string, unknown>;
    report_markdown: string;
    agent_files: Record<string, string>;
    readiness_report: {
      overall_score: number;
      verdict: string;
      narrative: string;
      top_strength: string;
      top_weakness: string;
      radar_chart: { dimension: string; score: number; max: number }[];
      dimension_scores: Record<string, number>;
      action_plan: {
        description: string;
        impact: string;
        effort: string;
        dimension: string;
        improvement: number;
        files: string[];
      }[];
    };
  };
}

export interface QARequest {
  job_id: string;
  question: string;
}

export interface QAResponse {
  answer: string;
  error: string | null;
}
