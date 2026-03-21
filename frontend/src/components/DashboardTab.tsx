import { useState } from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { AnalysisResult } from "../types";

interface Props {
  result: AnalysisResult;
}

export default function DashboardTab({ result }: Props) {
  const readiness = result.outputs.readiness_report;
  const scores = result.scores;
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  if (!readiness || !scores) {
    return <p>No readiness data available.</p>;
  }

  const radarData = readiness.radar_chart ||
    Object.entries(scores.dimension_scores).map(([dim, score]) => ({
      dimension: dim.replace(/_/g, " "),
      score,
      max: 10,
    }));

  const overallScore = readiness.overall_score || scores.overall_score;
  const scoreColor =
    overallScore >= 7 ? "#4caf50" : overallScore >= 4 ? "#ff9800" : "#f44336";

  return (
    <div className="dashboard-tab">
      <div className="dashboard-header">
        <div className="overall-score" style={{ borderColor: scoreColor }}>
          <span className="score-value" style={{ color: scoreColor }}>
            {overallScore}
          </span>
          <span className="score-max">/10</span>
          <span className="score-label">AI-Readiness</span>
        </div>

        {readiness.verdict && (
          <div className="verdict-card">
            <h3>Verdict</h3>
            <p className="verdict-text">{readiness.verdict}</p>
          </div>
        )}
      </div>

      <div className="dashboard-body">
        <div className="radar-container">
          <h3>Dimension Scores</h3>
          <ResponsiveContainer width="100%" height={400}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
              <PolarRadiusAxis domain={[0, 10]} tick={{ fontSize: 10 }} />
              <Radar
                name="Score"
                dataKey="score"
                stroke="#6366f1"
                fill="#6366f1"
                fillOpacity={0.3}
              />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="dimension-cards">
          {Object.entries(scores.dimension_scores).map(([dim, score]) => {
            const isExpanded = expandedDim === dim;
            const dimColor =
              score >= 7 ? "#4caf50" : score >= 4 ? "#ff9800" : "#f44336";

            return (
              <div
                key={dim}
                className={`dimension-card ${isExpanded ? "expanded" : ""}`}
                onClick={() => setExpandedDim(isExpanded ? null : dim)}
              >
                <div className="dim-header">
                  <span className="dim-name">{dim.replace(/_/g, " ")}</span>
                  <span className="dim-score" style={{ color: dimColor }}>
                    {score}/10
                  </span>
                </div>
                {isExpanded && (
                  <div className="dim-detail">
                    <div className="score-bar">
                      <div
                        className="score-bar-fill"
                        style={{
                          width: `${(score / 10) * 100}%`,
                          backgroundColor: dimColor,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {readiness.narrative && (
        <div className="narrative-section">
          <h3>Analysis</h3>
          <p>{readiness.narrative}</p>
          {readiness.top_strength && (
            <p>
              <strong>Top Strength:</strong> {readiness.top_strength}
            </p>
          )}
          {readiness.top_weakness && (
            <p>
              <strong>Top Weakness:</strong> {readiness.top_weakness}
            </p>
          )}
        </div>
      )}

      {readiness.action_plan && readiness.action_plan.length > 0 && (
        <div className="action-plan">
          <h3>Action Plan</h3>
          <div className="action-list">
            {readiness.action_plan.map((action, i) => (
              <div key={i} className="action-card">
                <div className="action-header">
                  <span className="action-num">#{i + 1}</span>
                  <span className={`impact-badge impact-${action.impact.toLowerCase()}`}>
                    {action.impact} impact
                  </span>
                  <span className={`effort-badge effort-${action.effort.toLowerCase()}`}>
                    {action.effort} effort
                  </span>
                </div>
                <p>{action.description}</p>
                <div className="action-meta">
                  <span>Dimension: {action.dimension}</span>
                  <span>+{action.improvement} pts</span>
                </div>
                {action.files.length > 0 && (
                  <div className="action-files">
                    {action.files.map((f, j) => (
                      <code key={j}>{f}</code>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
