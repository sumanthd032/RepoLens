import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names, resolving Tailwind conflicts. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

// Map tree-sitter / file-extension language names to the Observatory language colours.
const LANGUAGE_COLORS: Record<string, string> = {
  python: "var(--lang-py)",
  typescript: "var(--lang-ts)",
  javascript: "var(--lang-js)",
  go: "var(--lang-go)",
  rust: "var(--lang-rs)",
  c: "var(--lang-c)",
  cpp: "var(--lang-c)",
  java: "var(--lang-java)",
  markdown: "var(--lang-md)",
};

export function languageColor(language?: string | null): string {
  if (!language) return "var(--text-secondary)";
  return LANGUAGE_COLORS[language.toLowerCase()] ?? "var(--text-secondary)";
}

const EXTENSION_LANGUAGES: Record<string, string> = {
  py: "python",
  pyi: "python",
  ts: "typescript",
  tsx: "typescript",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  go: "go",
  rs: "rust",
  c: "c",
  h: "c",
  cc: "cpp",
  cpp: "cpp",
  hpp: "cpp",
  java: "java",
  md: "markdown",
};

/** Best-effort language detection from a file path's extension. */
export function languageForFile(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_LANGUAGES[ext] ?? "text";
}

/** Deterministic hue (0–359) from a string — used for each repo's signature orb. */
export function hashHue(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash % 360;
}

/** Compact relative time ("just now", "5m", "3h", "2d") from an ISO timestamp. */
export function relativeTime(iso?: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

/** Short repo basename for display (strips trailing slashes and .git). */
export function repoBasename(source: string): string {
  return source.replace(/\/+$/, "").replace(/\.git$/, "").split("/").pop() ?? source;
}
