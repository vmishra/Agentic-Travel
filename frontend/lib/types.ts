// Types mirroring the backend JSON (snake_case, as produced by Pydantic's
// model_dump(mode="json")). Kept deliberately close to the API contract.

export interface Money {
  amount: string;
  currency: string;
}

export interface Carrier {
  code: string;
  name: string;
}

export interface FlightSegment {
  carrier: Carrier;
  flight_number: string;
  origin_city_id: string;
  destination_city_id: string;
  departure: string;
  arrival: string;
  duration_minutes: number;
}

export interface FlightOffer {
  offer_id: string;
  segments: FlightSegment[];
  cabin: string;
  fare_tier: string;
  price: Money;
  seats_available: number;
  baggage_kg: number;
  refundable: boolean;
}

export interface Hotel {
  hotel_id: string;
  name: string;
  city_id: string;
  brand: string;
  star_rating: number;
  guest_rating: number;
  review_count: number;
  amenities: string[];
  budget_tier: string;
  nightly_rate: Money;
}

export interface HotelOffer {
  offer_id: string;
  hotel: Hotel;
  room_type: string;
  nights: number;
  total_price: Money;
  rooms_available: number;
  free_cancellation: boolean;
}

export interface VisaRequirement {
  passport_country: string;
  destination_country: string;
  category: string;
  processing_days: number;
  fee: Money | null;
  max_stay_days: number;
  notes: string;
}

export interface Activity {
  poi_id: string;
  name: string;
  start: string;
  end: string;
  estimated_cost: Money | null;
  notes: string;
}

export interface DayPlan {
  day_index: number;
  date: string;
  city_id: string;
  activities: Activity[];
  notes: string;
}

export interface Itinerary {
  itinerary_id: string;
  title: string;
  traveler_id: string | null;
  party_size: number;
  origin_city_id: string;
  destination_city_ids: string[];
  start_date: string;
  end_date: string;
  flights: FlightOffer[];
  hotels: HotelOffer[];
  visa: VisaRequirement[];
  days: DayPlan[];
  estimated_total: Money;
  summary: string;
}

export interface ValidationIssue {
  severity: "error" | "warning";
  code: string;
  message: string;
  day_index: number | null;
  poi_id: string | null;
}

export interface ValidationReport {
  issues: ValidationIssue[];
}

export interface TripBrief {
  intent: string;
  traveler_id: string | null;
  passport_country: string;
  origin_city_id: string | null;
  destination_query: string;
  start_date: string | null;
  nights: number | null;
  party_size: number;
  budget: Money | null;
  budget_tier: string;
  food_preference: string;
  interests: string[];
  occasion: string | null;
  clarifications_needed: string[];
}

export interface PlanningResult {
  brief: TripBrief;
  itinerary: Itinerary | null;
  validation: ValidationReport;
  resolved_city_ids: string[];
  attempts: number;
}

export interface TravelerProfile {
  traveler_id: string;
  display_name: string;
  home_city_id: string;
  passport_country: string;
  food_preference: string;
  budget_tier: string;
  loyalty_programs: string[];
  visited_city_ids: string[];
  interests: string[];
}

export type SpanKind = "agent" | "tool" | "model" | "mcp" | "internal";

export interface SpanMetrics {
  span_id: string;
  parent_id: string | null;
  name: string;
  kind: SpanKind;
  status: "ok" | "error";
  duration_ms: number | null;
  model: string | null;
  tokens: number | null;
  cost_usd: string | null;
}
