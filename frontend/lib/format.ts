import type { Money } from "./types";

const SYMBOL: Record<string, string> = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
  AED: "AED ",
  SGD: "S$",
  THB: "฿",
  JPY: "¥",
};

/** Format money with a currency symbol and thousands separators. */
export function formatMoney(money: Money | null | undefined): string {
  if (!money) return "—";
  const value = Number(money.amount);
  const symbol = SYMBOL[money.currency] ?? `${money.currency} `;
  return `${symbol}${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/** Trim a "HH:MM:SS" time to "HH:MM". */
export function hhmm(time: string): string {
  return time.slice(0, 5);
}

/** Format a USD cost string for the telemetry readout. */
export function formatCost(usd: string | number): string {
  return `$${Number(usd).toFixed(4)}`;
}

/** Format minutes as "Hh Mm". */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

/** Format a millisecond duration compactly. */
export function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
}

function parseDate(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}

/** Format a date range like "12 Sep – 16 Sep 2026". */
export function formatDateRange(start: string, end: string): string {
  if (start === end) {
    return parseDate(start).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }
  const left = parseDate(start).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const right = parseDate(end).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return `${left} – ${right}`;
}

/** Format a day's date like "Friday, 12 September". */
export function formatDayDate(iso: string): string {
  return parseDate(iso).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

/** Minutes between two "HH:MM:SS" times. */
export function minutesBetween(start: string, end: string): number {
  const toMin = (t: string) => {
    const [h, m] = t.split(":");
    return Number(h) * 60 + Number(m);
  };
  return toMin(end) - toMin(start);
}
