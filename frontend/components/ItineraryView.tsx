import { Fragment } from "react";

import type { Activity, DiningPick, Itinerary, Money, PlanningResult } from "@/lib/types";
import {
  formatDateRange,
  formatDayDate,
  formatDuration,
  formatMoney,
  hhmm,
  minutesBetween,
} from "@/lib/format";
import { MiniMap } from "./MiniMap";

const CITY_NAMES: Record<string, string> = {
  city_bom: "Mumbai",
  city_goi: "Goa",
  city_cmb: "Colombo",
  city_dxb: "Dubai",
  city_sfo: "San Francisco",
  city_nyc: "New York",
  city_lon: "London",
  city_par: "Paris",
  city_tyo: "Tokyo",
  city_sin: "Singapore",
};

const cityName = (id: string) => CITY_NAMES[id] ?? id.replace("city_", "").replace(/\b\w/g, (c) => c.toUpperCase());
const code = (id: string) => id.replace("city_", "").toUpperCase();
const partOf = (start: string) => {
  const hour = Number(start.slice(0, 2));
  return hour < 12 ? "Morning" : hour < 17 ? "Afternoon" : "Evening";
};

function ValidationBanner({ result }: { result: PlanningResult }) {
  const issues = result.validation.issues;
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  if (errors.length === 0 && warnings.length === 0) {
    return (
      <div className="banner banner--ok">
        Verified — every place, flight, and hotel is grounded and feasible
        {result.attempts > 1 ? `, refined over ${result.attempts} passes` : ""}.
      </div>
    );
  }
  const shown = [...errors, ...warnings].slice(0, 5);
  return (
    <div className={`banner ${errors.length ? "banner--err" : "banner--warn"}`}>
      {errors.length ? "Some constraints could not be satisfied:" : "Planned, with a few notes:"}
      <ul>
        {shown.map((issue, i) => (
          <li key={i}>{issue.message}</li>
        ))}
      </ul>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="fact__label">{label}</div>
      <div className="fact__value">{value}</div>
    </div>
  );
}

function FlightCard({ flight }: { flight: Itinerary["flights"][number] }) {
  const first = flight.segments[0];
  const last = flight.segments[flight.segments.length - 1];
  const minutes = flight.segments.reduce((t, s) => t + s.duration_minutes, 0);
  const stops = flight.segments.length - 1;
  return (
    <div className="card">
      <div className="card__top">
        <span className="card__name">
          {code(first.origin_city_id)} → {code(last.destination_city_id)}
        </span>
        <span className="card__price num">{formatMoney(flight.price)}</span>
      </div>
      <div className="card__meta">
        {first.carrier.name} · {flight.segments.map((s) => s.flight_number).join(", ")} ·{" "}
        {formatDuration(minutes)} · {stops === 0 ? "nonstop" : `${stops} stop via ${code(first.destination_city_id)}`}
      </div>
      <span className="card__tag">
        {flight.cabin.replace("_", " ")} · {flight.fare_tier}
      </span>
    </div>
  );
}

function StayCard({ stay }: { stay: Itinerary["hotels"][number] }) {
  return (
    <div className="card">
      <div className="card__top">
        <span className="card__name">{stay.hotel.name}</span>
        <span className="card__price num">{formatMoney(stay.total_price)}</span>
      </div>
      <div className="card__meta">
        {stay.hotel.brand} · {"★".repeat(stay.hotel.star_rating)} · {stay.hotel.guest_rating}/10 ·{" "}
        {stay.nights} night{stay.nights > 1 ? "s" : ""}
      </div>
      <span className="card__tag">
        {stay.hotel.amenities.slice(0, 4).join(" · ")}
      </span>
    </div>
  );
}

function Stop({ activity }: { activity: Activity }) {
  const duration = minutesBetween(activity.start, activity.end);
  const meta = [
    activity.rating ? `${activity.rating.toFixed(1)} ★` : null,
    duration > 0 ? formatDuration(duration) : null,
    activity.estimated_cost && Number(activity.estimated_cost.amount) > 0
      ? formatMoney(activity.estimated_cost)
      : "Free",
  ].filter(Boolean);
  return (
    <div className="stop">
      <div className="stop__time num">{hhmm(activity.start)}</div>
      <div>
        <div className="stop__name">
          {activity.name}
          {activity.category && <span className="stop__cat">{activity.category}</span>}
        </div>
        <div className="stop__meta">{meta.join("  ·  ")}</div>
        {activity.notes && <div className="stop__note">{activity.notes}</div>}
      </div>
    </div>
  );
}

function DiningRow({ pick }: { pick: DiningPick }) {
  return (
    <div className="dine">
      <div className="dine__meal">{pick.meal}</div>
      <div>
        <div className="dine__name">
          {pick.name}
          <span className="dine__cuisine">
            {pick.cuisine}
            {pick.neighborhood ? ` · ${pick.neighborhood}` : ""}
          </span>
        </div>
        {pick.why && <div className="dine__why">{pick.why}</div>}
      </div>
    </div>
  );
}

function BudgetBar({ label, amount, total }: { label: string; amount: Money; total: number }) {
  const pct = total > 0 ? (Number(amount.amount) / total) * 100 : 0;
  return (
    <div className="brow">
      <span className="brow__label">{label}</span>
      <span className="brow__bar">
        <span className="brow__fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="brow__amt num">{formatMoney(amount)}</span>
    </div>
  );
}

