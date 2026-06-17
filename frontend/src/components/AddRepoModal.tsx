// Glass modal for adding a repository by local path or clone URL. Submits via the useAddRepo
// mutation; the new repo then begins indexing in the background.

import { useState, type FormEvent } from "react";
import { FolderGit2, Link2, X } from "lucide-react";

import { useAddRepo } from "../hooks/useRepos";
import { ApiError } from "../lib/api";
import { cn } from "../lib/utils";

type Mode = "path" | "url";

export function AddRepoModal({ onClose }: { onClose: () => void }) {
  const [mode, setMode] = useState<Mode>("path");
  const [source, setSource] = useState("");
  const [name, setName] = useState("");
  const addRepo = useAddRepo();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!source.trim()) return;
    const body =
      mode === "path"
        ? { path: source.trim(), name: name.trim() || undefined }
        : { url: source.trim(), name: name.trim() || undefined };
    addRepo.mutate(body, { onSuccess: onClose });
  };

  const error =
    addRepo.error instanceof ApiError
      ? addRepo.error.message
      : addRepo.error
        ? "Could not add repository"
        : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-void/60 p-4"
      onClick={onClose}
    >
      <div
        className="glass w-full max-w-md rounded-xl p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal
        aria-label="Add repository"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-medium text-text-primary">Add repository</h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="rounded p-1 text-text-muted hover:text-text-primary focus-visible:outline focus-visible:outline-accent-purple"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mb-4 flex gap-2">
          {(["path", "url"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn(
                "flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
                mode === m
                  ? "border-accent-purple bg-muted text-text-primary"
                  : "border-border-default text-text-secondary hover:border-border-strong",
              )}
            >
              {m === "path" ? <FolderGit2 size={15} /> : <Link2 size={15} />}
              {m === "path" ? "Local path" : "Clone URL"}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="space-y-3">
          <input
            autoFocus
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder={mode === "path" ? "/path/to/repo" : "https://github.com/org/repo"}
            className="w-full rounded-lg border border-border-default bg-muted px-3 py-2 font-mono text-sm text-text-primary placeholder:text-text-muted focus:border-accent-purple focus:outline-none"
          />
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Display name (optional)"
            className="w-full rounded-lg border border-border-default bg-muted px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-purple focus:outline-none"
          />

          {error && (
            <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={addRepo.isPending || !source.trim()}
            className="w-full rounded-lg bg-accent-grad px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {addRepo.isPending ? "Adding…" : "Add & index"}
          </button>
        </form>
      </div>
    </div>
  );
}
