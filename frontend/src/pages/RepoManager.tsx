// Repository Manager: grid of repo cards, add-repo modal, live indexing progress, empty state.

import { useState } from "react";
import { Plus, Telescope } from "lucide-react";

import { AddRepoModal } from "../components/AddRepoModal";
import { IndexProgress } from "../components/IndexProgress";
import { RepoCard } from "../components/RepoCard";
import { useDeleteRepo, useRepos } from "../hooks/useRepos";

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-default py-20 text-center">
      <Telescope size={48} className="text-accent-purple" strokeWidth={1.25} />
      <h2 className="mt-4 text-xl font-medium text-text-primary">
        No repositories indexed yet
      </h2>
      <p className="mt-1 max-w-sm text-sm text-text-secondary">
        Add a GitHub repository or local path to start asking questions grounded in the real code.
      </p>
      <button
        type="button"
        onClick={onAdd}
        className="mt-5 inline-flex items-center gap-2 rounded-lg bg-accent-grad px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
      >
        <Plus size={16} />
        Add repository
      </button>
    </div>
  );
}

export function RepoManager() {
  const [modalOpen, setModalOpen] = useState(false);
  const { data: repos, isLoading } = useRepos();
  const deleteRepo = useDeleteRepo();

  const indexing = (repos ?? []).filter(
    (r) => r.status === "indexing" || r.status === "pending",
  );

  return (
    <div className="mx-auto max-w-5xl px-8 py-8">
      {indexing.map((repo) => (
        <IndexProgress key={repo.id} repoId={repo.id} name={repo.name} />
      ))}

      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-medium text-text-primary">Repositories</h1>
          <p className="text-sm text-text-secondary">
            {repos?.length ?? 0} indexed · ask questions grounded in the code
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-accent-grad px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          <Plus size={16} />
          Add repository
        </button>
      </header>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : !repos || repos.length === 0 ? (
        <EmptyState onAdd={() => setModalOpen(true)} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {repos.map((repo) => (
            <RepoCard key={repo.id} repo={repo} onDelete={(id) => deleteRepo.mutate(id)} />
          ))}
        </div>
      )}

      {modalOpen && <AddRepoModal onClose={() => setModalOpen(false)} />}
    </div>
  );
}