export function ItineraryView({ result }: { result: PlanningResult }) {
  const it = result.itinerary;
  if (!it) {
    const asks = result.brief.clarifications_needed;
    return (
      <div className="empty">
        <div className="empty__glyph">A moment —</div>
        <p>
          {asks.length > 0
            ? `Tell me ${asks.join(" and ")}, and I'll compose the plan.`
            : "No itinerary yet."}
        </p>
      </div>
    );
  }

  const destinations = it.destination_city_ids.map(cityName).join(", ");
  const allActivities = it.days.flatMap((d) => d.activities);
  const localCurrency = it.hotels[0]?.hotel.nightly_rate.currency;
  const cb = it.cost_breakdown;

  return (
    <article className="dossier">
      <header className="dossier__hero">
        <div className="dossier__eyebrow">
          {destinations} · {formatDateRange(it.start_date, it.end_date)}
        </div>
        <h1 className="dossier__title">{it.title}</h1>
        {it.style_tags.length > 0 && (
          <div className="dossier__tags">
            {it.style_tags.map((t) => (
              <span className="tag" key={t}>
                {t}
              </span>
            ))}
          </div>
        )}
        {it.summary && <p className="dossier__summary">{it.summary}</p>}
        <div className="facts">
          <Fact label="Length" value={`${it.days.length} day${it.days.length > 1 ? "s" : ""}`} />
          <Fact label="Travellers" value={`Party of ${it.party_size}`} />
          <Fact label="Estimated total" value={formatMoney(it.estimated_total)} />
          {cb && <Fact label="Per person" value={formatMoney(cb.per_person)} />}
        </div>
      </header>

      <ValidationBanner result={result} />

      {it.highlights.length > 0 && (
        <section className="section">
          <h2 className="section__label">The highlights</h2>
          <ul className="highlights">
            {it.highlights.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </section>
      )}

      {it.flights.length > 0 && (
        <section className="section">
          <h2 className="section__label">Getting there</h2>
          <div className="cards">
            {it.flights.map((f) => (
              <FlightCard flight={f} key={f.offer_id} />
            ))}
          </div>
        </section>
      )}

      {it.hotels.length > 0 && (
        <section className="section">
          <h2 className="section__label">Where you&apos;ll stay</h2>
          <div className="cards">
            {it.hotels.map((h) => (
              <StayCard stay={h} key={h.offer_id} />
            ))}
          </div>
        </section>
      )}

      <section className="section">
        <h2 className="section__label">Day by day</h2>
        {it.days.map((day) => {
          let lastPart = "";
          return (
            <div className="chapter" key={day.day_index}>
              <div className="chapter__head">
                <span className="chapter__no">Day {day.day_index}</span>
                <span className="chapter__date">{formatDayDate(day.date)}</span>
              </div>
              {day.theme && <div className="chapter__theme">{day.theme}</div>}
              {day.activities.length === 0 && (
                <div className="dayfree">A free day to wander at your own pace.</div>
              )}
              {day.activities.map((a, i) => {
                const part = partOf(a.start);
                const newPart = part !== lastPart;
                lastPart = part;
                return (
                  <Fragment key={i}>
                    {newPart && <div className="daypart__label">{part}</div>}
                    <Stop activity={a} />
                    {a.travel_minutes_to_next != null && (
                      <div className="leg">
                        ≈ {a.travel_minutes_to_next} min
                        {a.travel_mode_to_next ? ` by ${a.travel_mode_to_next}` : ""} to the next stop
                      </div>
                    )}
                  </Fragment>
                );
              })}
              {day.dining.length > 0 && (
                <div className="dining">
                  <div className="dining__label">Where to eat</div>
                  {day.dining.map((d, i) => (
                    <DiningRow pick={d} key={i} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </section>

      {allActivities.some((a) => a.location) && (
        <section className="section">
          <h2 className="section__label">The route</h2>
          <MiniMap activities={allActivities} />
        </section>
      )}

      {cb && (
        <section className="section">
          <h2 className="section__label">What it costs</h2>
          <div className="budget">
            <div className="budget__rows">
              <BudgetBar label="Flights" amount={cb.flights} total={Number(cb.total.amount)} />
              <BudgetBar label="Stays" amount={cb.stays} total={Number(cb.total.amount)} />
              <BudgetBar label="Activities & entry" amount={cb.activities} total={Number(cb.total.amount)} />
            </div>
            <div className="budget__totals">
              <Fact label="Per person" value={formatMoney(cb.per_person)} />
              <Fact label="Per day" value={formatMoney(cb.per_day)} />
              <Fact label="Total" value={formatMoney(cb.total)} />
            </div>
            <p className="budget__note">{cb.note}</p>
          </div>
        </section>
      )}

      <section className="section">
        <h2 className="section__label">Before you go</h2>
        <div className="notes">
          {it.season_note && (
            <div>
              <div className="note__label">Season &amp; weather</div>
              <div className="note__body">{it.season_note}</div>
            </div>
          )}
          {it.getting_around && (
            <div>
              <div className="note__label">Getting around</div>
              <div className="note__body">{it.getting_around}</div>
            </div>
          )}
          {it.events.length > 0 && (
            <div>
              <div className="note__label">While you&apos;re there</div>
              <div className="note__body">
                {it.events.map((e, i) => (
                  <p className="event" key={i}>
                    <strong>{e.name}.</strong> {e.blurb}
                  </p>
                ))}
              </div>
            </div>
          )}
          {it.visa.map((v, i) => (
            <div key={i}>
              <div className="note__label">Entry &amp; visa — {v.destination_country}</div>
              <div className="note__body">
                <em>{v.category.replace(/_/g, " ")}</em>
                {v.processing_days > 0 ? ` · about ${v.processing_days} days to process` : ""}. {v.notes}
              </div>
            </div>
          ))}
          {localCurrency && (
            <div>
              <div className="note__label">Money</div>
              <div className="note__body">
                Prices shown in INR; the local currency is <em>{localCurrency}</em>. Estimates exclude
                travel insurance and shopping.
              </div>
            </div>
          )}
        </div>
      </section>
    </article>
  );
}
