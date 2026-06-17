// Typed fetch wrappers for the RepoLens API. Same-origin in production; the Vite dev server
// proxies /api to the FastAPI backend (see vite.config.ts).

import type { AddRepoRequest, DriftReport, Repo } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new ApiError(response.status, detail || response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listRepos: () => request<Repo[]>("/api/repos"),
  getRepo: (id: string) => request<Repo>(`/api/repos/${id}`),
  addRepo: (body: AddRepoRequest) =>
    request<Repo>("/api/repos", { method: "POST", body: JSON.stringify(body) }),
  deleteRepo: (id: string) =>
    request<void>(`/api/repos/${id}`, { method: "DELETE" }),
  runDrift: (id: string) =>
    request<DriftReport>(`/api/repos/${id}/drift`, { method: "POST" }),
  latestDrift: (id: string) => request<DriftReport>(`/api/repos/${id}/drift/latest`),
};

export const endpoints = {
  ask: (id: string) => `/api/repos/${id}/ask`,
  index: (id: string) => `/api/repos/${id}/index`,
};
