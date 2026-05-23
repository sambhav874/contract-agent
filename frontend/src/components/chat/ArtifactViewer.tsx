"use client";

import { useState } from "react";
import { Maximize2, Minimize2, X, Download } from "lucide-react";

interface Artifact {
  type: "html" | "svg" | "json";
  content: string;
}

interface ArtifactViewerProps {
  artifact: Artifact;
  onClose?: () => void;
}

export function ArtifactViewer({ artifact, onClose }: ArtifactViewerProps) {
  const [fullscreen, setFullscreen] = useState(false);

  const isHtml = artifact.type === "html";
  const isSvg = artifact.type === "svg";

  return (
    <div
      className={`border rounded-lg bg-white overflow-hidden transition-all ${
        fullscreen ? "fixed inset-4 z-50" : "relative"
      }`}
    >
      <div className="flex items-center justify-between p-3 bg-gray-100 border-b border-gray-200">
        <span className="text-sm font-medium text-gray-700">{artifact.type.toUpperCase()} Artifact</span>
        <div className="flex gap-2">
          <button
            onClick={() => setFullscreen(!fullscreen)}
            className="p-1.5 hover:bg-gray-200 rounded"
            title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {fullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          {onClose && (
            <button onClick={onClose} className="p-1.5 hover:bg-gray-200 rounded" title="Close">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className={`${fullscreen ? "h-[calc(100%-48px)]" : "h-64"} overflow-hidden`}>
        {isHtml ? (
          <iframe
            srcDoc={artifact.content}
            className="w-full h-full border-0"
            sandbox="allow-scripts"
            title="html-artifact"
          />
        ) : isSvg ? (
          <div className="p-4 w-full h-full flex items-center justify-center bg-white overflow-auto">
            <div dangerouslySetInnerHTML={{ __html: artifact.content }} />
          </div>
        ) : (
          <pre className="p-4 w-full h-full overflow-auto bg-gray-50 text-sm font-mono text-gray-800">
            {JSON.stringify(JSON.parse(artifact.content), null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
