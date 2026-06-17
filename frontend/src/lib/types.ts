// Shared TypeScript types mirroring the FastAPI backend contracts (see src/repolens/api).

export type RepoStatus = "pending" | "indexing" | "ready" | "error";

export interface Repo {
  id: string;
  name: string;
  source: string;
  status: RepoStatus;
  head_sha: string | null;
  num_files: number;
  num_chunks: number;
  languages: string[];
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface AddRepoRequest {
  name?: string;
  path?: string;
  url?: string;
}

// --- Ask SSE events ----------------------------------------------------------

export interface Citation {
  file: string;
  start: number;
  end: number;
  symbol: string | null;
}

export type GroundingVerdict = "high" | "medium" | "low" | "none";

export interface Grounding {
  score: number;
  verdict: GroundingVerdict;
}

export type AskErrorType = "not_found" | "validation_failed";

export type AskEvent =
  | { event: "token"; data: { text: string } }
  | { event: "citation"; data: Citation }
  | { event: "grounding"; data: Grounding }
  | { event: "done"; data: { total_citations: number } }
  | { event: "error"; data: { message: string; type: AskErrorType } };

// --- Index SSE events --------------------------------------------------------

export interface IndexProgressEvent {
  stage: string; // "walk" | "embed" | "store" | "graph" | "done" | "error"
  message: string;
  current?: number;
  total?: number;
}

// --- Drift -------------------------------------------------------------------

export type DriftStatus = "supported" | "contradicted" | "not_found";

export interface DriftFinding {
  claim: string;
  doc_file: string;
  doc_line: number;
  status: DriftStatus;
  score: number;
  code_file: string | null;
  code_start: number | null;
  code_end: number | null;
  code_symbol: string | null;
  code_excerpt: string;
}

export interface DriftReport {
  repo: string;
  counts: Record<DriftStatus, number>;
  has_contradictions: boolean;
  findings: DriftFinding[];
}

// --- Chat (client-side view model) -------------------------------------------

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  grounding: Grounding | null;
  error: string | null;
  streaming: boolean;
}
