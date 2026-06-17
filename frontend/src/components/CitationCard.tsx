// An expandable citation: file/symbol/language/line-range header, plus a syntax-highlighted code
// excerpt when one is available (drift findings carry code; ask citations carry only the span).

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { coldarkDark } from "react-syntax-highlighter/dist/esm/styles/prism";

import type { Citation } from "../lib/types";
import { languageColor, languageForFile } from "../lib/utils";

interface CitationCardProps {
  citation: Citation;
  code?: string;
  language?: string;
}

const codeTheme = {
  ...coldarkDark,
  'pre[class*="language-"]': {
    ...coldarkDark['pre[class*="language-"]'],
    background: "transparent",
    margin: 0,
    padding: 0,
  },
  'code[class*="language-"]': {
    ...coldarkDark['code[class*="language-"]'],
    background: "transparent",
  },
};

export function CitationCard({ citation, code, language }: CitationCardProps) {
  const lang = language ?? languageForFile(citation.file);
  const color = languageColor(lang);

  return (
    <div
      className="mt-2 overflow-hidden rounded-lg border-l-2 bg-muted animate-in"
      style={{ borderLeftColor: color }}
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-border-subtle px-3 py-2 text-xs">
        <span className="font-mono text-text-secondary">{citation.file}</span>
        {citation.symbol && (
          <>
            <span className="text-text-muted">•</span>
            <span className="font-medium text-text-primary">{citation.symbol}</span>
          </>
        )}
        <span className="text-text-muted">•</span>
        <span
          className="rounded bg-base px-1.5 py-0.5 text-[10px] capitalize"
          style={{ color }}
        >
          {lang}
        </span>
        <span className="text-text-muted">•</span>
        <span className="text-text-muted">
          lines {citation.start}–{citation.end}
        </span>
      </div>

      {code ? (
        <div className="overflow-x-auto px-3 py-2 font-mono text-[13px]">
          <SyntaxHighlighter
            language={lang}
            style={codeTheme}
            showLineNumbers
            startingLineNumber={citation.start}
            wrapLongLines
            customStyle={{ background: "transparent", fontSize: "13px" }}
            lineNumberStyle={{ color: "var(--text-muted)", minWidth: "2.5em" }}
          >
            {code.replace(/\n$/, "")}
          </SyntaxHighlighter>
        </div>
      ) : (
        <div className="px-3 py-2 font-mono text-xs text-text-muted">
          Cited span — open {citation.file} at lines {citation.start}–{citation.end}.
        </div>
      )}
    </div>
  );
}
