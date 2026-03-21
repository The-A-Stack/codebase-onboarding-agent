import { useState } from "react";
import type {
  AnalysisResult,
  KnownIssue,
  FirstTask,
  SetupStep,
} from "../types";

interface Props {
  result: AnalysisResult;
}

const SECTIONS = [
  { id: "identity", label: "1. Identity Card" },
  { id: "quickstart", label: "2. Quick Start" },
  { id: "directory", label: "3. Directory Structure" },
  { id: "config", label: "4. Config & Secrets" },
  { id: "architecture", label: "5. Architecture" },
  { id: "flows", label: "6. Feature Flows" },
  { id: "external", label: "7. External Services" },
  { id: "testing", label: "8. Testing" },
  { id: "devworkflow", label: "9. Dev Workflow" },
  { id: "patterns", label: "10. Patterns" },
  { id: "issues", label: "11. Known Issues" },
  { id: "tasks", label: "12. First Tasks" },
];

export default function ReportTab({ result }: Props) {
  const [activeSection, setActiveSection] = useState("identity");
  const [searchQuery, setSearchQuery] = useState("");
  const report = result.outputs.report_json as Record<string, unknown>;

  const downloadMarkdown = () => {
    const blob = new Blob([result.outputs.report_markdown], {
      type: "text/markdown",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "onboarding_report.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "analysis_result.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="report-tab">
      <div className="report-toolbar">
        <input
          type="text"
          placeholder="Search report..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        <div className="export-btns">
          <button className="btn-secondary" onClick={downloadMarkdown}>
            Export Markdown
          </button>
          <button className="btn-secondary" onClick={downloadJSON}>
            Export JSON
          </button>
        </div>
      </div>

      <div className="report-layout">
        <nav className="section-nav">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              className={`section-btn ${activeSection === s.id ? "active" : ""}`}
              onClick={() => setActiveSection(s.id)}
            >
              {s.label}
            </button>
          ))}
        </nav>

        <div className="section-content">
          {activeSection === "identity" && (
            <IdentitySection result={result} report={report} search={searchQuery} />
          )}
          {activeSection === "quickstart" && (
            <QuickStartSection report={report} result={result} search={searchQuery} />
          )}
          {activeSection === "directory" && (
            <DirectorySection report={report} search={searchQuery} />
          )}
          {activeSection === "config" && (
            <ConfigSection result={result} search={searchQuery} />
          )}
          {activeSection === "architecture" && (
            <ArchitectureSection result={result} search={searchQuery} />
          )}
          {activeSection === "flows" && (
            <FlowsSection report={report} search={searchQuery} />
          )}
          {activeSection === "external" && (
            <ExternalServicesSection result={result} search={searchQuery} />
          )}
          {activeSection === "testing" && (
            <TestingSection result={result} search={searchQuery} />
          )}
          {activeSection === "devworkflow" && (
            <DevWorkflowSection result={result} search={searchQuery} />
          )}
          {activeSection === "patterns" && (
            <PatternsSection result={result} search={searchQuery} />
          )}
          {activeSection === "issues" && (
            <KnownIssuesSection report={report} search={searchQuery} />
          )}
          {activeSection === "tasks" && (
            <FirstTasksSection report={report} search={searchQuery} />
          )}
        </div>
      </div>
    </div>
  );
}

function matchesSearch(text: string, query: string): boolean {
  if (!query) return true;
  return text.toLowerCase().includes(query.toLowerCase());
}

function safeStr(val: string | null | undefined, fallback = ""): string {
  if (!val || val === "None" || val === "null") return fallback;
  return val;
}

