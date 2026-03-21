import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { connectWebSocket, getJobStatus } from "../api/client";

interface Progress {
  node: string;
  status: string;
  message: string;
  detail?: string;
}

const NODE_LABELS: Record<string, string> = {
  structure_scanner: "Structure Scanner",
  dependency_analyzer: "Dependency Analyzer",
  module_deep_diver: "Module Deep Diver",
  pattern_detector: "Pattern Detector",
  ai_readiness_scorer: "AI-Readiness Scorer",
  output_router: "Output Router",
  doc_generator: "Documentation Generator",
  agent_file_generator: "Agent File Generator",
  readiness_report: "Readiness Report",
  final_assembler: "Final Assembler",
};

const ALL_NODES = Object.keys(NODE_LABELS);

export default function ProgressPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [progress, setProgress] = useState<Progress[]>([]);
  const [status, setStatus] = useState<string>("connecting");
  const [error, setError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const ws = connectWebSocket(
      jobId,
      (data) => {
        if (data.error) {
          setError(data.error);
          setStatus("failed");
          return;
        }
        if (data.node === "done") {
          setStatus("completed");
          // Poll for final result
          setTimeout(() => navigate(`/results/${jobId}`), 1500);
          return;
        }
        if (data.status === "failed") {
          setError(data.message || "Analysis failed");
          setStatus("failed");
          return;
        }
        setStatus("running");
        setProgress((prev) => [...prev, data as Progress]);
      },
      () => {
        // On close, check job status
        if (status !== "completed" && status !== "failed") {
          getJobStatus(jobId).then((job) => {
            if (job.status === "completed") {
              navigate(`/results/${jobId}`);
            } else if (job.status === "failed") {
              setError(job.error || "Analysis failed");
              setStatus("failed");
            }
          });
        }
      }
    );
    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [jobId]);

  const completedNodes = new Set(progress.map((p) => p.node));
  const currentNode = progress.length > 0 ? progress[progress.length - 1].node : "";
  const progressPercent = Math.round(
    (completedNodes.size / ALL_NODES.length) * 100
  );

  return (
    <div className="page progress-page">
      <div className="card">
        <h2>Analyzing Repository</h2>

        <div className="progress-bar-container">
          <div
            className="progress-bar-fill"
            style={{ width: `${progressPercent}%` }}
          />
          <span className="progress-text">{progressPercent}%</span>
        </div>

        {error && <div className="error-msg">{error}</div>}

        {status === "completed" && (
          <div className="success-msg">
            Analysis complete! Redirecting to results...
          </div>
        )}

        <div className="node-list">
          {ALL_NODES.map((node) => {
            const isCompleted = completedNodes.has(node);
            const isCurrent = node === currentNode && status === "running";
            let className = "node-item";
            if (isCompleted) className += " completed";
            else if (isCurrent) className += " current";

            const update = progress.find((p) => p.node === node);

            return (
              <div key={node} className={className}>
                <div className="node-icon">
                  {isCompleted ? "✓" : isCurrent ? "⟳" : "○"}
                </div>
                <div className="node-info">
                  <div className="node-name">{NODE_LABELS[node]}</div>
                  {update && (
                    <div className="node-message">{update.message}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
