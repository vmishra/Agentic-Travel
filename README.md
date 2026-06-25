<div align="center">

# Agentic Travel

**A reference-grade, multi-agent AI travel planner that produces _bookable_ itineraries.**

Built on Google's agent stack — ADK · A2A · MCP · AG-UI — with Gemini.

</div>

---

Most "AI travel planners" hand you plausible prose. A real traveler needs something they can
actually book: flights that exist, hotels with rooms, a visa they qualify for, activities that
fit the day's geography and opening hours — all inside a budget, and tuned to who they are.

**Agentic Travel** is a blueprint for building that. It is a multi-agent system where
specialized agents collaborate to assemble a constraint-satisfying, grounded, personalized
itinerary, with a live, inspectable view of the agents at work.

> **Status:** under active development. See the [system design](docs/design/2026-06-26-agentic-travel-design.md)
> for the authoritative architecture.

## What it does

- **Three conversational intents** — inspiration/inquiry, itinerary building, and post-travel
  changes to an existing plan.
- **Bookable itineraries** — grounded in concrete flight, hotel, point-of-interest, and visa
  inventory, sequenced by travel time and opening hours.
- **Personalized** — short-term session memory and long-term traveler profiles shape every plan.
- **Observable** — a live, interactive agent-trace view shows which agents run, what flows
  between them, and the latency, tokens, and cost of every step.

## Architecture at a glance

| Layer | Role |
|---|---|
| **Frontend** (Next.js) | Split conversational + live itinerary canvas, plus a technical trace view |
| **API gateway** (FastAPI) | Session management and the AG-UI event bridge |
| **Orchestration** (ADK) | A coordinator with parallel specialist agents and a validation loop |
| **Agents** (A2A) | Intent, enrichment, POI, flights, hotels, visa, weather, synthesis, critic, media |
| **Tools & data** (MCP) | Flight, hotel, POI-graph, weather, visa, memory, and maps services |

The mock data services are realistic and sit behind production-shaped interfaces, so any one of
them can be swapped for a live provider without touching agent code.

Read the full design: [`docs/design/2026-06-26-agentic-travel-design.md`](docs/design/2026-06-26-agentic-travel-design.md).

## Getting started

Setup instructions will be added as the implementation lands. Configuration is environment-driven;
see [`.env.example`](.env.example) for every variable (no secrets are committed to this repository).

## License

Licensed under the [Apache License 2.0](LICENSE).
