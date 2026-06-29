import { useMemo, useState } from "react";

import type { ArchNode, Architecture, NodeKind } from "@/lib/types";

const GLYPH: Record<NodeKind, string> = {
  coordinator: "◇",
  agent: "◆",
  tool: "▸",
  model: "✦",
  critic: "⟳",
};

function isActive(node: ArchNode, activeSteps: string[]): boolean {
  if (node.step_match.length === 0) return false;
  return activeSteps.some((step) =>
    node.step_match.some((prefix) => step === prefix || step.startsWith(prefix)),
  );
}

function flatten(node: ArchNode): ArchNode[] {
  return [node, ...node.children.flatMap(flatten)];
}

function Branch({
  node,
  depth,
  activeSteps,
  selectedId,
  onSelect,
}: {
  node: ArchNode;
  depth: number;
  activeSteps: string[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const active = isActive(node, activeSteps);
  const classes = [
    "archnode",
    `archnode--${node.kind}`,
    active ? "archnode--active" : "",
    node.id === selectedId ? "archnode--selected" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <>
      <button
        className={classes}
        style={{ marginLeft: depth * 26 }}
        onClick={() => onSelect(node.id)}
      >
        <span className="archnode__glyph">{GLYPH[node.kind]}</span>
        <span className="archnode__body">
          <span className="archnode__top">
            <span className="archnode__label">{node.label}</span>
            <span className="archnode__runtime">{node.runtime}</span>
          </span>
          <span className="archnode__summary">{node.summary}</span>
        </span>
        {active && <span className="archnode__live">live</span>}
      </button>
      {node.children.map((child) => (
        <Branch
          key={child.id}
          node={child}
          depth={depth + 1}
          activeSteps={activeSteps}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

export function ArchitectureView({
  architecture,
  activeSteps,
}: {
  architecture: Architecture;
  activeSteps: string[];
}) {
  const [selectedId, setSelectedId] = useState(architecture.root.id);
  const selected = useMemo(
    () => flatten(architecture.root).find((n) => n.id === selectedId) ?? architecture.root,
    [architecture, selectedId],
  );

  return (
    <div className="arch">
      <div className="arch__head">
        <div>
          <div className="arch__kicker">The architecture</div>
          <p className="arch__lead">
            The real agent graph behind every plan. While a trip composes, each node
            lights as its step runs — streamed live over AG-UI.
          </p>
        </div>
        <div className="arch__path">
          <span className="arch__pathlabel">Reasoning path</span>
          <span className="arch__pathval">
            {architecture.live ? "Gemini" : "Heuristic"}
          </span>
          <span className="arch__models">
            fast · {architecture.model_fast} &nbsp;·&nbsp; planner · {architecture.model_planner}
          </span>
        </div>
      </div>

      <div className="arch__grid">
        <div className="archtree">
          <Branch
            node={architecture.root}
            depth={0}
            activeSteps={activeSteps}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>

        <aside className="archpanel">
          <div className={`archpanel__kind archpanel__kind--${selected.kind}`}>
            {selected.kind}
          </div>
          <h3 className="archpanel__title">{selected.label}</h3>
          <div className="archpanel__runtime">{selected.runtime}</div>
          {selected.model && (
            <div className="archpanel__model">model · {selected.model}</div>
          )}
          <p className="archpanel__detail">{selected.detail}</p>
          {selected.io.length > 0 && (
            <ul className="archpanel__io">
              {selected.io.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      <div className="arch__legend">
        {architecture.protocols.map((p) => (
          <div className="legend" key={p.key}>
            <span className="legend__name">{p.name}</span>
            <span className="legend__role">{p.role}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
