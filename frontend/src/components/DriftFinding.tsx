// A single drift finding: the documentation claim (left, amber) beside the retrieved code
// (right, blue), with a status badge. The split makes doc/code disagreement obvious at a glance.

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { coldarkDark } from "react-syntax-highlighter/dist/esm/styles/prism";

import type { DriftFinding as DriftFindingModel, DriftStatus } from "../lib/types";
import { cn, languageForFile } from "../lib/utils";

const STATUS_BADGE: Record<DriftStatus, string> = {
  contradicted: "bg-danger/10 text-danger border-danger/30",
  not_found: "bg-warning/10 text-warning border-warning/30",
  supported: "bg-success/10 text-success border-success/30",
};

const STATUS_LABEL: Record<DriftStatus, string> = {
  contradicted: "CONTRADICTED",
  not_found: "NOT FOUND",
  supported: "SUPPORTED",
};

const STATUS_DOT: Record<DriftStatus, string> = {
  contradicted: "bg-danger",
  not_found: "bg-warning",
  supported: "bg-success",
};

export function DriftFinding({ finding }: { finding: DriftFindingModel }) {
  const hasCode = Boolean(finding.code_file);
  const lang = hasCode ? languageForFile(finding.code_file as string) : "text";

  return (
    <div className="rounded-xl border border-border-default bg-elevated p-4">
      <div className="mb-3 flex items-center justify-between">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
            STATUS_BADGE[finding.status],
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[finding.status])} />
          {STATUS_LABEL[finding.status]}
        </span>
        {hasCode && (
          <span className="font-mono text-xs text-text-muted">
            score {finding.score.toFixed(2)}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border-l-2 border-warning bg-warning/5 p-3">
          <div className="mb-1.5 font-mono text-xs text-text-secondary">
            {finding.doc_file}:{finding.doc_line}
          </div>
          <p className="text-sm italic text-text-primary">“{finding.claim}”</p>
        </div>

        <div className="rounded-lg border-l-2 border-info bg-info/5 p-3">
          {hasCode ? (
            <>
              <div className="mb-1.5 font-mono text-xs text-text-secondary">
                {finding.code_file}:{finding.code_start}–{finding.code_end}
                {finding.code_symbol ? ` · ${finding.code_symbol}` : ""}
              </div>
              <div className="overflow-x-auto font-mono text-[13px]">
                <SyntaxHighlighter
                  language={lang}
                  style={coldarkDark}
                  wrapLongLines
                  customStyle={{ background: "transparent", margin: 0, padding: 0, fontSize: "13px" }}
                >
                  {finding.code_excerpt.trim()}
                </SyntaxHighlighter>
              </div>
            </>
          ) : (
            <p className="text-sm text-text-muted">No relevant code was retrieved for this claim.</p>
          )}
        </div>
      </div>
    </div>
  );
}
