import type { PlanningResult } from "@/lib/types";
import { formatDuration, formatMoney, hhmm } from "@/lib/format";

function ValidationBanner({ result }: { result: PlanningResult }) {
  const issues = result.validation.issues;
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  if (errors.length === 0 && warnings.length === 0) {
    return (
      <div className="banner banner--ok">
        Itinerary verified — every place, flight, and hotel is grounded and
        feasible{result.attempts > 1 ? ` (repaired in ${result.attempts} passes)` : ""}.
      </div>
    );
  }
  const kind = errors.length > 0 ? "banner--err" : "banner--warn";
  const shown = [...errors, ...warnings].slice(0, 5);
  return (
    <div className={`banner ${kind}`}>
      {errors.length > 0
        ? "Some constraints could not be satisfied:"
        : "Planned with advisories:"}
      <ul>
        {shown.map((issue, i) => (
          <li key={i}>{issue.message}</li>
        ))}
      </ul>
    </div>
  );
}

export function ItineraryView({ result }: { result: PlanningResult }) {
  const itinerary = result.itinerary;
  if (!itinerary) {
    const asks = result.brief.clarifications_needed;
    return (
      <div className="empty">
        <div className="empty__glyph">— HOLD —</div>
        <p>
          {asks.length > 0
            ? `A few details first: ${asks.join(", ")}.`
            : "No itinerary yet."}
        </p>
      </div>
    );
  }

  return (
    <>
      <ValidationBanner result={result} />
      <article className="doc">
        <header className="doc__head">
          <div className="doc__total">
            <span className="mono">{formatMoney(itinerary.estimated_total)}</span>
            <small>est. total</small>
          </div>
          <h2 className="doc__title">{itinerary.title}</h2>
          <p className="doc__sub">
            {itinerary.summary} · party of {itinerary.party_size}
          </p>
        </header>

        {itinerary.flights.length > 0 && (
          <section className="doc__section">
            <h3>Flights</h3>
            <div className="cardrow">
              {itinerary.flights.map((f) => {
                const seg = f.segments[0];
                return (
                  <div className="tkt" key={f.offer_id}>
                    <div className="tkt__top">
                      <span className="tkt__code">{seg.flight_number}</span>
                      <span className="tkt__price">{formatMoney(f.price)}</span>
                    </div>
                    <div className="tkt__meta">
                      {seg.carrier.name} · {seg.origin_city_id.replace("city_", "").toUpperCase()} →{" "}
                      {seg.destination_city_id.replace("city_", "").toUpperCase()} ·{" "}
                      {formatDuration(seg.duration_minutes)}
                    </div>
                    <span className="tkt__tag">
                      {f.cabin} · {f.fare_tier}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {itinerary.hotels.length > 0 && (
          <section className="doc__section">
            <h3>Stays</h3>
            <div className="cardrow">
              {itinerary.hotels.map((h) => (
                <div className="tkt" key={h.offer_id}>
                  <div className="tkt__top">
                    <span className="tkt__code">{h.hotel.name}</span>
                    <span className="tkt__price">{formatMoney(h.total_price)}</span>
                  </div>
                  <div className="tkt__meta">
                    {h.hotel.brand} · {"★".repeat(h.hotel.star_rating)} ·{" "}
                    {h.hotel.guest_rating}/10 · {h.nights} night{h.nights > 1 ? "s" : ""}
                  </div>
                  <span className="tkt__tag">
                    {h.free_cancellation ? "free cancellation" : "non-refundable"}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="doc__section">
          <h3>Itinerary</h3>
          {itinerary.days.map((day) => (
            <div className="day" key={day.day_index}>
              <div className="day__head">
                <span className="day__index">DAY {day.day_index}</span>
                <span className="day__date">{day.date}</span>
              </div>
              {day.activities.length === 0 && (
                <div className="stop">
                  <span className="stop__time">—</span>
                  <span className="stop__note">A free day to explore at your pace.</span>
                </div>
              )}
              {day.activities.map((a, i) => (
                <div className="stop" key={i}>
                  <span className="stop__time">
                    {hhmm(a.start)}–{hhmm(a.end)}
                  </span>
                  <div>
                    <div className="stop__name">{a.name}</div>
                    {a.notes && <div className="stop__note">{a.notes}</div>}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </section>

        {itinerary.visa.length > 0 && (
          <section className="doc__section">
            <h3>Entry & visa</h3>
            {itinerary.visa.map((v, i) => (
              <p className="visa" key={i}>
                <span className="visa__cat">{v.category.replace(/_/g, " ")}</span> ·{" "}
                {v.destination_country}: {v.notes}
                {v.processing_days > 0 && ` (${v.processing_days}d processing)`}
              </p>
            ))}
          </section>
        )}

        <section className="doc__section">
          <h3>Route</h3>
          <div className="mapph">map view · arriving in a later build</div>
        </section>
      </article>
    </>
  );
}
