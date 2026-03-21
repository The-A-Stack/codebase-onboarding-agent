import { useState } from "react";
import SyntaxHighlighter from "react-syntax-highlighter";
import { vs2015 } from "react-syntax-highlighter/dist/esm/styles/hljs";
import type { AnalysisResult } from "../types";

interface Props {
  result: AnalysisResult;
}

const FILE_LANGUAGES: Record<string, string> = {
  "CLAUDE.md": "markdown",
  ".github/copilot-instructions.md": "markdown",
  ".clinerules": "markdown",
  ".aider.conf.yml": "yaml",
};

export default function AgentFilesTab({ result }: Props) {
  const files = result.outputs.agent_files;
  const fileNames = Object.keys(files);
  const [activeFile, setActiveFile] = useState(fileNames[0] || "");
  const [editedFiles, setEditedFiles] = useState<Record<string, string>>({
    ...files,
  });

  const currentContent = editedFiles[activeFile] || "";
  const language = FILE_LANGUAGES[activeFile] || "markdown";

  const handleCopy = () => {
    navigator.clipboard.writeText(currentContent);
  };

  const handleDownload = () => {
    const blob = new Blob([currentContent], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = activeFile.replace("/", "__");
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleEdit = (value: string) => {
    setEditedFiles((prev) => ({ ...prev, [activeFile]: value }));
  };

  // Check for VERIFY comments
  const verifyCount = (currentContent.match(/# VERIFY/g) || []).length;

  return (
    <div className="agent-files-tab">
      <div className="file-tabs">
        {fileNames.map((name) => (
          <button
            key={name}
            className={`file-tab-btn ${activeFile === name ? "active" : ""}`}
            onClick={() => setActiveFile(name)}
          >
            {name}
          </button>
        ))}
      </div>

      <div className="file-toolbar">
        {verifyCount > 0 && (
          <span className="verify-badge">
            {verifyCount} VERIFY comment{verifyCount > 1 ? "s" : ""}
          </span>
        )}
        <button className="btn-secondary" onClick={handleCopy}>
          Copy to Clipboard
        </button>
        <button className="btn-secondary" onClick={handleDownload}>
          Download
        </button>
      </div>

      <div className="file-editor-container">
        <div className="file-preview">
          <h4>Preview</h4>
          <SyntaxHighlighter
            language={language}
            style={vs2015}
            showLineNumbers
            customStyle={{
              borderRadius: "8px",
              fontSize: "13px",
              maxHeight: "600px",
            }}
          >
            {currentContent}
          </SyntaxHighlighter>
        </div>
        <div className="file-edit">
          <h4>Edit</h4>
          <textarea
            className="code-editor"
            value={currentContent}
            onChange={(e) => handleEdit(e.target.value)}
            spellCheck={false}
          />
        </div>
      </div>
    </div>
  );
}
