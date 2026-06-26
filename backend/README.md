# Agentic Travel — Backend

Python service hosting the agent orchestration, tool/data services, and API gateway.

## Development

```bash
uv sync --extra dev      # create the virtual environment and install dependencies
uv run pytest            # run the test suite
uv run ruff check .      # lint
uv run mypy              # type-check
```

## Running the API

```bash
uv run uvicorn agentic_travel.api.app:app --reload --port 8000
```

The API runs with **no credentials** using a deterministic heuristic planner, so
the demo works out of the box. Set the Gemini variables in a `.env` (see
[`../.env.example`](../.env.example)) to switch on live model reasoning.

Endpoints: `GET /health`, `GET /personas`, `POST /plan`, and `POST /plan/stream`
(AG-UI Server-Sent Events streaming the live agent trace).

The MCP tool servers can each be run standalone, e.g.:

```bash
uv run python -m agentic_travel.mcp_servers.flights --http
```
