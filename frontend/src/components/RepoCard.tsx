// An "observatory orb" card for one repository: a deterministic gradient orb, a status dot, an
// indexing progress bar, and quick stats. Clicking it opens the repo's chat.

import { useNavigate } from "react-router-dom";
import { AlertCircle, Trash2 } from "lucide-react";

import type { Repo } from "../lib/types";
import { cn, hashHue, relativeTime, repoBasename } from "../lib/utils";

interface RepoCardProps {
  repo: Repo;
  indexedPercent?: number;
  onDelete: (id: string) => void;
}

const STATUS_DOT: Record<Repo["status"], string> = {
  pending: "bg-warning animate-pulse-slow",
  indexing: "bg-success animate-pulse-slow",
  ready: "bg-success",
  error: "bg-danger",
};

const STATUS_LABEL: Record<Repo["status"], string> = {
  pending: "Queued",
  indexing: "Indexing",
  ready: "Ready",
  error: "Error",
};

export function RepoCard({ repo, indexedPercent, onDelete }: RepoCardProps) {
  const navigate = useNavigate();
  const hue = hashHue(repo.name);
  const active = repo.status === "indexing" || repo.status === "pending";
  const percent = active ? Math.round(indexedPercent ?? 0) : 100;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => repo.status === "ready" && navigate(`/repos/${repo.id}/chat`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && repo.status === "ready") navigate(`/repos/${repo.id}/chat`);
      }}
      className={cn(
        "group cursor-pointer rounded-xl border border-border-default bg-elevated p-4 transition-all duration-200",
        "hover:scale-[1.01] hover:border-border-strong focus-visible:outline focus-visible:outline-accent-purple",
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className="h-10 w-10 shrink-0 rounded-full"
          style={{
            background: `conic-gradient(from 180deg, hsl(${hue}deg 70% 60%), hsl(${hue + 60}deg 60% 50%))`,
          }}
          aria-hidden
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={cn("h-2 w-2 shrink-0 rounded-full", STATUS_DOT[repo.status])} />
            <h3 className="truncate text-base font-medium text-text-primary">{repo.name}</h3>
          </div>
          <p className="truncate font-mono text-xs text-text-secondary">
            {repoBasename(repo.source)}
          </p>
        </div>
        <button
          type="button"
          aria-label={`Delete ${repo.name}`}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(repo.id);
          }}
          className="rounded p-1 text-text-muted opacity-0 transition-opacity hover:text-danger group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-accent-purple"
        >
          <Trash2 size={15} />
        </button>
      </div>

      <div className="mt-4">
        {active ? (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-accent-grad transition-all duration-300"
              style={{ width: `${percent}%` }}
            />
          </div>
        ) : repo.status === "error" ? (
          <div className="flex items-center gap-1.5 text-xs text-danger">
            <AlertCircle size={13} />
            <span className="truncate">{repo.error ?? "Indexing failed"}</span>
          </div>
        ) : (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full w-full rounded-full bg-accent-grad" />
          </div>
        )}
      </div>

      <div className="mt-2 flex items-center gap-2 text-xs text-text-secondary">
        <span>{STATUS_LABEL[repo.status]}</span>
        <span className="text-text-muted">·</span>
        <span>{repo.num_chunks} chunks</span>
        <span className="text-text-muted">·</span>
        <span>{repo.languages.length} langs</span>
        <span className="text-text-muted">·</span>
        <span>{relativeTime(repo.updated_at)}</span>
      </div>
    </div>
  );
}
