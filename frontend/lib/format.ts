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
