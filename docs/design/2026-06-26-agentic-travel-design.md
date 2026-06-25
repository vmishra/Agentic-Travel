# Agentic Travel — System Design

**Status:** Draft for review · **Date:** 2026-06-26 · **Owner:** Vikas Mishra

A reference-grade, multi-agent AI travel planner that produces **bookable** itineraries —
aware of flights, hotels, visas, points of interest, weather, budget, and traveler
personalization — built on Google's agent stack (ADK, A2A, MCP, AG-UI) with Gemini.

This document is the authoritative design. It is intended to be inspected and adopted by
travel companies and startups as a blueprint for how agentic systems should be built in 2026.

---

## 1. Goals & non-goals

### Goals
- Produce **bookable, constraint-satisfying itineraries**, not generic LLM travel prose.
- Three conversational intents: **inquiry/inspiration**, **itinerary building** (hero flow),
  and **post-travel modification**.
- **Grounded** in concrete inventory: real-looking flights, hotels, POIs, visa rules.
- **Personalized** via short-term (session) and long-term (profile) memory.
- **Efficient**: minimal, parallelized LLM/tool calls; metered tokens/cost/latency.
- **Observable**: a live, interactive agent-trace view as a first-class product surface.
- **World-class UX**: split conversational + live canvas, voice, maps, generated imagery.
- **Pluggable**: clean interfaces so any of the mock services can be swapped for a real one.

### Non-goals (v1)
- Real booking transactions or payments.
- Real flight/hotel inventory (mocked, but realistic and behind production-shaped interfaces).
- Multi-tenant auth/accounts (synthetic personas only).

---

## 2. Architecture overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Next.js)                            │
│   Chat thread  │  Live canvas (itinerary · map · cards · imagery)          │
│                │  Technical view (live agent trace)                        │
└───────────────────────────▲───────────────────────────────────────────────┘
                            │ AG-UI event stream (SSE/WebSocket)
┌───────────────────────────┴───────────────────────────────────────────────┐
│                          API Gateway (FastAPI)                              │
│            session mgmt · AG-UI bridge · voice (Gemini Live) relay          │
└───────────────────────────▲───────────────────────────────────────────────┘
                            │
┌───────────────────────────┴───────────────────────────────────────────────┐
│                     Orchestration (Google ADK)                              │
│  Root Coordinator                                                           │
│   ├─ Intent Agent          (fast model)                                     │
│   ├─ Enrichment Agent       (fast model)                                    │
│   ├─ Memory/Personalization (tool-backed)                                   │
│   ├─ ParallelAgent ── POI · Flights · Hotels · Visa · Weather               │
│   ├─ Itinerary Synthesizer  (reasoning model, schema-constrained)           │
│   ├─ Critic / Guardrail      (LoopAgent — feasibility + grounding checks)   │
│   └─ Media Agent             (image generation)                             │
│                                                                             │
│  Reasoning agents collaborate via A2A.                                      │
└───────────────────────────▲───────────────────────────────────────────────┘
                            │ MCP (tools & data)
┌───────────────────────────┴───────────────────────────────────────────────┐
│   MCP servers:  FlightMCP · HotelMCP · POIGraphMCP · WeatherMCP ·           │
│                 VisaMCP · MemoryMCP · MapsMCP                               │
│   Data layer:   graph-shaped POI store (→ Spanner Graph later),             │
│                 flight/hotel/visa datasets, persona memory store            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Layer responsibilities & the stack narrative**
- **ADK** — agent definitions, orchestration primitives (`Sequential`/`Parallel`/`Loop`).
- **A2A** — protocol for reasoning agents to collaborate (agent cards, typed messages);
  surfaced live in the technical view.
- **MCP** — uniform interface for *tools and data* (the mock services are MCP servers, so a
  consumer can replace any one with a real provider without touching agent code).
- **AG-UI** — streams agent lifecycle/state events to the frontend, driving both the canvas
  and the trace view.
- **Gemini** — reasoning; **image model** — destination imagery; **Gemini Live** — voice;
  **Maps + grounding** — grounded geographic facts.

---

## 3. Agent topology (hero flow: itinerary building)

