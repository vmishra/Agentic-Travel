# Agentic Travel — Backend

Python service hosting the agent orchestration, tool/data services, and API gateway.

## Development

```bash
uv sync --extra dev      # create the virtual environment and install dependencies
uv run pytest            # run the test suite
uv run ruff check .      # lint
uv run mypy              # type-check
```
