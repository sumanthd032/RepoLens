// Live indexing progress for a repo, driven by the /index SSE stream: a fixed top progress bar
// plus a glass detail panel showing the current stage and file being processed.

import { useState } from "react";

import { endpoints } from "../lib/api";
import { useEventStream, type SSEFrame } from "../hooks/useSSE";
import type { IndexProgressEvent } from "../lib/types";

const STAGE_LABEL: Record<string, string> = {
  walk: "Scanning",
  embed: "Embedding",
  store: "Storing vectors",
  graph: "Building symbol graph",
  done: "Complete",
  error: "Failed",
};

export function IndexProgress({ repoId, name }: { repoId: string; name: string }) {
  const [event, setEvent] = useState<IndexProgressEvent | null>(null);

  useEventStream(endpoints.index(repoId), (frame: SSEFrame) => {
    setEvent(frame.data as IndexProgressEvent);
  });

  if (!event || event.stage === "done") return null;

  const total = event.total ?? 0;
  const current = event.current ?? 0;
  const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : undefined;
  const stage = STAGE_LABEL[event.stage] ?? event.stage;

  return (
    <>
      <div className="fixed left-0 right-0 top-0 z-50 h-0.5 bg-border-subtle">
        <div
          className="h-full bg-accent-grad transition-all duration-300"
          style={{ width: percent !== undefined ? `${percent}%` : "40%" }}
        />
      </div>
      <div className="mb-6 rounded-lg border border-border-subtle bg-muted/50 p-4 backdrop-blur-glass">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium text-text-primary">
            Indexing {name} · {stage}
          </span>
          {total > 0 && (
            <span className="text-2xl font-medium text-text-primary">
              {current}
              <span className="text-sm text-text-secondary"> / {total}</span>
            </span>
          )}
        </div>
        {event.message && (
          <p className="mt-1 truncate font-mono text-xs text-text-secondary">{event.message}</p>
        )}
      </div>
    </>
  );
}
