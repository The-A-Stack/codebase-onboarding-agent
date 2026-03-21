import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getJobStatus } from "../api/client";
import type { AnalysisResult } from "../types";
import ReportTab from "../components/ReportTab";
import AgentFilesTab from "../components/AgentFilesTab";
import DashboardTab from "../components/DashboardTab";
import QATab from "../components/QATab";

const TABS = [
  { id: "report", label: "Onboarding Report" },
  { id: "agents", label: "Agent Files" },
  { id: "dashboard", label: "AI-Readiness" },
  { id: "qa", label: "Q&A Chat" },
];

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [activeTab, setActiveTab] = useState("report");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const job = await getJobStatus(jobId);
        if (job.status === "completed" && job.result) {
          setResult(job.result);
          setLoading(false);
        } else if (job.status === "failed") {
          setError(job.error || "Analysis failed");
          setLoading(false);
        } else {
          // Still running, redirect to progress
          navigate(`/progress/${jobId}`);
        }
      } catch {
        setError("Failed to fetch results");
        setLoading(false);
      }
    };

    poll();
  }, [jobId]);

  if (loading)
    return (
      <div className="page">
        <div className="card">Loading results...</div>
      </div>
    );
  if (error)
    return (
      <div className="page">
        <div className="card error-msg">{error}</div>
      </div>
    );
  if (!result)
    return (
      <div className="page">
        <div className="card">No results found</div>
      </div>
    );

  return (
    <div className="page results-page">
      <div className="results-header">
        <h2>{result.metadata.repo_url}</h2>
        <span className="commit-badge">
          {result.metadata.commit_hash?.slice(0, 8)}
        </span>
        <button
          className="btn-secondary"
          onClick={() => navigate("/")}
        >
          New Analysis
        </button>
      </div>

      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === "report" && <ReportTab result={result} />}
        {activeTab === "agents" && <AgentFilesTab result={result} />}
        {activeTab === "dashboard" && <DashboardTab result={result} />}
        {activeTab === "qa" && jobId && <QATab jobId={jobId} />}
      </div>
    </div>
  );
}
