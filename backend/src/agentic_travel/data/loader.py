"""Loaders for packaged seed datasets."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from agentic_travel.graph.store import InMemoryGraphStore, load_graph_data


def default_graph_data_path() -> Path:
    """Return the filesystem path to the packaged graph seed dataset."""
    resource = resources.files("agentic_travel.data") / "graph_seed.json"
    return Path(str(resource))


def load_default_graph_store() -> InMemoryGraphStore:
    """Load the packaged seed graph into an in-memory store."""
    data = load_graph_data(default_graph_data_path())
    return InMemoryGraphStore(data)
