import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { submitAnalysis } from "../api/client";

const AGENT_OPTIONS = [
  { id: "claude", label: "Claude (CLAUDE.md)" },
  { id: "copilot", label: "GitHub Copilot" },
  { id: "cline", label: "Cline (.clinerules)" },
  { id: "aider", label: "Aider (.aider.conf.yml)" },
];

const DEPTH_OPTIONS = [
  { value: "quick", label: "Quick", desc: "15 files — fast overview" },
  { value: "standard", label: "Standard", desc: "30 files — balanced" },
  { value: "deep", label: "Deep", desc: "75 files — thorough" },
];

export default function SubmitPage() {
  const navigate = useNavigate();
  const [repoUrl, setRepoUrl] = useState("");
  const [depth, setDepth] = useState<"quick" | "standard" | "deep">("standard");
  const [agentFiles, setAgentFiles] = useState<string[]>([
    "claude",
    "copilot",
    "cline",
    "aider",
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggleAgent = (id: string) => {
    setAgentFiles((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim()) {
      setError("Please enter a GitHub repository URL");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await submitAnalysis({
        repo_url: repoUrl.trim(),
        depth,
        agent_files: agentFiles,
      });
      navigate(`/progress/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page submit-page">
      <div className="card submit-card">
        <h1>Codebase Onboarding Agent</h1>
        <p className="subtitle">
          Analyze any GitHub repository and generate onboarding documentation,
          AI context files, and readiness scores.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="repo-url">GitHub Repository URL</label>
            <input
              id="repo-url"
              type="url"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>Analysis Depth</label>
            <div className="depth-options">
              {DEPTH_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`depth-btn ${depth === opt.value ? "active" : ""}`}
                  onClick={() =>
                    setDepth(opt.value as "quick" | "standard" | "deep")
                  }
                  disabled={loading}
                >
                  <strong>{opt.label}</strong>
                  <span>{opt.desc}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label>Agent Files to Generate</label>
            <div className="agent-options">
              {AGENT_OPTIONS.map((opt) => (
                <label key={opt.id} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={agentFiles.includes(opt.id)}
                    onChange={() => toggleAgent(opt.id)}
                    disabled={loading}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          {error && <div className="error-msg">{error}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Starting Analysis..." : "Analyze Repository"}
          </button>
        </form>
      </div>
    </div>
  );
}
