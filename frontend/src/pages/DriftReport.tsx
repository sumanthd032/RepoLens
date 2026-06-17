// Drift Report page: runs a drift check (or loads the latest), then shows findings grouped into
// Contradicted / Not Found / Supported tabs.

import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompare, Loader2, RefreshCw } from "lucide-react";

import { DriftFinding } from "../components/DriftFinding";
import { useRepo } from "../hooks/useRepos";
import { api } from "../lib/api";
import type { DriftReport as DriftReportModel, DriftStatus } from "../lib/types";
import { cn } from "../lib/utils";

const TABS: { status: DriftStatus; label: string; color: string }[] = [
  { status: "contradicted", label: "Contradicted", color: "text-danger" },
  { status: "not_found", label: "Not Found", color: "text-warning" },
  { status: "supported", label: "Supported", color: "text-success" },
];

function EmptyState({ onRun, running }: { onRun: () => void; running: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-default py-20 text-center">
      <GitCompare size={40} className="text-accent-purple" strokeWidth={1.25} />
      <h2 className="mt-4 text-xl font-medium text-text-primary">No drift report yet</h2>
      <p className="mt-1 max-w-sm text-sm text-text-secondary">
        Run a drift check to find where documentation disagrees with the code.
      </p>
      <button
        type="button"
        onClick={onRun}
        disabled={running}
        className="mt-5 inline-flex items-center gap-2 rounded-lg bg-accent-grad px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        {running ? <Loader2 size={16} className="animate-spin" /> : <GitCompare size={16} />}
        {running ? "Checking…" : "Run drift check"}
      </button>
    </div>
  );
}

export function DriftReport() {
  const { repoId } = useParams<{ repoId: string }>();
  const { data: repo } = useRepo(repoId);
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<DriftStatus>("contradicted");

  const latest = useQuery({
    queryKey: ["drift", repoId],
    queryFn: () => api.latestDrift(repoId as string),
    enabled: Boolean(repoId),
    retry: false,
  });

  const run = useMutation({
    mutationFn: () => api.runDrift(repoId as string),
    onSuccess: (data: DriftReportModel) =>
      queryClient.setQueryData(["drift", repoId], data),
  });

  const report = run.data ?? latest.data;
  const running = run.isPending;

  if (latest.isLoading) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-8">
        <div className="h-40 animate-pulse rounded-2xl bg-muted" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-8">
        <h1 className="mb-6 text-xl font-medium text-text-primary">Drift Report</h1>
        <EmptyState onRun={() => run.mutate()} running={running} />
      </div>
    );
  }

  const findings = report.findings.filter((f) => f.status === tab);

  return (
    <div className="mx-auto max-w-4xl px-8 py-8">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-medium text-text-primary">Drift Report</h1>
          <p className="text-sm text-text-secondary">
            {repo?.name ?? report.repo} · {report.findings.length} claims checked
          </p>
        </div>
        <button
          type="button"
          onClick={() => run.mutate()}
          disabled={running}
          className="inline-flex items-center gap-2 rounded-lg border border-border-default px-4 py-2 text-sm text-text-primary transition-colors hover:border-border-strong disabled:opacity-60"
        >
          {running ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <RefreshCw size={15} />
          )}
          {running ? "Checking…" : "Run new check"}
        </button>
      </header>

      <div className="mb-6 flex gap-2 border-b border-border-subtle">
        {TABS.map(({ status, label, color }) => (
          <button
            key={status}
            type="button"
            onClick={() => setTab(status)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2 text-sm transition-colors",
              tab === status
                ? "border-accent-purple text-text-primary"
                : "border-transparent text-text-secondary hover:text-text-primary",
            )}
          >
            <span className={color}>●</span> {label}
            <span className="ml-1.5 text-text-muted">{report.counts[status]}</span>
          </button>
        ))}
      </div>

      {findings.length === 0 ? (
        <p className="py-12 text-center text-sm text-text-secondary">
          No {TABS.find((t) => t.status === tab)?.label.toLowerCase()} claims.
        </p>
      ) : (
        <div className="space-y-4">
          {findings.map((finding, i) => (
            <DriftFinding key={`${finding.doc_file}-${finding.doc_line}-${i}`} finding={finding} />
          ))}
        </div>
      )}
    </div>
  );
}
