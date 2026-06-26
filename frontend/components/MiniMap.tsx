import type { Activity } from "@/lib/types";

const W = 620;
const H = 300;
const PAD = 34;

/** A keyless, editorial route sketch: numbered pins plotted from POI coordinates. */
export function MiniMap({ activities }: { activities: Activity[] }) {
  const pts = activities.filter((a): a is Activity & { location: NonNullable<Activity["location"]> } =>
    a.location !== null,
  );

  if (pts.length < 2) {
    return (
      <div className="map">
        <div className="map__empty">A route sketch appears once stops are placed.</div>
      </div>
    );
  }

  const lats = pts.map((p) => p.location.lat);
  const lngs = pts.map((p) => p.location.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);

  const x = (lng: number) =>
    maxLng === minLng ? W / 2 : PAD + ((lng - minLng) / (maxLng - minLng)) * (W - 2 * PAD);
  const y = (lat: number) =>
    maxLat === minLat ? H / 2 : PAD + ((maxLat - lat) / (maxLat - minLat)) * (H - 2 * PAD);

  const coords = pts.map((p) => ({ cx: x(p.location.lng), cy: y(p.location.lat) }));
  const path = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.cx} ${c.cy}`).join(" ");

  return (
    <div className="map">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Route sketch">
        <path className="map__line" d={path} />
        {coords.map((c, i) => (
          <g key={i}>
            <circle className="map__pin" cx={c.cx} cy={c.cy} r="11" />
            <text className="map__no" x={c.cx} y={c.cy + 3.2}>
              {i + 1}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
