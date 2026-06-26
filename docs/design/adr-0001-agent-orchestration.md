# ADR-0001: Agent orchestration approach

**Status:** Accepted · **Date:** 2026-06-26

## Context

The planner is a multi-agent system: intent classification, query enrichment,
personalization, parallel specialist retrieval (POI, flights, hotels, visa,
weather), itinerary synthesis, and a validation/critique loop. We want it to be
(1) efficient and schema-constrained in its model usage, (2) precisely
observable — every step metered for the live trace view, (3) deterministically
testable without network access, and (4) aligned with Google's agent stack
(ADK, A2A, MCP, AG-UI) for interoperability and narrative.

## Decision

Use a **typed orchestration core** built on a thin `LlmClient` seam for the
reasoning steps, and expose the system through Google's stack at its boundaries.

- **Reasoning core.** Each agent is a small, single-responsibility unit that
  calls the model through `LlmClient` with **structured (schema-constrained)
  output**. This gives direct control over prompts, exact token/cost metering
  via the tracer, and deterministic tests through `FakeLlmClient`.
- **Tools and data as MCP.** Flights, hotels, visa, weather, POI graph, and
  memory are exposed as MCP servers, so any can be swapped for a live provider
  and agents can consume them over the standard protocol.
- **Boundary integration with ADK / A2A / AG-UI.** The assembled planner is
  exposed as an ADK-compatible agent and over A2A for agent-to-agent use, and it
  streams progress to the frontend via AG-UI events. These live at the system
  boundary rather than wrapping every internal reasoning step.

## Rationale

Forcing every micro-step through a framework's tool-calling loop would obscure
the precise, per-call tracing the product's technical view depends on, make
structured outputs harder to constrain, and couple unit tests to a model runner.
Keeping a clean reasoning core while speaking ADK/A2A/MCP/AG-UI at the edges
gives both control and interoperability — and reads clearly to anyone adopting
the blueprint.

## Consequences

- The core is fully unit-testable offline; live model calls are an
  implementation of one seam (`GeminiClient`).
- Observability is first-class: spans wrap agents, model calls, and tool calls.
- The Google-stack integration is additive and isolated, so it can evolve with
  those fast-moving libraries without destabilizing the core.
