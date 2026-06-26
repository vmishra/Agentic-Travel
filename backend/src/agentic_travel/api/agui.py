"""Bridge the coordinator's span stream to AG-UI Server-Sent Events.

A planning run executes in a worker thread; its tracer pushes span lifecycle
events onto a queue, which this module translates into AG-UI events (step
lifecycle plus a custom ``trace.span`` event carrying per-step metrics) and
finally a state snapshot of the result.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from ag_ui.core import (
    CustomEvent,
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
)
from ag_ui.encoder import EventEncoder

from agentic_travel.agents.coordinator import PlanningResult
from agentic_travel.agents.models import ConversationState
from agentic_travel.api.dependencies import PlannerFactory
from agentic_travel.observability.events import SpanEvent
from agentic_travel.observability.span import Span
from agentic_travel.observability.tracer import Tracer


def span_payload(span: Span) -> dict[str, object]:
    """Serialize a span into the metrics the technical view renders."""
    return {
        "span_id": span.span_id,
        "parent_id": span.parent_id,
        "name": span.name,
        "kind": span.kind.value,
        "status": span.status.value,
        "duration_ms": span.duration_ms,
        "model": span.model,
        "tokens": span.usage.total_tokens if span.usage else None,
        "cost_usd": str(span.cost_usd) if span.cost_usd is not None else None,
    }


def _result_snapshot(result: PlanningResult) -> dict[str, object]:
    return result.model_dump(mode="json")


async def plan_event_stream(
    factory: PlannerFactory,
    *,
    query: str,
    traveler_id: str | None,
    state: ConversationState | None,
    thread_id: str,
    run_id: str,
    persist: Callable[[ConversationState], None],
) -> AsyncIterator[str]:
    """Yield encoded AG-UI SSE frames for a planning run."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
    tracer = Tracer()

    def _enqueue(event: SpanEvent) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, ("span", event))

    tracer.add_listener(_enqueue)
    coordinator = factory.build(tracer)
    encoder = EventEncoder()

    async def run() -> None:
        try:
            result = await asyncio.to_thread(
                coordinator.plan_itinerary, query, traveler_id=traveler_id, state=state
            )
            loop.call_soon_threadsafe(queue.put_nowait, ("result", result))
        except Exception as exc:  # noqa: BLE001 — surfaced to the client as RUN_ERROR
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))

    task = asyncio.create_task(run())
    yield encoder.encode(
        RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id)
    )
    try:
        while True:
            kind, payload = await queue.get()
            if kind == "span":
                for frame in _span_frames(encoder, payload):
                    yield frame
            elif kind == "result":
                assert isinstance(payload, PlanningResult)
                persist(payload.conversation)
                yield encoder.encode(
                    StateSnapshotEvent(
                        type=EventType.STATE_SNAPSHOT, snapshot=_result_snapshot(payload)
                    )
                )
                yield encoder.encode(
                    RunFinishedEvent(
                        type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id
                    )
                )
                return
            elif kind == "error":
                yield encoder.encode(
                    RunErrorEvent(type=EventType.RUN_ERROR, message=str(payload))
                )
                return
    finally:
        await task


def _span_frames(encoder: EventEncoder, event: object) -> list[str]:
    if not isinstance(event, SpanEvent):
        return []
    span = event.span
    if event.phase == "started":
        return [
            encoder.encode(
                StepStartedEvent(type=EventType.STEP_STARTED, step_name=span.name)
            )
        ]
    return [
        encoder.encode(
            CustomEvent(type=EventType.CUSTOM, name="trace.span", value=span_payload(span))
        ),
        encoder.encode(
            StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=span.name)
        ),
    ]