| Agent | Model tier | Responsibility | Key I/O |
|---|---|---|---|
| Root Coordinator | — | Owns session, routes by intent, sequences sub-agents | conversation ↔ structured plan |
| Intent | fast | Classify `{inquiry, itinerary, post_travel}`; extract slots | text → `IntentResult` |
| Enrichment | fast | Rewrite/expand query, fill gaps from memory, ask clarifying Qs only when a *critical* slot is missing | slots + memory → `EnrichedBrief` |
| Memory/Personalization | tool | Fetch long-term profile + short-term session memory | persona id → `TravelerProfile` |
| POI/Destination | fast | Graph traversal; select & sequence POIs by geography, opening hours, travel time; maps grounding | brief → `POIPlan` |
| Flights | fast | Query FlightMCP; pick tiered options consistent with budget | brief → `FlightOptions` |
| Hotels | fast | Query HotelMCP; pick by location/budget/prefs | brief → `HotelOptions` |
| Visa & Docs | fast | Resolve visa/entry requirements for the traveler's passport | brief → `VisaAssessment` |
| Weather | fast | Seasonality + forecast caveats | brief → `WeatherBrief` |
| Itinerary Synthesizer | reasoning | Compose day-by-day bookable plan integrating all inputs | all of the above → `Itinerary` |
| Critic/Guardrail | reasoning | Validate feasibility, budget, grounding; trigger re-plan | `Itinerary` → `ValidationReport` |
| Media | image | Generate hero imagery for itinerary/cards | itinerary → image refs |

**Parallelism.** Once destination + dates + travelers are fixed, POI/Flights/Hotels/Visa/Weather
run concurrently (ADK `ParallelAgent`). The Synthesizer makes a **single** reasoning call over
the merged context. The Critic runs a bounded `LoopAgent` (max N iterations) and only re-invokes
the specific failing specialist, not the whole fan-out.

**Other intents (layered after the hero flow).**
- *Inquiry*: Intent → (Memory) → POI/Maps grounding → grounded answer + inspiration imagery.
- *Post-travel*: Intent → load existing itinerary → targeted specialist(s) → diff/modify → re-validate.

---

## 4. Efficiency & cost discipline

- **Model tiering** — fast model for intent/enrichment/specialists; reasoning model only for
  synthesis and critique.
- **Parallel fan-out** — independent specialists run concurrently.
- **Schema-constrained output** — structured (typed) generation so outputs are consumed
  directly, never re-parsed or re-prompted.
- **Scoped context** — each sub-agent receives only the slice of state it needs, not the whole
  transcript; keeps token counts low and behavior predictable.
- **Caching** — prompt caching for stable system instructions; memoized graph/memory/visa lookups.
- **Single-synthesis principle** — heavy reasoning happens once; the Critic loop is targeted.
- **Full metering** — every model and tool call records `{tokens_in, tokens_out, cost, latency}`,
  computed from a configurable pricing table and streamed to the trace view.

---

## 5. Grounding, guardrails & safety

- **Entity grounding** — the Critic cross-checks **every** referenced entity (POI id, flight
  number, hotel id) against the data services; unmatched entities are rejected and regenerated.
  The model may never invent inventory.
- **Deterministic feasibility checks** (non-LLM): no overlapping activity times; daily pace
  within bounds; inter-POI travel time respected; total cost within budget; opening hours honored.
- **Visa/advisory surfacing** — entry requirements always shown, never silently assumed.
- **Synthetic data only** — no real PII; personas are fictional.
- **Prompt-injection mitigation** — grounded web/maps content is treated as untrusted and
  sandboxed from instruction context.
- **Transparency** — confidence and source attributions surfaced in the UI.

---

## 6. Data layer

### 6.1 POI graph
Graph model designed to map cleanly onto **Spanner Graph** later:
- **Nodes:** `Region`, `Country`, `City`, `POI` (with type, geo, opening/closing hours, typical
  visit duration, ticket price, rating, tags), plus inter-city POIs.
- **Edges:** `CONTAINS` (Region→Country→City→POI), `NEAR(distance)`, `CONNECTED_BY(mode, time)`.
- **Storage:** graph-shaped flat files (JSON) now, behind a `GraphStore` interface with
  traversal methods; a future `SpannerGraphStore` implements the same interface.

