import React, { useEffect, useRef } from "react";
import { FileText, Search } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

interface ContractViewerProps {
  text: string;
  highlightText?: string;
  highlightTexts?: string[];
  activeHighlightText?: string;
  isLoading?: boolean;
}

export default function ContractViewer({ text, highlightText, highlightTexts, activeHighlightText, isLoading }: ContractViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const markdownComponents = {
    h1: ({ node, ...props }: any) => (
      <h1 className="mt-0 mb-5 text-xl font-bold tracking-normal text-slate-950" {...props} />
    ),
    h2: ({ node, ...props }: any) => (
      <h2 className="mt-7 mb-3 border-b border-slate-200 pb-2 text-base font-bold tracking-normal text-slate-900" {...props} />
    ),
    h3: ({ node, ...props }: any) => (
      <h3 className="mt-5 mb-2 text-sm font-bold tracking-normal text-slate-800" {...props} />
    ),
    p: ({ node, ...props }: any) => (
      <p className="mb-3 text-[13px] leading-7 text-slate-700" {...props} />
    ),
    ul: ({ node, ...props }: any) => (
      <ul className="mb-3 list-disc space-y-1 pl-5 text-[13px] leading-7 text-slate-700" {...props} />
    ),
    ol: ({ node, ...props }: any) => (
      <ol className="mb-3 list-decimal space-y-1 pl-5 text-[13px] leading-7 text-slate-700" {...props} />
    ),
    li: ({ node, ...props }: any) => <li className="pl-1" {...props} />,
    strong: ({ node, ...props }: any) => <strong className="font-bold text-slate-900" {...props} />,
    code: ({ node, ...props }: any) => (
      <code className="rounded bg-slate-100 px-1 py-0.5 text-[12px] text-slate-800" {...props} />
    ),
    table: ({ node, ...props }: any) => (
      <div className="my-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full border-collapse text-left text-xs" {...props} />
      </div>
    ),
    th: ({ node, ...props }: any) => (
      <th className="border-b border-slate-200 bg-slate-50 px-3 py-2 font-bold text-slate-600" {...props} />
    ),
    td: ({ node, ...props }: any) => (
      <td className="border-b border-slate-100 px-3 py-2 text-slate-700" {...props} />
    ),
    mark: ({ node, className, ...props }: any) => (
      <mark
        className={`rounded px-1 font-bold text-slate-950 shadow-sm ${
          className === "active-source"
            ? "bg-cyan-300 ring-2 ring-cyan-500"
            : "bg-yellow-200"
        }`}
        {...props}
      />
    ),
  };

  const buildHighlightedMarkdown = () => {
    if (!text) return "";

    const displayText = text.replace(/\\n/g, "\n");
    const terms: string[] = [];
    if (highlightTexts && highlightTexts.length > 0) {
      highlightTexts.forEach(t => {
        if (t && t.trim()) terms.push(t.trim());
      });
    }
    if (highlightText && highlightText.trim()) {
      terms.push(highlightText.trim());
    }

    if (terms.length === 0) {
      return displayText;
    }

    const ranges: { start: number; end: number; active: boolean }[] = [];
    const lowerText = displayText.toLowerCase();

    const addMatches = (term: string, active: boolean) => {
      const lowerTerm = term.toLowerCase();
      let index = lowerText.indexOf(lowerTerm);
      const beforeCount = ranges.length;

      while (index !== -1) {
        ranges.push({ start: index, end: index + term.length, active });
        index = lowerText.indexOf(lowerTerm, index + 1);
      }

      if (ranges.length === beforeCount) {
        const sentences = term.split(/(?<=[.!?])\s+/);
        sentences.forEach(s => {
          const trimmed = s.trim();
          if (trimmed.length > 20) {
            let sIndex = lowerText.indexOf(trimmed.toLowerCase());
            while (sIndex !== -1) {
              ranges.push({ start: sIndex, end: sIndex + trimmed.length, active });
              sIndex = lowerText.indexOf(trimmed.toLowerCase(), sIndex + 1);
            }
          }
        });
      }
    };

    terms.forEach(term => addMatches(term, false));
    if (activeHighlightText && activeHighlightText.trim()) {
      addMatches(activeHighlightText.trim(), true);
    }

    if (ranges.length === 0) {
      return displayText;
    }

    ranges.sort((a, b) => a.start - b.start);
    const mergedRanges: { start: number; end: number; active: boolean }[] = [];
    let current = ranges[0];

    for (let i = 1; i < ranges.length; i++) {
      const next = ranges[i];
      if (next.start <= current.end) {
        current.end = Math.max(current.end, next.end);
        current.active = current.active || next.active;
      } else {
        mergedRanges.push(current);
        current = next;
      }
    }
    mergedRanges.push(current);

    let markdown = "";
    let lastIndex = 0;

    mergedRanges.forEach((range, idx) => {
      if (range.start > lastIndex) {
        markdown += displayText.substring(lastIndex, range.start);
      }
      const attrs = `${idx === 0 ? ' id="highlighted-citation"' : ""}${range.active ? ' class="active-source"' : ""}`;
      markdown += `<mark${attrs}>${displayText.substring(range.start, range.end)}</mark>`;
      lastIndex = range.end;
    });

    if (lastIndex < displayText.length) {
      markdown += displayText.substring(lastIndex);
    }

    return markdown;
  };

  useEffect(() => {
    if (highlightText || activeHighlightText || (highlightTexts && highlightTexts.length > 0)) {
      setTimeout(() => {
        const el = document.getElementById("highlighted-citation");
        if (el && containerRef.current) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 100);
    }
  }, [highlightText, activeHighlightText, highlightTexts, text]);

  const hasHighlights = highlightText || activeHighlightText || (highlightTexts && highlightTexts.length > 0);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col h-full min-h-0">
      <div className="px-4 py-3 border-b border-gray-100 bg-white flex items-center justify-between">
        <h3 className="text-sm font-bold text-gray-800 flex items-center gap-2">
          <FileText className="h-4 w-4 text-indigo-500" />
          Contract Viewer
        </h3>
        {hasHighlights && (
          <span className="text-[10px] text-indigo-600 bg-indigo-50 px-2 py-1 rounded-md flex items-center gap-1 font-medium">
            <Search className="h-3 w-3" /> Citation Highlighted
          </span>
        )}
      </div>
      <div className="p-5 pb-16 overflow-y-auto flex-1 bg-slate-50/60" ref={containerRef}>
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <span className="text-xs text-gray-400 font-medium animate-pulse">Loading contract text...</span>
          </div>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
            components={markdownComponents}
          >
            {buildHighlightedMarkdown()}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}
