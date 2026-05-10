const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface ResearchRequest {
  topic: string;
}

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

export async function streamResearch(
  payload: ResearchRequest,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${BASE_URL}/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(text || `Request failed (${resp.status})`);
  }

  const reader = resp.body?.getReader();
  if (!reader) throw new Error("Streaming not supported");

  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);

      if (raw.startsWith("data:")) {
        const jsonStr = raw.slice(5).trim();
        if (jsonStr) {
          try {
            const event = JSON.parse(jsonStr) as SSEEvent;
            onEvent(event);
            if (event.type === "error" || event.type === "done") return;
          } catch {
            // skip malformed events
          }
        }
      }
      boundary = buffer.indexOf("\n\n");
    }

    if (done) break;
  }
}
