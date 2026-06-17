import { Navigate, Route, Routes } from "react-router-dom";

/**
 * Application shell and routing skeleton.
 *
 * The real pages (Repo Manager, Chat, Drift Report) and the Observatory layout are implemented
 * in Step 9. For now these are minimal placeholders so the router and build are wired up.
 */

function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="bg-accent-grad bg-clip-text text-xl font-medium text-transparent">
        RepoLens
      </h1>
      <p className="text-sm text-text-secondary">{title}</p>
      <p className="text-xs text-text-muted">
        The Observatory UI is built in Step 9.
      </p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/repos" replace />} />
      <Route
        path="/repos"
        element={<Placeholder title="Repository Manager" />}
      />
      <Route
        path="/repos/:repoId/chat"
        element={<Placeholder title="Chat" />}
      />
      <Route
        path="/repos/:repoId/drift"
        element={<Placeholder title="Drift Report" />}
      />
      <Route path="*" element={<Placeholder title="Not found" />} />
    </Routes>
  );
}
