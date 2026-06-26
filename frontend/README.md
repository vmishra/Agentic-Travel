# Agentic Travel — Frontend

A Next.js interface with a split **conversation + live canvas**: a chat thread on
the left, and on the right a canvas that toggles between the **itinerary** (a
bookable, day-by-day document) and the **technical view** — a live trace of the
agents at work, with per-step latency, tokens, and cost.

It consumes the API's AG-UI Server-Sent Event stream, so the trace populates as
the plan is built.

## Development

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # production build + type-check
npm run typecheck
```

Point it at the API with `NEXT_PUBLIC_API_BASE` (see [`.env.example`](.env.example));
it defaults to `http://localhost:8000`. The API runs credential-free by default,
so the full experience works without any keys.

## Design

"Departure at dusk, instrumented" — a midnight-indigo console with runway-amber
and telemetry-aqua accents, Space Grotesk display type, and IBM Plex Mono for
flight numbers, fares, and agent metrics. The live agent trace is the signature.
