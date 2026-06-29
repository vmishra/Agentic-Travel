"""A structured description of the live agent architecture.

The hero flow is a hierarchical coordinator that fans out to specialist data
agents, synthesizes a plan with a model, and tightens it in a bounded
critic-repair loop. This module renders that real topology as a tree the UI can
draw and animate: every node carries the runtime it embodies (ADK, A2A, MCP,
AG-UI, Gemini), the model it reasons with, and the runtime step-name prefixes
that light it up while a plan streams in over AG-UI.

The descriptions are honest about the blueprint: data services are mocked, but
they sit behind the same seams a production system would use — so the diagram
shows where each Google technology belongs, not a fiction that it is wired to a
live booking backend.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeKind = Literal["coordinator", "agent", "tool", "model", "critic"]


class ArchNode(BaseModel):
    """One component in the agent graph."""

    id: str
    label: str
    kind: NodeKind
    runtime: str
    model: str | None = None
    summary: str
    detail: str
    io: list[str] = Field(default_factory=list)
    step_match: list[str] = Field(default_factory=list)
    children: list[ArchNode] = Field(default_factory=list)


class ProtocolInfo(BaseModel):
    """A legend entry for one technology in the stack."""

    key: str
    name: str
    role: str


class Architecture(BaseModel):
    """The full architecture description served to the technical view."""

    root: ArchNode
    live: bool
    model_fast: str
    model_planner: str
    protocols: list[ProtocolInfo]


_PROTOCOLS = [
    ProtocolInfo(
        key="adk",
        name="Google ADK",
        role=(
            "Agent runtime — defines the coordinator and each specialist as an agent "
            "with a tool surface."
        ),
    ),
    ProtocolInfo(
        key="a2a",
        name="A2A",
        role=(
            "Agent-to-agent boundary — how the coordinator delegates to specialists and "
            "collects their results."
        ),
    ),
    ProtocolInfo(
        key="mcp",
        name="MCP",
        role="Model Context Protocol — the tool contract the data services are exposed through.",
    ),
    ProtocolInfo(
        key="agui",
        name="AG-UI",
        role=(
            "The event spine streaming run, step, and trace events to this interface as "
            "the plan is composed."
        ),
    ),
    ProtocolInfo(
        key="gemini",
        name="Gemini",
        role=(
            "The reasoning models — a fast model for understanding, a planner model for "
            "synthesis."
        ),
    ),
]


def _reasoning_runtime(live: bool) -> str:
    return "Google ADK · Gemini" if live else "Google ADK · heuristic"


def describe_architecture(
    *,
    live: bool,
    model_fast: str,
    model_planner: str,
) -> Architecture:
    """Build the architecture tree for the currently wired reasoning path."""
    fast = model_fast if live else "heuristic"
    planner = model_planner if live else "heuristic"

    intent = ArchNode(
        id="intent",
        label="Intent",
        kind="agent",
        runtime=_reasoning_runtime(live),
        model=fast,
        summary="Classifies the request: inquiry, itinerary build, or post-travel.",
        detail=(
            "An ADK agent on the fast Gemini model. It routes the conversation to the "
            "right flow so the heavy planner only runs when a bookable trip is actually "
            "being requested — the first lever for efficient model use."
        ),
        io=["in · the traveller's message", "out · intent label"],
        step_match=["intent"],
    )
    enrichment = ArchNode(
        id="enrichment",
        label="Enrichment",
        kind="agent",
        runtime=_reasoning_runtime(live),
        model=fast,
        summary="Extracts trip slots — destination, dates, party, budget, interests.",
        detail=(
            "Pulls structured slots out of free text on the fast model, then folds them "
            "into conversation state that accumulates across turns. Missing essentials "
            "become clarifying questions rather than guesses — an anti-hallucination guard."
        ),
        io=["in · message + prior state", "out · merged trip slots"],
        step_match=["enrichment"],
    )
    resolver = ArchNode(
        id="resolver",
        label="Destination resolver",
        kind="tool",
        runtime="Knowledge graph",
        summary="Maps free-text places onto known cities in the graph.",
        detail=(
            "A deterministic lookup over the destination knowledge graph. It only resolves "
            "cities the system actually covers, so the planner can never invent a place it "
            "has no data for."
        ),
        io=["in · destination text", "out · resolved city ids"],
    )

    specialists = ArchNode(
        id="specialists",
        label="Specialists",
        kind="agent",
        runtime="A2A · MCP",
        summary="Fans out to gather every bookable option in parallel.",
        detail=(
            "The coordinator delegates to a specialist data layer across an A2A boundary. "
            "Each source below is reached through an MCP tool contract; in this blueprint "
            "the datasets are mocked, but the seam is exactly where a live provider would "
            "connect."
        ),
        io=["in · the trip brief", "out · flights, stays, visas, weather, candidate places"],
        step_match=["specialists"],
        children=[
            ArchNode(
                id="flights",
                label="Flights",
                kind="tool",
                runtime="MCP tool",
                summary="Hash-seeded flight offers, including connections via hubs.",
                detail=(
                    "Returns deterministic offers priced in INR. When no direct route "
                    "exists it builds a connection through a hub, so far-apart cities "
                    "still produce a bookable pair."
                ),
                io=["in · origin, destination, date, cabin", "out · flight offers"],
                step_match=["flights:"],
            ),
            ArchNode(
                id="hotels",
                label="Stays",
                kind="tool",
                runtime="MCP tool",
                summary="Stays ranked to the traveller's budget tier.",
                detail=(
                    "Selects properties matched to the budget tier and party size, with "
                    "nightly and total pricing carried through to the cost breakdown."
                ),
                io=["in · city, nights, budget tier", "out · hotel offers"],
                step_match=["hotels:"],
            ),
            ArchNode(
                id="visa",
                label="Visa",
                kind="tool",
                runtime="MCP tool",
                summary="Entry requirements for the passport and destination.",
                detail=(
                    "Assesses the visa category, processing time, and notes for the "
                    "traveller's passport against each destination country."
                ),
                io=["in · passport, destination country", "out · visa requirement"],
                step_match=["visa:"],
            ),
            ArchNode(
                id="weather",
                label="Weather",
                kind="tool",
                runtime="MCP tool",
                summary="Seasonal brief for the month of travel.",
                detail=(
                    "Provides the seasonal outlook used for the season note and to keep "
                    "day plans sensible for the time of year."
                ),
                io=["in · city, month", "out · weather brief"],
                step_match=["weather:"],
            ),
            ArchNode(
                id="pois",
                label="Places",
                kind="tool",
                runtime="Knowledge graph",
                summary="Candidate sights ranked against stated interests.",
                detail=(
                    "Ranks points of interest from the knowledge graph by interest match "
                    "and rating, capped per city to keep the synthesis prompt lean."
                ),
                io=["in · city, interests", "out · candidate places"],
                step_match=["pois:"],
            ),
        ],
    )

    synthesizer = ArchNode(
        id="synthesizer",
        label="Synthesizer",
        kind="agent",
        runtime=_reasoning_runtime(live),
        model=planner,
        summary="Composes a day-by-day plan from the gathered options.",
        detail=(
            "The one place the heavy planner model runs. It is handed only the gathered, "
            "real options and must build the plan from them — it cannot reach outside the "
            "provided context, which is what keeps the itinerary grounded. Falls back to a "
            "deterministic composer when no model key is present."
        ),
        io=["in · the planning context", "out · a synthesis plan"],
        step_match=["synthesizer"],
    )
    assembler = ArchNode(
        id="assembler",
        label="Assembler",
        kind="tool",
        runtime="MCP · composition",
        summary="Turns the plan into a rich itinerary — dining, transit, events, themes.",
        detail=(
            "Deterministically assembles the final itinerary: schedules each day against "
            "opening hours, picks dining respecting diet and budget, adds transit between "
            "stops, a day theme, getting-around notes, seasonal events, and the cost "
            "breakdown."
        ),
        io=["in · synthesis plan + options", "out · the itinerary"],
        children=[
            ArchNode(
                id="dining",
                label="Dining",
                kind="tool",
                runtime="MCP tool",
                summary="Lunch and dinner picks respecting diet and budget.",
                detail=(
                    "Recommends restaurants per day that satisfy the traveller's food "
                    "preference and budget tier, never repeating a venue across the trip."
                ),
                io=["in · city, meal, diet, budget", "out · dining picks"],
            ),
            ArchNode(
                id="guide",
                label="City guide",
                kind="tool",
                runtime="MCP tool",
                summary="Getting-around notes and seasonal events.",
                detail=(
                    "Supplies the getting-around guidance and the month-aware events that "
                    "appear in the 'before you go' section."
                ),
                io=["in · city, month", "out · transit note, events"],
            ),
        ],
    )

    critic = ArchNode(
        id="critic",
        label="Critic",
        kind="critic",
        runtime="Validation loop",
        summary="Checks the itinerary and sends fixes back for repair.",
        detail=(
            "Validates feasibility — grounded places, opening hours, budget fit — and on "
            "failure feeds the specific problems back to the synthesizer for a bounded "
            "number of repair passes. The plan is only returned once it is valid or the "
            "repair budget is spent."
        ),
        io=["in · candidate itinerary", "out · validation report → repair feedback"],
        step_match=["critic"],
    )

    root = ArchNode(
        id="coordinator",
        label="Coordinator",
        kind="coordinator",
        runtime="Google ADK · AG-UI",
        summary="Orchestrates the whole hero flow and streams it live.",
        detail=(
            "The root agent. It runs intent → enrichment → resolution → parallel gathering "
            "→ synthesis → validate-and-repair, tracing every step. Each span is streamed "
            "over AG-UI as it starts and finishes, which is what drives the live highlight "
            "in this view."
        ),
        io=["in · message + traveller", "out · a validated, bookable itinerary"],
        step_match=["coordinator"],
        children=[intent, enrichment, resolver, specialists, synthesizer, assembler, critic],
    )

    return Architecture(
        root=root,
        live=live,
        model_fast=fast,
        model_planner=planner,
        protocols=_PROTOCOLS,
    )