// --- Section 1: Identity Card ---
function IdentitySection({
  result,
  report,
  search,
}: {
  result: AnalysisResult;
  report: Record<string, unknown>;
  search: string;
}) {
  const tech = result.dependencies.tech_stack;
  const s1 = report.section1_identity as Record<string, unknown> | undefined;
  const description = s1?.project_description as string | undefined;
  const license = result.metadata.license_info;

  return (
    <div>
      <h3>Project Identity Card</h3>
      {description && <p className="project-description">{description}</p>}

      {tech && (
        <table className="info-table">
          <tbody>
            {[
              ["Language", `${safeStr(tech.primary_language)} ${safeStr(tech.language_version)}`.trim()],
              ["Framework", `${safeStr(tech.framework, "—")} ${safeStr(tech.framework_version)}`.trim()],
              ["Build", safeStr(tech.build_tool, "—")],
              ["Test", safeStr(tech.test_framework, "—")],
              ["Linter", safeStr(tech.linter, "—")],
              ["Formatter", safeStr(tech.formatter, "—")],
              ["Deployment", safeStr(tech.deployment_target, "—")],
            ]
              .filter(([, val]) => val !== "—" || true) // show all rows
              .filter(([label, val]) => matchesSearch(`${label} ${val}`, search))
              .map(([label, val]) => (
                <tr key={label}>
                  <td className="label-cell">{label}</td>
                  <td>{val || "—"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      )}

      {license?.is_present && (
        <div className="info-badge">
          License: <strong>{license.license_type || "Unknown"}</strong> ({license.license_file})
        </div>
      )}
      {!license?.is_present && (
        <div className="info-badge warning">No license file detected</div>
      )}

      <div className="stats-row">
        <div className="stat">
          <span className="stat-value">{result.metadata.total_source_files}</span>
          <span className="stat-label">Source Files</span>
        </div>
        <div className="stat">
          <span className="stat-value">
            {result.patterns?.code_quality?.total_lines_of_code ?? "—"}
          </span>
          <span className="stat-label">Lines of Code</span>
        </div>
        <div className="stat">
          <span className="stat-value">{result.dependencies.packages.length}</span>
          <span className="stat-label">Dependencies</span>
        </div>
      </div>

      <h4>Entry Points</h4>
      <ul>
        {result.metadata.entry_points
          .filter((ep) => matchesSearch(ep, search))
          .map((ep) => (
            <li key={ep}>
              <code>{ep}</code>
            </li>
          ))}
      </ul>

      {tech?.key_libraries && tech.key_libraries.length > 0 && (
        <>
          <h4>Key Libraries</h4>
          <div className="tag-list">
            {tech.key_libraries.map((lib) => (
              <span key={lib} className="tag">{lib}</span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// --- Section 2: Quick Start ---
function QuickStartSection({
  report,
  result,
  search,
}: {
  report: Record<string, unknown>;
  result: AnalysisResult;
  search: string;
}) {
  const s2 = report.section2_quickstart as Record<string, unknown> | undefined;
  const setupSteps = (s2?.setup_steps || []) as SetupStep[];
  const runCommand = s2?.run_command as string | undefined;
  const requiredEnvVars = (s2?.required_env_vars || []) as {
    name: string;
    format: string;
  }[];
  const packagesCount = (s2?.packages_count as number) ?? result.dependencies.packages.length;

  return (
    <div>
      <h3>Quick Start</h3>
      <p className="section-subtitle">Get from clone to running in minutes.</p>

      {requiredEnvVars.length > 0 && (
        <div className="callout warning">
          <strong>Required before running:</strong> You need to set{" "}
          {requiredEnvVars.map((ev) => (
            <code key={ev.name}>{ev.name}</code>
          )).reduce((prev, curr, i) => (
            <>{prev}{i > 0 ? ", " : ""}{curr}</>
          ))}
        </div>
      )}

      {setupSteps.length > 0 ? (
        <ol className="setup-steps">
          {setupSteps
            .filter((s) => matchesSearch(`${s.command} ${s.explanation}`, search))
            .map((step) => (
              <li key={step.step} className="setup-step">
                <div className="step-explanation">{step.explanation}</div>
                {step.command && (
                  <pre className="step-command">
                    <code>{step.command}</code>
                  </pre>
                )}
              </li>
            ))}
        </ol>
      ) : (
        <p>Setup steps could not be determined automatically.</p>
      )}

      {runCommand && (
        <div className="run-command-box">
          <h4>Run Command</h4>
          <pre className="step-command">
            <code>{runCommand}</code>
          </pre>
        </div>
      )}

      <p className="package-count">{packagesCount} dependencies to install.</p>
    </div>
  );
}

// --- Section 3: Directory Structure ---
function DirectorySection({
  report,
  search,
}: {
  report: Record<string, unknown>;
  search: string;
}) {
  const s3 = report.section3_directory as Record<string, unknown> | undefined;
  const tree = (s3?.directory_tree || {}) as Record<string, unknown>;

  return (
    <div>
      <h3>Directory Structure</h3>
      <pre className="directory-tree">
        <code>{renderTree(tree, "", search)}</code>
      </pre>
    </div>
  );
}

function renderTree(
  tree: Record<string, unknown>,
  prefix = "",
  search = "",
  depth = 0
): string {
  const entries = Object.entries(tree);
  const lines: string[] = [];

  entries.forEach(([name, value], i) => {
    const isLast = i === entries.length - 1;
    const connector = isLast ? "└── " : "├── ";
    const extension = isLast ? "    " : "│   ";

    if (search && !matchesSearch(name, search)) return;

    if (typeof value === "object" && value !== null) {
      if (name === "..." && (value as Record<string, unknown>).truncated) {
        lines.push(`${prefix}${connector}...`);
      } else {
        lines.push(`${prefix}${connector}${name}/`);
        if (depth < 5) {
          const subtree = renderTree(
            value as Record<string, unknown>,
            prefix + extension,
            "",
            depth + 1
          );
          if (subtree) lines.push(subtree);
        }
      }
    } else {
      lines.push(`${prefix}${connector}${name}`);
    }
  });

  return lines.join("\n");
}

// --- Section 4: Configuration & Secrets ---
function ConfigSection({
  result,
  search,
}: {
  result: AnalysisResult;
  search: string;
}) {
  const envVars = result.dependencies.env_vars;
  const apiKeys = envVars.filter((ev) => ev.expected_format === "API_KEY");
  const urls = envVars.filter((ev) => ev.expected_format === "URL");
  const others = envVars.filter(
    (ev) => ev.expected_format !== "API_KEY" && ev.expected_format !== "URL"
  );

  return (
    <div>
      <h3>Configuration & Secrets</h3>

      {apiKeys.length > 0 && (
        <>
          <h4>API Keys & Secrets</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Variable</th>
                <th>Required</th>
                <th>Used In</th>
              </tr>
            </thead>
            <tbody>
              {apiKeys
                .filter((ev) => matchesSearch(ev.name, search))
                .map((ev) => (
                  <tr key={ev.name}>
                    <td><code>{ev.name}</code></td>
                    <td>{ev.has_default ? "No" : "Yes"}</td>
                    <td>{ev.files_used_in.slice(0, 3).join(", ")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}

      {urls.length > 0 && (
        <>
          <h4>URLs & Endpoints</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Variable</th>
                <th>Required</th>
                <th>Used In</th>
              </tr>
            </thead>
            <tbody>
              {urls
                .filter((ev) => matchesSearch(ev.name, search))
                .map((ev) => (
                  <tr key={ev.name}>
                    <td><code>{ev.name}</code></td>
                    <td>{ev.has_default ? "No" : "Yes"}</td>
                    <td>{ev.files_used_in.slice(0, 3).join(", ")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}

      {others.length > 0 && (
        <>
          <h4>Other Configuration</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Variable</th>
                <th>Format</th>
                <th>Required</th>
                <th>Used In</th>
              </tr>
            </thead>
            <tbody>
              {others
                .filter((ev) => matchesSearch(ev.name, search))
                .map((ev) => (
                  <tr key={ev.name}>
                    <td><code>{ev.name}</code></td>
                    <td>{ev.expected_format || "string"}</td>
                    <td>{ev.has_default ? "No" : "Yes"}</td>
                    <td>{ev.files_used_in.slice(0, 3).join(", ")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}

      {envVars.length === 0 && <p>No environment variables detected.</p>}

      <h4>Config Files</h4>
      <ul>
        {result.metadata.config_files
          .filter((cf) => matchesSearch(`${cf.name} ${cf.file_type}`, search))
          .map((cf) => (
            <li key={cf.name}>
              <code>{cf.name}</code> — <span className="tag-sm">{cf.file_type}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}

// --- Section 5: Architecture Overview ---
function ArchitectureSection({
  result,
  search,
}: {
  result: AnalysisResult;
  search: string;
}) {
  const graphEntries = Object.entries(result.dependencies.import_graph)
    .filter(([file]) => matchesSearch(file, search))
    .slice(0, 50);

  return (
    <div>
      <h3>Architecture Overview</h3>
      <p>
        {Object.keys(result.dependencies.import_graph).length} modules with
        import relationships.
      </p>

      <h4>Analyzed Modules</h4>
      <div className="module-list">
        {result.modules.analyzed
          .filter((m) => matchesSearch(`${m.file_path} ${m.purpose}`, search))
          .map((m) => (
            <div key={m.file_path} className="module-card">
              <div className="module-path">
                <code>{m.file_path}</code>
              </div>
              <div className="module-purpose">{m.purpose}</div>
              {m.public_interfaces.length > 0 && (
                <div className="module-interfaces">
                  {m.public_interfaces.slice(0, 5).map((iface) => (
                    <span key={iface.name} className="interface-badge">
                      {iface.kind}: {iface.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
      </div>

      <h4>Import Graph</h4>
      <div className="graph-list">
        {graphEntries.map(([file, imports]) => (
          <div key={file} className="graph-entry">
            <code>{file}</code>
            <span className="arrow">&rarr;</span>
            <span>{(imports as string[]).join(", ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Section 6: Feature Flows ---
function FlowsSection({
  report,
  search,
}: {
  report: Record<string, unknown>;
  search: string;
}) {
  const section6 = report.section6_flows as Record<string, unknown> | undefined;
  const flows = (section6?.flows || []) as Array<{
    name: string;
    steps: Array<{
      step_number?: number;
      file: string;
      action: string;
      function?: string;
      external_calls?: string[];
    }>;
  }>;

  return (
    <div>
      <h3>Feature Flows</h3>
      {flows.length > 0 ? (
        flows
          .filter((f) => matchesSearch(f.name, search))
          .map((flow, i) => (
            <div key={i} className="flow-card">
              <h4>{flow.name}</h4>
              <ol>
                {flow.steps?.map((step, j) => (
                  <li key={j} value={step.step_number ?? j + 1}>
                    <code>{step.file}</code>
                    {step.function && (
                      <span className="fn-name">.{step.function}()</span>
                    )}
                    <span className="step-action"> &mdash; {step.action}</span>
                    {step.external_calls && step.external_calls.length > 0 && (
                      <div className="external-calls">
                        External: {step.external_calls.join(", ")}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          ))
      ) : (
        <p>No feature flows traced.</p>
      )}
    </div>
  );
}

// --- Section 7: External Services & APIs ---
function ExternalServicesSection({
  result,
  search,
}: {
  result: AnalysisResult;
  search: string;
}) {
  const endpoints = result.modules.api_endpoints;
  const externalApis = result.dependencies.external_apis ?? [];

  return (
    <div>
      <h3>External Services & APIs</h3>

      {externalApis.length > 0 && (
        <>
          <h4>Consumed External APIs</h4>
          <div className="api-list">
            {externalApis
              .filter((api) => matchesSearch(`${api.name} ${api.base_url}`, search))
              .map((api) => (
                <div key={api.base_url} className="api-card">
                  <div className="api-name">
                    <strong>{api.name}</strong>
                    <code className="api-url">{api.base_url}</code>
                  </div>
                  <div className="api-details">
                    {api.auth_method && (
                      <div>Auth: {api.auth_method}</div>
                    )}
                    {api.auth_env_var && (
                      <div>Env var: <code>{api.auth_env_var}</code></div>
                    )}
                    {api.rate_limit_info && (
                      <div>Rate limit: {api.rate_limit_info}</div>
                    )}
                    {api.files_used_in.length > 0 && (
                      <div>Used in: {api.files_used_in.join(", ")}</div>
                    )}
                  </div>
                </div>
              ))}
          </div>
        </>
      )}

      {endpoints.length > 0 && (
        <>
          <h4>Exposed API Endpoints</h4>
          <table className="data-table sortable">
            <thead>
              <tr>
                <th>Method</th>
                <th>Path</th>
                <th>Handler</th>
              </tr>
            </thead>
            <tbody>
              {endpoints
                .filter((ep) =>
                  matchesSearch(`${ep.method} ${ep.path} ${ep.handler_file}`, search)
                )
                .map((ep, i) => (
                  <tr key={i}>
                    <td>
                      <span className={`method-badge method-${ep.method.toLowerCase()}`}>
                        {ep.method}
                      </span>
                    </td>
                    <td><code>{ep.path}</code></td>
                    <td>
                      <code>{ep.handler_file}:{ep.handler_function}</code>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}

      {externalApis.length === 0 && endpoints.length === 0 && (
        <p>No external APIs consumed or API endpoints exposed.</p>
      )}
    </div>
  );
}

// --- Section 8: Testing ---
function TestingSection({
  result,
  search,
}: {
  result: AnalysisResult;
  search: string;
}) {
  const testing = result.metadata.testing_info;

  return (
    <div>
      <h3>Testing</h3>

      {testing?.has_tests ? (
        <>
          <table className="info-table">
            <tbody>
              <tr>
                <td className="label-cell">Framework</td>
                <td>{testing.test_framework || "Unknown"}</td>
              </tr>
              <tr>
                <td className="label-cell">Test Files</td>
                <td>{testing.test_file_count}</td>
              </tr>
              {testing.test_directories.length > 0 && (
                <tr>
                  <td className="label-cell">Test Directories</td>
                  <td>{testing.test_directories.join(", ")}</td>
                </tr>
              )}
              <tr>
                <td className="label-cell">Coverage</td>
                <td>{testing.coverage_configured ? "Configured" : "Not configured"}</td>
              </tr>
            </tbody>
          </table>

          {testing.test_files.length > 0 && (
            <>
              <h4>Test Files</h4>
              <ul>
                {testing.test_files
                  .filter((f) => matchesSearch(f, search))
                  .map((f) => (
                    <li key={f}><code>{f}</code></li>
                  ))}
              </ul>
            </>
          )}
        </>
      ) : (
        <div className="callout info">
          <strong>No test suite found.</strong> Consider adding tests with{" "}
          {testing?.test_framework || "pytest/jest"}.
        </div>
      )}

      <h4>CI/CD</h4>
      {testing?.has_ci ? (
        <ul>
          {testing.ci_config_files
            .filter((f) => matchesSearch(f, search))
            .map((f) => (
              <li key={f}><code>{f}</code></li>
            ))}
        </ul>
      ) : (
        <p>No CI/CD configuration detected.</p>
      )}
    </div>
  );
}

// --- Section 9: Development Workflow ---
function DevWorkflowSection({
  result,
  search,
}: {
  result: AnalysisResult;
  search: string;
}) {
  const tech = result.dependencies.tech_stack;
  const quality = result.patterns?.code_quality;

  return (
    <div>
      <h3>Development Workflow</h3>

      <table className="info-table">
        <tbody>
          <tr>
            <td className="label-cell">Build Tool</td>
            <td>{safeStr(tech?.build_tool, "Not detected")}</td>
          </tr>
          <tr>
            <td className="label-cell">Linter</td>
            <td>{safeStr(tech?.linter, "Not configured")}</td>
          </tr>
          <tr>
            <td className="label-cell">Formatter</td>
            <td>{safeStr(tech?.formatter, "Not configured")}</td>
          </tr>
          <tr>
            <td className="label-cell">Pre-commit Hooks</td>
            <td>{quality?.has_pre_commit_hooks ? "Configured" : "Not configured"}</td>
          </tr>
        </tbody>
      </table>

      {quality && (
        <>
          <h4>Code Quality Signals</h4>
          <div className="quality-grid">
            <div className={`quality-card ${quality.type_hint_coverage}`}>
              <div className="quality-label">Type Hints</div>
              <div className="quality-value">{quality.type_hint_coverage}</div>
            </div>
            <div className={`quality-card ${quality.docstring_coverage}`}>
              <div className="quality-label">Docstrings</div>
              <div className="quality-value">{quality.docstring_coverage}</div>
            </div>
            <div className="quality-card">
              <div className="quality-label">Lines of Code</div>
              <div className="quality-value">
                {quality.total_lines_of_code.toLocaleString()}
              </div>
            </div>
            <div className="quality-card">
              <div className="quality-label">Source Files</div>
              <div className="quality-value">{quality.total_source_files}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// --- Section 10: Patterns & Conventions ---
function PatternsSection({
  result,
  search,
}: {
  result: AnalysisResult;
  search: string;
}) {
  const conventions = result.patterns?.conventions ?? [];
  const inconsistencies = result.patterns?.inconsistencies ?? [];
  const hotspots = result.patterns?.complexity_hotspots ?? [];
  const deadCode = result.patterns?.dead_code ?? [];

  return (
    <div>
      <h3>Patterns & Conventions</h3>

      {conventions.length > 0 ? (
        <>
          <h4>Conventions</h4>
          {conventions
            .filter((c) => matchesSearch(`${c.name} ${c.description}`, search))
            .map((c, i) => (
              <div key={i} className="convention-card">
                <strong>{c.name}</strong>
                <span className="tag-sm">{c.pattern_type}</span>
                <p>{c.description}</p>
                {c.example_files?.length > 0 && (
                  <div className="examples">
                    {c.example_files.slice(0, 3).map((ex, j) => (
                      <code key={j}>{ex}</code>
                    ))}
                  </div>
                )}
              </div>
            ))}
        </>
      ) : (
        <p>No conventions detected.</p>
      )}

      {inconsistencies.length > 0 && (
        <>
          <h4>Inconsistencies</h4>
          {inconsistencies
            .filter((i) => matchesSearch(i.description, search))
            .map((issue, i) => (
              <div key={i} className="issue-card">
                <span className={`severity-badge severity-${issue.severity}`}>
                  {issue.severity}
                </span>
                <p>{issue.description}</p>
                {issue.possible_explanation && (
                  <p className="explanation">Explanation: {issue.possible_explanation}</p>
                )}
                {issue.files_involved.length > 0 && (
                  <div className="files-list">
                    Files: {issue.files_involved.join(", ")}
                  </div>
                )}
              </div>
            ))}
        </>
      )}

      {deadCode.length > 0 && (
        <>
          <h4>Potential Dead Code</h4>
          <ul>
            {deadCode.map((dc, i) => (
              <li key={i}>
                <code>{(dc as Record<string, string>).file}</code>
                {" — "}
                {(dc as Record<string, string>).reason_flagged}
              </li>
            ))}
          </ul>
        </>
      )}

      {hotspots.length > 0 && (
        <>
          <h4>Complexity Hotspots</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Lines</th>
                <th>Max Nesting</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {hotspots
                .filter((h) => matchesSearch(h.file, search))
                .map((h, i) => (
                  <tr key={i}>
                    <td><code>{h.file}</code></td>
                    <td>{h.line_count || "—"}</td>
                    <td>{h.nesting_depth || "—"}</td>
                    <td>{h.description}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

// --- Section 11: Known Issues & Gotchas ---
function KnownIssuesSection({
  report,
  search,
}: {
  report: Record<string, unknown>;
  search: string;
}) {
  const s11 = report.section11_known_issues as Record<string, unknown> | undefined;
  const issues = (s11?.issues || []) as KnownIssue[];

  return (
    <div>
      <h3>Known Issues & Gotchas</h3>
      {issues.length > 0 ? (
        <div className="issues-list">
          {issues
            .filter((i) => matchesSearch(`${i.issue} ${i.workaround}`, search))
            .map((issue, i) => (
              <div key={i} className="gotcha-card">
                <div className="gotcha-header">
                  {issue.category && (
                    <span className={`category-badge category-${issue.category}`}>
                      {issue.category}
                    </span>
                  )}
                  <strong>{issue.issue}</strong>
                </div>
                {issue.workaround && (
                  <div className="gotcha-workaround">
                    <em>Workaround:</em> {issue.workaround}
                  </div>
                )}
              </div>
            ))}
        </div>
      ) : (
        <p>No known issues identified.</p>
      )}
    </div>
  );
}

// --- Section 12: Suggested First Tasks ---
function FirstTasksSection({
  report,
  search,
}: {
  report: Record<string, unknown>;
  search: string;
}) {
  const s12 = report.section12_first_tasks as Record<string, unknown> | undefined;
  const tasks = (s12?.tasks || []) as FirstTask[];

  return (
    <div>
      <h3>Suggested First Tasks</h3>
      <p className="section-subtitle">
        Actionable tasks to get started, ordered by difficulty.
      </p>
      {tasks.length > 0 ? (
        <ol className="task-list">
          {tasks
            .filter((t) => matchesSearch(`${t.task} ${t.why}`, search))
            .map((task, i) => (
              <li key={i} className="task-item">
                <div className="task-header">
                  <span className="task-title">{task.task}</span>
                  {task.difficulty && (
                    <span className={`difficulty-badge difficulty-${task.difficulty}`}>
                      {task.difficulty}
                    </span>
                  )}
                </div>
                {task.why && <p className="task-why">{task.why}</p>}
                {task.files_involved?.length > 0 && (
                  <div className="task-files">
                    Files: {task.files_involved.map((f) => (
                      <code key={f}>{f}</code>
                    ))}
                  </div>
                )}
              </li>
            ))}
        </ol>
      ) : (
        <p>No tasks generated.</p>
      )}
    </div>
  );
}
