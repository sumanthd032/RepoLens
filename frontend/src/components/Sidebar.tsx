// Fixed left navigation. Always shows Repositories; when a repo is selected (from the URL) it
// reveals that repo's Chat and Drift Report sub-navigation.

import { NavLink, useMatch } from "react-router-dom";
import {
  BookOpen,
  GitCompare,
  MessageSquare,
  Settings,
  Telescope,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useRepos } from "../hooks/useRepos";
import { cn } from "../lib/utils";

function NavItem({
  to,
  icon: Icon,
  label,
  nested = false,
  end = false,
}: {
  to: string;
  icon: LucideIcon;
  label: string;
  nested?: boolean;
  end?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
          "focus-visible:outline focus-visible:outline-accent-purple",
          nested && "ml-3 text-[13px]",
          isActive
            ? "border-l-2 border-accent-purple bg-muted text-text-primary"
            : "text-text-secondary hover:bg-muted/50 hover:text-text-primary",
        )
      }
    >
      <Icon size={nested ? 16 : 18} strokeWidth={1.5} />
      <span className="truncate">{label}</span>
    </NavLink>
  );
}

export function Sidebar() {
  const match = useMatch("/repos/:repoId/*");
  const repoId = match?.params.repoId;
  const { data: repos } = useRepos();
  const activeRepo = repos?.find((r) => r.id === repoId);

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border-subtle bg-base">
      <div className="flex items-center gap-2 px-5 py-5">
        <Telescope size={22} className="text-accent-purple" strokeWidth={1.5} />
        <span className="bg-accent-grad bg-clip-text text-xl font-medium text-transparent">
          RepoLens
        </span>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        <p className="px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wider text-text-muted">
          Navigation
        </p>
        <NavItem to="/repos" icon={BookOpen} label="Repositories" end />

        {activeRepo && (
          <div className="space-y-1 pt-1">
            <p className="truncate px-3 pt-2 text-xs font-medium text-text-secondary">
              {activeRepo.name}
            </p>
            <NavItem
              to={`/repos/${activeRepo.id}/chat`}
              icon={MessageSquare}
              label="Chat"
              nested
            />
            <NavItem
              to={`/repos/${activeRepo.id}/drift`}
              icon={GitCompare}
              label="Drift Report"
              nested
            />
          </div>
        )}
      </nav>

      <div className="border-t border-border-subtle px-3 py-3">
        <div className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-muted">
          <Settings size={18} strokeWidth={1.5} />
          <span>Settings</span>
        </div>
      </div>
    </aside>
  );
}
