import type { SpanKind, SpanMetrics } from "@/lib/types";
import { formatCost, formatMs } from "@/lib/format";

function depthOf(span: SpanMetrics, byId: Map<string, SpanMetrics>): number {
  let depth = 0;
  let current = span.parent_id;
  while (current && byId.has(current) && depth < 6) {
    depth += 1;
    current = byId.get(current)!.parent_id;
  }
  return depth;
}

function dotClass(kind: SpanKind): string {
  if (kind === "agent") return "dot dot--agent";
  if (kind === "tool") return "dot dot--tool";
  if (kind === "model") return "dot dot--model";
  return "dot";
}

interface TraceViewProps {
  spans: SpanMetrics[];
  activeSteps: string[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function TraceView({ spans, activeSteps, selectedId, onSelect }: TraceViewProps) {
  if (spans.length === 0 && activeSteps.length === 0) {
    return (
      <div className="empty">
        <div className="empty__glyph">Behind the plan</div>
        <p>As a trip is composed, each agent and tool appears here with its latency, tokens, and cost.</p>
      </div>
    );
  }

  const byId = new Map(spans.map((s) => [s.span_id, s]));
  const selected = spans.find((s) => s.span_id === selectedId) ?? null;

  return (
    <div className="trace">
      {spans.map((span) => {
        const depth = depthOf(span, byId);
        const classes = [
          "tracenode",
          depth > 0 ? "tracenode--depth" : "",
          span.span_id === selectedId ? "tracenode--selected" : "",
        ].join(" ");
        return (
          <button
            key={span.span_id}
            className={classes}
            style={{ marginLeft: depth * 22 }}
            onClick={() => onSelect(span.span_id)}
          >
            <span className={dotClass(span.kind)} />
            <span>
              <span className="tracenode__name">{span.name}</span>
              <span className="tracenode__kind">{span.kind}</span>
            </span>
            <span className="tracenode__metrics">
              <span>{formatMs(span.duration_ms)}</span>
              {span.tokens !== null && <span className="t">{span.tokens} tok</span>}
              {span.cost_usd !== null && <span className="c">{formatCost(span.cost_usd)}</span>}
            </span>
          </button>
        );
      })}

      {activeSteps.map((name) => (
        <div className="tracenode tracenode--active" key={`active-${name}`}>
          <span className="dot dot--agent" />
          <span>
            <span className="tracenode__name">{name}</span>
            <span className="tracenode__kind">running</span>
          </span>
          <span className="tracenode__metrics">…</span>
        </div>
      ))}

      {selected && (
        <div className="inspector">
          <h4>{selected.name}</h4>
          <dl className="kv">
            <dt>kind</dt>
            <dd>{selected.kind}</dd>
            <dt>status</dt>
            <dd>{selected.status}</dd>
            <dt>latency</dt>
            <dd>{formatMs(selected.duration_ms)}</dd>
            {selected.model && (
              <>
                <dt>model</dt>
                <dd>{selected.model}</dd>
              </>
            )}
            {selected.tokens !== null && (
              <>
                <dt>tokens</dt>
                <dd>{selected.tokens}</dd>
              </>
            )}
            {selected.cost_usd !== null && (
              <>
                <dt>cost</dt>
                <dd>{formatCost(selected.cost_usd)}</dd>
              </>
            )}
            <dt>span id</dt>
            <dd>{selected.span_id}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}
