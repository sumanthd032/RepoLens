// App shell: fixed sidebar + scrollable main content (the routed page renders into the Outlet).

import { Outlet } from "react-router-dom";

import { Sidebar } from "./Sidebar";

export function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
