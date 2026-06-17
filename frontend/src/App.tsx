import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Chat } from "./pages/Chat";
import { DriftReport } from "./pages/DriftReport";
import { RepoManager } from "./pages/RepoManager";

/** Application routing. All pages render inside the Observatory shell (sidebar + main). */
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/repos" replace />} />
        <Route path="/repos" element={<RepoManager />} />
        <Route path="/repos/:repoId/chat" element={<Chat />} />
        <Route path="/repos/:repoId/drift" element={<DriftReport />} />
        <Route path="*" element={<Navigate to="/repos" replace />} />
      </Route>
    </Routes>
  );
}
