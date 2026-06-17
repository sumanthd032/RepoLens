// Chat page: streams a grounded answer token-by-token, collecting citations and the grounding
// score from the /ask SSE stream and rendering them via ChatMessage.

import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { MessageSquare, SendHorizontal } from "lucide-react";

import { ChatMessage } from "../components/ChatMessage";
import { useRepo } from "../hooks/useRepos";
import { streamSSE } from "../hooks/useSSE";
import { endpoints } from "../lib/api";
import type {
  ChatMessage as ChatMessageModel,
  Citation,
  Grounding,
} from "../lib/types";

const SUGGESTIONS = [
  "How does authentication work?",
  "What is the entry point?",
  "How are errors handled?",
];

let counter = 0;
const nextId = () => `m${(counter += 1)}`;

export function Chat() {
  const { repoId } = useParams<{ repoId: string }>();
  const { data: repo } = useRepo(repoId);
  const [messages, setMessages] = useState<ChatMessageModel[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const patch = (id: string, fn: (m: ChatMessageModel) => ChatMessageModel) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));

  async function send(query: string) {
    if (!repoId || streaming || !query.trim()) return;
    const userMessage: ChatMessageModel = {
      id: nextId(),
      role: "user",
      content: query.trim(),
      citations: [],
      grounding: null,
      error: null,
      streaming: false,
    };
    const assistantId = nextId();
    const assistant: ChatMessageModel = {
      id: assistantId,
      role: "assistant",
      content: "",
      citations: [],
      grounding: null,
      error: null,
      streaming: true,
    };
    setMessages((prev) => [...prev, userMessage, assistant]);
    setInput("");
    setStreaming(true);

    try {
      await streamSSE(endpoints.ask(repoId), {
        method: "POST",
        body: { query: query.trim() },
        onEvent: ({ event, data }) => {
          if (event === "token") {
            patch(assistantId, (m) => ({ ...m, content: m.content + (data as { text: string }).text }));
          } else if (event === "citation") {
            patch(assistantId, (m) => ({ ...m, citations: [...m.citations, data as Citation] }));
          } else if (event === "grounding") {
            patch(assistantId, (m) => ({ ...m, grounding: data as Grounding }));
          } else if (event === "error") {
            patch(assistantId, (m) => ({
              ...m,
              error: (data as { message: string }).message,
              streaming: false,
            }));
          } else if (event === "done") {
            patch(assistantId, (m) => ({ ...m, streaming: false }));
          }
        },
      });
    } catch (err) {
      patch(assistantId, (m) => ({
        ...m,
        error: err instanceof Error ? err.message : "Request failed",
        streaming: false,
      }));
    } finally {
      patch(assistantId, (m) => ({ ...m, streaming: false }));
      setStreaming(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col px-6">
      <div className="flex-1 space-y-6 overflow-y-auto py-8">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center pt-24 text-center">
            <MessageSquare size={40} className="text-accent-purple" strokeWidth={1.25} />
            <h2 className="mt-4 text-xl font-medium text-text-primary">
              Ask anything about {repo?.name ?? "this repo"}
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              Every answer is grounded in the actual code, with file·line citations.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-border-default bg-elevated px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-accent-purple hover:text-text-primary"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <ChatMessage key={m.id} message={m} />)
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="sticky bottom-0 mb-6 mt-2 flex items-end gap-2 rounded-xl border border-border-default bg-elevated p-2"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          rows={1}
          placeholder="Ask how something works…"
          disabled={streaming}
          className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={streaming || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-grad text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          <SendHorizontal size={16} />
        </button>
      </form>
    </div>
  );
}
