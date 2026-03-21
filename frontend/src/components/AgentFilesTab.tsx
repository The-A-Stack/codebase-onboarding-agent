import { useState, useRef } from "react";
import type { AnalysisResult } from "../types";

interface Props {
  result: AnalysisResult;
}

export default function AgentFilesTab({ result }: Props) {
  const files = result.outputs.agent_files;
  const fileNames = Object.keys(files);
  const [activeFile, setActiveFile] = useState(fileNames[0] || "");
  const [editedFiles, setEditedFiles] = useState<Record<string, string>>({
    ...files,
  });
  const [copied, setCopied] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const currentContent = editedFiles[activeFile] || "";
  const isModified = files[activeFile] !== editedFiles[activeFile];

  const handleCopy = () => {
    navigator.clipboard.writeText(currentContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

  const handleReset = () => {
    setEditedFiles((prev) => ({ ...prev, [activeFile]: files[activeFile] }));
  };

  const handleEdit = (value: string) => {
    setEditedFiles((prev) => ({ ...prev, [activeFile]: value }));
  };

  const handleDownloadAll = () => {
    for (const [name, content] of Object.entries(editedFiles)) {
      const blob = new Blob([content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name.replace("/", "__");
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  // Count VERIFY comments
  const verifyCount = (currentContent.match(/# VERIFY/g) || []).length;
  const lineCount = currentContent.split("\n").length;

  return (
    <div className="agent-files-tab">
      {/* Header: file tabs + Download All */}
      <div className="af-header">
        <div className="af-file-tabs">
          {fileNames.map((name) => (
            <button
              key={name}
              className={`af-tab ${activeFile === name ? "active" : ""}`}
              onClick={() => setActiveFile(name)}
            >
              <span className="af-tab-icon">
                {name.endsWith(".md") ? "M" : name.endsWith(".yml") ? "Y" : "F"}
              </span>
              <span className="af-tab-name">{name}</span>
              {files[name] !== editedFiles[name] && (
                <span className="af-tab-dot" title="Modified" />
              )}
            </button>
          ))}
        </div>
        {fileNames.length > 1 && (
          <button className="af-btn af-btn-primary" onClick={handleDownloadAll}>
            Download All Files
          </button>
        )}
      </div>

      {/* Toolbar */}
      <div className="af-toolbar">
        <div className="af-toolbar-left">
          {verifyCount > 0 && (
            <span className="af-verify">
              {verifyCount} VERIFY comment{verifyCount > 1 ? "s" : ""}
            </span>
          )}
          {isModified && (
            <span className="af-modified">Modified</span>
          )}
          <span className="af-line-count">{lineCount} lines</span>
        </div>
        <div className="af-toolbar-right">
          {isModified && (
            <button className="af-btn af-btn-ghost" onClick={handleReset}>
              Reset
            </button>
          )}
          <button
            className={`af-btn ${copied ? "af-btn-success" : "af-btn-secondary"}`}
            onClick={handleCopy}
          >
            {copied ? "Copied!" : "Copy"}
          </button>
          <button className="af-btn af-btn-secondary" onClick={handleDownload}>
            Download
          </button>
        </div>
      </div>

      {/* Single editable code area */}
      <div className="af-editor-wrapper">
        <div className="af-line-numbers" aria-hidden="true">
          {currentContent.split("\n").map((_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>
        <textarea
          ref={textareaRef}
          className="af-editor"
          value={currentContent}
          onChange={(e) => handleEdit(e.target.value)}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
        />
      </div>
    </div>
  );
}
