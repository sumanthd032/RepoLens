// Renders one chat turn. User turns are right-aligned bubbles; assistant turns render the grounded
// answer with inline file:line-range citation chips that expand a CitationCard on click, plus the
// grounding ring once the answer completes.

import { useState, type ReactNode } from "react";
import { AlertCircle, Telescope, User } from "lucide-react";

import type { ChatMessage as ChatMessageModel } from "../lib/types";
import { cn, languageColor, languageForFile } from "../lib/utils";
import { CitationCard } from "./CitationCard";
import { GroundingBadge } from "./GroundingBadge";

const CITATION_RE = /\[([^[\]\s:]+):(\d+)(?:-(\d+))?\]/g;

function citationKey(file: string, start: number, end: number): string {
  return `${file}:${start}-${end}`;
}

interface ParsedCitation {
  file: string;
  start: number;
  end: number;
  key: string;
}

/** Split answer text into prose segments and clickable citation chips. */
function renderBody(
  text: string,
  expanded: Set<string>,
  toggle: (key: string) => void,
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let chipIndex = 0;
  CITATION_RE.lastIndex = 0;

  while ((match = CITATION_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const file = match[1];
    const start = Number(match[2]);
    const end = match[3] ? Number(match[3]) : start;
    const key = citationKey(file, start, end);
    const color = languageColor(languageForFile(file));
    nodes.push(
      <button
        key={`chip-${chipIndex}`}
        type="button"
        onClick={() => toggle(key)}
        className={cn(
          "mx-0.5 cursor-pointer rounded border border-border-default bg-muted px-1.5 py-0.5 font-mono text-xs align-baseline",
          "transition-colors hover:border-accent-purple focus-visible:outline focus-visible:outline-accent-purple",
          expanded.has(key) && "border-accent-purple",
        )}
        style={{ color }}
      >
        {file}:{start}-{end}
      </button>,
    );
    chipIndex += 1;
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

function parseCitations(text: string): ParsedCitation[] {
  const seen = new Set<string>();
  const out: ParsedCitation[] = [];
  let match: RegExpExecArray | null;
  CITATION_RE.lastIndex = 0;
  while ((match = CITATION_RE.exec(text)) !== null) {
    const file = match[1];
    const start = Number(match[2]);
    const end = match[3] ? Number(match[3]) : start;
    const key = citationKey(file, start, end);
    if (!seen.has(key)) {
      seen.add(key);
      out.push({ file, start, end, key });
    }
  }
  return out;
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex items-start justify-end gap-3">
      <div className="ml-auto max-w-[70%] rounded-2xl rounded-tr-sm bg-muted px-4 py-3 text-sm text-text-primary">
        {content}
      </div>
      <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border-default bg-elevated">
        <User size={15} className="text-text-secondary" />
      </div>
    </div>
  );
}

function AssistantMessage({ message }: { message: ChatMessageModel }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const citationByKey = new Map(
    message.citations.map((c) => [citationKey(c.file, c.start, c.end), c]),
  );
  const parsed = parseCitations(message.content);

  return (
    <div className="flex items-start gap-3">
      <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-grad">
        <Telescope size={15} className="text-white" />
      </div>
      <div className="max-w-full flex-1 rounded-2xl rounded-tl-sm border border-border-subtle bg-elevated p-4">
        <div className="mb-2 text-xs font-medium text-text-secondary">RepoLens</div>

        {message.error ? (
          <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            <AlertCircle size={16} />
            {message.error}
          </div>
        ) : (
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-text-primary">
            {renderBody(message.content, expanded, toggle)}
            {message.streaming && (
              <span className="ml-0.5 inline-block animate-stream-cursor">▍</span>
            )}
          </div>
        )}

        {parsed
          .filter((c) => expanded.has(c.key))
          .map((c) => {
            const known = citationByKey.get(c.key);
            return (
              <CitationCard
                key={c.key}
                citation={known ?? { file: c.file, start: c.start, end: c.end, symbol: null }}
              />
            );
          })}

        {message.grounding && !message.error && (
          <div className="mt-4 border-t border-border-subtle pt-3">
            <GroundingBadge grounding={message.grounding} />
          </div>
        )}
      </div>
    </div>
  );
}

export function ChatMessage({ message }: { message: ChatMessageModel }) {
  return message.role === "user" ? (
    <UserMessage content={message.content} />
  ) : (
    <AssistantMessage message={message} />
  );
}
