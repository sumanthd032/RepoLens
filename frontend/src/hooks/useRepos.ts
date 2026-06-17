// react-query hooks for repository data. The list auto-refetches while any repo is mid-index so
// the UI reflects indexing → ready transitions without a manual reload.

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";

import { api } from "../lib/api";
import type { AddRepoRequest, Repo } from "../lib/types";

const REPOS_KEY = ["repos"] as const;

function anyIndexing(repos: Repo[] | undefined): boolean {
  return (repos ?? []).some((r) => r.status === "pending" || r.status === "indexing");
}

export function useRepos(): UseQueryResult<Repo[]> {
  return useQuery({
    queryKey: REPOS_KEY,
    queryFn: api.listRepos,
    refetchInterval: (query) => (anyIndexing(query.state.data) ? 1500 : false),
  });
}

export function useRepo(id: string | undefined): UseQueryResult<Repo> {
  return useQuery({
    queryKey: ["repo", id],
    queryFn: () => api.getRepo(id as string),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "indexing" ? 1500 : false;
    },
  });
}

export function useAddRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AddRepoRequest) => api.addRepo(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: REPOS_KEY }),
  });
}

export function useDeleteRepo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteRepo(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: REPOS_KEY }),
  });
}