### 6.2 Flights / hotels / visa
- **Flights** — realistic carriers, plausible flight numbers, schedules, durations consistent
  with real routes, and fare tiers (saver/standard/flex) across carriers.
- **Hotels** — recognizable chains, room types, price tiers, availability windows, ratings and
  representative reviews, location relative to POIs.
- **Visa** — entry requirements keyed by destination country for the traveler's passport
  (visa-free / visa-on-arrival / e-visa / embassy), with processing time and cost.

All exposed via MCP servers with production-shaped request/response schemas so each can be
swapped for a live provider.

### 6.3 Memory / personalization
2–3+ rich personas with **long-term** memory (food preferences, budget tier, brand/loyalty
affinity, past destinations, travel style, companions) and **short-term** session memory
(current trip context). Served by `MemoryMCP`; switchable in the demo to show personalization
changing outputs.

---

## 7. Frontend

- **Stack:** Next.js + TypeScript, a deliberate custom design system (not templated defaults).
- **Layout:** split **chat thread** + **live canvas** (itinerary timeline, day cards,
  flight/hotel option cards, Google map, generated hero imagery) that updates as agents work.
- **Technical view (toggle):** live, animated agent graph; A2A messages shown as flowing edges;
  per-node tokens/cost/latency; **clickable nodes** open a panel with prompt/output/metrics —
  these are the demo's talking-point anchors; **replayable** via a timeline scrubber.
- **Voice:** Gemini Live (mic in / audio out) with graceful text fallback.
- **Iterative refinement:** the user can adjust constraints or request changes; re-planning is
  incremental (only affected specialists re-run).

---

## 8. Configuration & secrets

- **All model IDs are environment-configurable** (`GEMINI_MODEL_PLANNER`, `GEMINI_MODEL_FAST`,
  `GEMINI_MODEL_LIVE`, `GEMINI_IMAGE_MODEL`) and **validated against the active key at startup**.
- Credentials via `.env` (never committed); `.env.example` documents every variable with
  placeholders. Supports Gemini API key, Google Maps Platform key, and Vertex AI/GCP.
- **Graceful degradation:** a missing/limited key disables only the dependent feature (e.g.
  static map fallback, skipped imagery) — the core flow always works.

---

## 9. Repository layout

```
agentic-travel/
├─ backend/
│  ├─ agents/            # ADK agent definitions
│  ├─ orchestration/     # root coordinator, A2A wiring
│  ├─ mcp_servers/       # flight, hotel, poi_graph, weather, visa, memory, maps
│  ├─ observability/     # span collection, cost model, event stream
│  ├─ data/              # mock datasets (graph, flights, hotels, visa, personas)
│  ├─ api/               # FastAPI gateway + AG-UI bridge + voice relay
│  └─ tests/
├─ frontend/
│  ├─ app/               # Next.js routes
│  ├─ components/        # chat, canvas, itinerary, map, trace-view
│  └─ lib/               # AG-UI client, types
├─ docs/
│  └─ design/            # this document and ADRs
├─ .env.example
└─ README.md
```

---

## 10. Build sequence

1. **Foundations** — repo scaffolding, config, typed domain models, data schemas.
2. **Data layer** — POI graph + GraphStore, flight/hotel/visa datasets, personas.
3. **MCP servers** — expose each data service with production-shaped schemas.
4. **Observability core** — span model, cost table, event stream (built early so every
   subsequent agent is observable from day one).
5. **Agents + orchestration** — hero itinerary flow end-to-end with the critic loop.
6. **API + AG-UI bridge.**
7. **Frontend** — chat + canvas, then the technical trace view.
8. **Live capabilities** — maps, imagery, then voice (riskiest last), all with degradation.
9. **Inquiry & post-travel** intents.
10. **Hardening** — tests, docs, README, polish.

Each step is an independent, testable unit with a clear interface, delivered as small logical
commits.

---

## 11. Open items to confirm at implementation time
- Exact Gemini model IDs exposed by the provided key (resolved by startup validation).
- Final destination roster for the curated hero set (~15–20, expandable).
- Weather source: live weather API/MCP vs. seasonal dataset (degradation-friendly default).
