import { API_BASE } from "./api";
import type { PlanningResult, SpanMetrics } from "./types";

export interface PlanStreamHandlers {
  onRunStarted?: () => void;
  onStepStarted?: (name: string) => void;
  onStepFinished?: (name: string) => void;
  onSpan?: (span: SpanMetrics) => void;
  onSnapshot?: (result: PlanningResult) => void;
  onRunFinished?: () => void;
  onError?: (message: string) => void;
}

interface AgUiEvent {
  type: string;
  stepName?: string;
  name?: string;
  value?: unknown;
  snapshot?: unknown;
  message?: string;
}

function dispatch(event: AgUiEvent, handlers: PlanStreamHandlers): void {
  switch (event.type) {
    case "RUN_STARTED":
      handlers.onRunStarted?.();
      break;
    case "STEP_STARTED":
      if (event.stepName) handlers.onStepStarted?.(event.stepName);
      break;
    case "STEP_FINISHED":
      if (event.stepName) handlers.onStepFinished?.(event.stepName);
      break;
    case "CUSTOM":
      if (event.name === "trace.span" && event.value) {
        handlers.onSpan?.(event.value as SpanMetrics);
      }
      break;
    case "STATE_SNAPSHOT":
      if (event.snapshot) handlers.onSnapshot?.(event.snapshot as PlanningResult);
      break;
    case "RUN_FINISHED":
      handlers.onRunFinished?.();
      break;
    case "RUN_ERROR":
      handlers.onError?.(event.message ?? "The planning run failed.");
      break;
  }
}

/** Stream a planning run, invoking handlers as AG-UI events arrive. */
export async function streamPlan(
  request: { query: string; travelerId?: string | null; sessionId: string },
  handlers: PlanStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/plan/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      query: request.query,
      traveler_id: request.travelerId ?? null,
      session_id: request.sessionId,
    }),
    signal,
  });
  if (!response.ok || !response.body) {
    handlers.onError?.(`Request failed (${response.status}).`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separator = buffer.indexOf("\n\n");
    while (separator !== -1) {
      const frame = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      const dataLine = frame
        .split("\n")
        .find((line) => line.startsWith("data:"));
      if (dataLine) {
        const payload = dataLine.slice("data:".length).trim();
        try {
          dispatch(JSON.parse(payload) as AgUiEvent, handlers);
        } catch {
          // Ignore malformed frames; the stream continues.
        }
      }
      separator = buffer.indexOf("\n\n");
    }
  }
}
