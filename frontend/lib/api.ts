import type { TravelerProfile } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface Health {
  status: string;
  live_models: boolean;
  missing_config: string[];
}

export async function fetchHealth(): Promise<Health> {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) throw new Error(`health check failed: ${response.status}`);
  return response.json();
}

export async function fetchPersonas(): Promise<TravelerProfile[]> {
  const response = await fetch(`${API_BASE}/personas`);
  if (!response.ok) throw new Error(`could not load personas: ${response.status}`);
  return response.json();
}
