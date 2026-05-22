import { useMemo, useState } from "react";
import { getArtifactContent } from "../api/client";
import type { Artifact, ArtifactContent, EvidenceSelection } from "../api/types";
import { useAsyncResource } from "../hooks/useAsyncResource";

/**
 * Props for the artifact viewer component.
 */
export interface ArtifactViewerProps {
  /** Indexed artifacts for the selected run. */
  artifacts: Artifact[];
  /** Currently selected artifact evidence span, if any. */
  evidenceSelection: EvidenceSelection | null;
  /** Callback fired when an annotator selects artifact evidence lines. */
  onSelectEvidence: (selection: EvidenceSelection | null) => void;
}

/**
 * Render content-addressed artifacts and their logical run paths.
 *
 * @param props - Artifact viewer inputs.
 * @returns Artifact list panel.
 */
export function ArtifactViewer({
  artifacts,
  evidenceSelection,
  onSelectEvidence
}: ArtifactViewerProps) {
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const [anchorLine, setAnchorLine] = useState<number | null>(null);
  const activeArtifact = artifacts.find((artifact) => artifact.id === artifactId) ?? artifacts[0] ?? null;
  const content = useAsyncResource<ArtifactContent | null>(
    () => (activeArtifact ? getArtifactContent(activeArtifact.id) : Promise.resolve(null)),
    [activeArtifact?.id]
  );
  const lines = useMemo(() => content.data?.content.split(/\n/) ?? [], [content.data?.content]);

  const highlightedRange =
    evidenceSelection &&
    activeArtifact &&
    content.data &&
    evidenceSelection.artifact_id === activeArtifact.id &&
    evidenceSelection.file_path === content.data.logical_path
      ? { start: evidenceSelection.start_line, end: evidenceSelection.end_line }
      : null;

  /**
   * Update the selected line span and notify the parent annotation panel.
   */
  function selectLine(lineNumber: number) {
    if (!activeArtifact || !content.data) {
      return;
    }
    const start = anchorLine === null ? lineNumber : Math.min(anchorLine, lineNumber);
    const end = anchorLine === null ? lineNumber : Math.max(anchorLine, lineNumber);
    const selectedText = lines.slice(start - 1, end).join("\n");
    setAnchorLine(anchorLine === null ? lineNumber : null);
    onSelectEvidence({
      artifact_id: activeArtifact.id,
      file_path: content.data.logical_path,
      start_line: start,
      end_line: end,
      selected_text: selectedText
    });
  }

  return (
    <section className="panel artifact-panel">
      <h2>Artifacts</h2>
      <p className="artifact-hint">Click line numbers to attach evidence. Long lines wrap.</p>
      <div className="artifact-browser">
        <ul className="artifact-list">
          {artifacts.map((artifact) => (
            <li key={artifact.id}>
              <button
                className={artifact.id === activeArtifact?.id ? "text-button selected" : "text-button"}
                onClick={() => {
                  setArtifactId(artifact.id);
                  setAnchorLine(null);
                  onSelectEvidence(null);
                }}
              >
                <strong>{artifact.logical_path}</strong>
                <span>{artifact.artifact_type}</span>
                <code>{artifact.content_hash.slice(0, 12)}</code>
              </button>
            </li>
          ))}
        </ul>
        <div className="artifact-content">
          {content.error ? <div className="error-inline">{content.error}</div> : null}
          {!content.data ? <div className="empty-state">Select an artifact.</div> : null}
          {content.data?.truncated ? (
            <div className="warning-inline">
              Content truncated ({content.data.size_bytes} bytes, showing {content.data.max_bytes} max).
            </div>
          ) : null}
          {content.data ? (
            <div className="code-block" role="document">
              {lines.map((line, index) => {
                const lineNumber = index + 1;
                const inRange =
                  highlightedRange &&
                  lineNumber >= highlightedRange.start &&
                  lineNumber <= highlightedRange.end;
                const isAnchor = anchorLine === lineNumber;
                return (
                  <div
                    key={`${content.data?.artifact_id}-${lineNumber}`}
                    className={
                      inRange ? "code-line selected" : isAnchor ? "code-line anchor" : "code-line"
                    }
                  >
                    <button
                      type="button"
                      className="line-gutter"
                      aria-label={`Select line ${lineNumber}`}
                      onClick={() => selectLine(lineNumber)}
                    >
                      {lineNumber}
                    </button>
                    <code className="line-text">{line || "\u00a0"}</code>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
