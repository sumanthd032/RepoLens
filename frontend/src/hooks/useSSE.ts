// Server-Sent-Events over fetch. EventSource only supports GET without a body, but /ask is a
// POST with a JSON payload — so we stream the response body ourselves and parse SSE frames. The
// same helper drives both the ask stream (POST) and the index/drift progress streams (GET).

import { useEffect, useRef } from "react";

export interface SSEFrame {
  event: string;
  data: unknown;
}

export interface StreamOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  onEvent: (frame: SSEFrame) => void;
}

function parseFrame(raw: string): SSEFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return { event, data: dataLines.join("\n") };
  }
}

/** Stream an SSE endpoint, invoking `onEvent` for every frame until the stream closes. */
export async function streamSSE(url: string, options: StreamOptions): Promise<void> {
  const { method = "GET", body, signal, onEvent } = options;
  const response = await fetch(url, {
    method,
    signal,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(detail || `Stream failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    // Normalise CRLF: sse-starlette ends frames with \r\n\r\n, but the frame/line splitting
    // below keys off \n, and "\r\n\r\n" contains no "\n\n" substring — so without this the
    // boundary is never found and no frame is ever dispatched. Stripping \r is safe: raw CR
    // bytes only appear as SSE line endings, never inside the JSON data payload.
    buffer += decoder.decode(value, { stream: true }).replace(/\r/g, "");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = parseFrame(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      if (frame) onEvent(frame);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

/** Subscribe to a GET SSE endpoint for the component's lifetime (e.g. indexing progress). */
export function useEventStream(
  url: string | null,
  onEvent: (frame: SSEFrame) => void,
  enabled = true,
): void {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!url || !enabled) return;
    const controller = new AbortController();
    streamSSE(url, {
      signal: controller.signal,
      onEvent: (frame) => handler.current(frame),
    }).catch((error) => {
      if (!controller.signal.aborted) console.error("SSE stream error:", error);
    });
    return () => controller.abort();
  }, [url, enabled]);
}
