"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ArchitectureView } from "@/components/ArchitectureView";
import { ItineraryView } from "@/components/ItineraryView";
import { TraceView } from "@/components/TraceView";
import { fetchArchitecture, fetchHealth, fetchPersonas, type Health } from "@/lib/api";
import { streamPlan } from "@/lib/agui";
import { formatCost, formatMoney, formatMs } from "@/lib/format";
import type {
  Architecture,
  PlanningResult,
  SpanMetrics,
  TravelerProfile,
} from "@/lib/types";

interface Message {
  role: "user" | "agent" | "system";
  text: string;
}

type View = "itinerary" | "trace";

const SUGGESTIONS = [
  "3 nights in Goa for a couple",
  "5 days in Tokyo from 10 September",
  "A week in Paris",
  "San Francisco for 4 days",
];

export default function Page() {
  const [personas, setPersonas] = useState<TravelerProfile[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [architecture, setArchitecture] = useState<Architecture | null>(null);

  const [messages, setMessages] = useState<Message[]>([
    { role: "system", text: "Pick a traveler, then describe the trip you want." },
  ]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);

  const [spans, setSpans] = useState<SpanMetrics[]>([]);
  const [activeSteps, setActiveSteps] = useState<string[]>([]);
  const [result, setResult] = useState<PlanningResult | null>(null);
  const [view, setView] = useState<View>("itinerary");
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const threadRef = useRef<HTMLDivElement>(null);
  const startRef = useRef(0);
  const sessionRef = useRef("");

  const selectPersona = useCallback((id: string) => {
    setPersonaId(id);
    sessionRef.current = ""; // a new traveler starts a fresh conversation
    setMessages([{ role: "system", text: "New trip — describe where and when." }]);
    setResult(null);
    setSpans([]);
    setActiveSteps([]);
  }, []);

  useEffect(() => {
    fetchPersonas()
      .then((p) => {
        setPersonas(p);
        setPersonaId((current) => current ?? p[0]?.traveler_id ?? null);
      })
      .catch(() => undefined);
    fetchHealth()
      .then(setHealth)
      .catch(() => undefined);
    fetchArchitecture()
      .then(setArchitecture)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setElapsedMs(performance.now() - startRef.current), 80);
    return () => clearInterval(id);
  }, [running]);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const telemetry = useMemo(() => {
    let tokens = 0;
    let cost = 0;
    for (const span of spans) {
      if (span.tokens) tokens += span.tokens;
      if (span.cost_usd) cost += Number(span.cost_usd);
    }
    return { tokens, cost, steps: spans.length };
  }, [spans]);

  const submit = useCallback(async () => {
    const query = input.trim();
    if (!query || running) return;
    setMessages((m) => [...m, { role: "user", text: query }]);
    setInput("");
    setSpans([]);
    setActiveSteps([]);
    setResult(null);
    setSelectedSpanId(null);
    setView("trace");
    setRunning(true);
    startRef.current = performance.now();
    setElapsedMs(0);
    if (!sessionRef.current) sessionRef.current = crypto.randomUUID();

    try {
      await streamPlan(
        { query, travelerId: personaId, sessionId: sessionRef.current },
        {
          onStepStarted: (name) => setActiveSteps((s) => [...s, name]),
          onSpan: (span) => setSpans((s) => [...s, span]),
          onStepFinished: (name) =>
            setActiveSteps((s) => {
              const idx = s.indexOf(name);
              return idx === -1 ? s : [...s.slice(0, idx), ...s.slice(idx + 1)];
            }),
          onSnapshot: (res) => {
            setResult(res);
            setView("itinerary");
            setMessages((m) => [...m, { role: "agent", text: summarize(res) }]);
          },
          onError: (msg) => {
            setMessages((m) => [...m, { role: "system", text: msg }]);
          },
        },
      );
    } catch {
      setMessages((m) => [
        ...m,
        { role: "system", text: "Could not reach the planner. Is the API running on :8000?" },
      ]);
    } finally {
      setRunning(false);
      setActiveSteps([]);
    }
  }, [input, personaId, running]);

  return (
    <div className="shell">
      <header className="header">
        <div className="brand">
          <span className="brand__mark">
            Agentic<span>·</span>Travel
          </span>
          <span className="brand__tag">a private travel concierge</span>
        </div>
        <div className="header__spacer" />
        <div className="telemetry">
          <div className="metric">
            <span className="metric__value">{formatMs(running ? elapsedMs : lastDuration(spans))}</span>
            <span className="metric__label">latency</span>
          </div>
          <div className="metric">
            <span className="metric__value metric__value--aqua">{telemetry.tokens}</span>
            <span className="metric__label">tokens</span>
          </div>
          <div className="metric">
            <span className="metric__value metric__value--amber">
              {telemetry.cost > 0 ? formatCost(telemetry.cost) : "$0"}
            </span>
            <span className="metric__label">est. cost</span>
          </div>
          <div className="metric">
            <span className="metric__value">{telemetry.steps}</span>
            <span className="metric__label">steps</span>
          </div>
          {health && (
            <span className={`pill ${health.live_models ? "pill--live" : "pill--offline"}`}>
              {health.live_models ? "Gemini live" : "heuristic mode"}
            </span>
          )}
        </div>
      </header>

      <div className="main">
        <section className="pane pane--chat">
          <div className="persona-bar">
            {personas.map((p) => (
              <button
                key={p.traveler_id}
                className={`persona ${p.traveler_id === personaId ? "persona--active" : ""}`}
                onClick={() => selectPersona(p.traveler_id)}
              >
                <span className="persona__name">{p.display_name}</span>
                <span className="persona__meta">
                  {p.budget_tier} · {p.food_preference}
                </span>
              </button>
            ))}
          </div>

          <div className="thread" ref={threadRef}>
            {messages.map((m, i) => (
              <div key={i} className={`msg msg--${m.role}`}>
                {m.text}
              </div>
            ))}
            {running && <div className="msg msg--system">planning…</div>}
          </div>

          {!result && !running && (
            <div className="suggests">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => setInput(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="composer">
            <textarea
              rows={2}
              placeholder="e.g. Plan 3 nights in Goa for a couple, love beaches and heritage"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit();
                }
              }}
            />
            <button className="btn" onClick={() => void submit()} disabled={running || !input.trim()}>
              Plan
            </button>
          </div>
        </section>

        <section className="pane">
          <div className="canvas">
            <div className="canvas__tabs">
              <button
                className={`tab ${view === "itinerary" ? "tab--active" : ""}`}
                onClick={() => setView("itinerary")}
              >
                Itinerary
              </button>
              <button
                className={`tab ${view === "trace" ? "tab--active" : ""}`}
                onClick={() => setView("trace")}
              >
                Technical
                <span className="tab__count">{spans.length}</span>
              </button>
            </div>
            <div className="canvas__body grain">
              {view === "itinerary" ? (
                result ? (
                  <ItineraryView result={result} />
                ) : (
                  <div className="empty">
                    <div className="empty__glyph">Where to?</div>
                    <p>
                      Describe the trip you have in mind and a complete, bookable
                      itinerary will be composed here — flights, stays, a day-by-day
                      plan, and the details that matter.
                      <br />
                      <br />
                      Covering Goa, Mumbai, Dubai, Colombo, Singapore, Tokyo, Paris,
                      London, New York &amp; San Francisco.
                    </p>
                  </div>
                )
              ) : (
                <div className="technical">
                  {architecture && (
                    <ArchitectureView
                      architecture={architecture}
                      activeSteps={activeSteps}
                    />
                  )}
                  <div className="technical__trace">
                    <div className="technical__tracehead">
                      <span className="arch__kicker">The run trace</span>
                      <p className="arch__lead">
                        Each step from the most recent plan, with its latency, tokens,
                        and cost.
                      </p>
                    </div>
                    <TraceView
                      spans={spans}
                      activeSteps={activeSteps}
                      selectedId={selectedSpanId}
                      onSelect={setSelectedSpanId}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function lastDuration(spans: SpanMetrics[]): number | null {
  const root = spans.find((s) => s.parent_id === null);
  return root?.duration_ms ?? null;
}

function summarize(result: PlanningResult): string {
  if (result.itinerary) {
    const it = result.itinerary;
    const valid = result.validation.issues.every((i) => i.severity !== "error");
    return `Planned “${it.title}” — ${it.days.length} day${
      it.days.length > 1 ? "s" : ""
    }, est. ${formatMoney(it.estimated_total)}.${valid ? "" : " Some constraints need attention."}`;
  }
  if (result.brief.clarifications_needed.length > 0) {
    return `To plan this well, I need: ${result.brief.clarifications_needed.join(", ")}.`;
  }
  return "I couldn't match that to a destination I know yet. Try Goa, Mumbai, Colombo, or Dubai.";
}
