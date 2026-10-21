import type { Adjustment } from "./annotations";
import type { Candidate } from "./match";

/**
 * The data model, lifted from `pricing/catalog.py`.
 *
 * One deliberate change from the real engine, and only one: the engine
 * stores every rate as a *cell reference into a live workbook* plus the
 * value last seen there, so it can detect a rate sheet shifting under it.
 * The demo has no workbook, so `cell` becomes a literal `amount`, and
 * `name_cell`, `source_rows`, `row_fingerprint`, `structure_fingerprint`
 * and `last_seen` are dropped. Nothing else is redesigned.
 */

/** An exact decimal held as a string, e.g. "285.00". Never a number. */
export type Money = string;

export type Currency = "EUR" | "GBP" | "CHF" | "CZK";

export type DayPart = "AM" | "PM" | "EVENING";

export type Weekday = "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN";

export type Op = "add_per_unit" | "add_per_booking" | "multiply";

export type Tier = { maxPax: number; amount: Money };

export type Pricing =
  | { pattern: "flat"; amount: Money }
  /** Ascending by maxPax. Above the top tier is a refusal, never an extrapolation. */
  | { pattern: "tiered_by_pax"; tiers: Tier[] };

export type Modifier =
  | { type: "day_part"; when: DayPart[]; op: Op; amount?: Money; factor?: string }
  | { type: "day_of_week"; when: Weekday[]; op: Op; amount?: Money; factor?: string }
  /** ISO dates, inclusive at both ends. */
  | { type: "seasonal"; from: string; to: string; op: Op; amount?: Money; factor?: string }
  | { type: "blackout"; dates: string[] };

export type CatalogItem = {
  id: string;
  name: string;
  city: string;
  country: string;
  currency: Currency;
  unit: "per_person" | "per_group";
  minBillablePax?: number;
  /** Absent for an "on request" experience, which can only ever be quoted by a supplier. */
  pricing?: Pricing;
  modifiers: Modifier[];
  /** Shown in the admin view, e.g. "Billed for 4 minimum". */
  note?: string;
};

export type PricingRequest = {
  pax: number;
  /** ISO date, or null when the itinerary line carries no date. */
  date?: string | null;
  dayPart?: DayPart | null;
  /**
   * The consultant's own adjustments for this one line, read from notes she
   * wrote into its wording — a partial group, an agreed discount.
   *
   * This is an addition to the engine's INPUT, not to the catalog model: the
   * shape in `pricing/catalog.py` is untouched, and an item never carries
   * one of these. They ride with the multiply step so that rounding still
   * happens exactly once and the non-positive guard still governs the result.
   */
  adjustments?: { factor: Money; note: string }[];
};

/**
 * A refusal is a value, not an exception. The UI has no code path that can
 * render a price it did not receive — which is what makes rules 1 and 3 of
 * the handoff's non-negotiables structurally true rather than a convention.
 */
export type PricingResult =
  | { ok: true; total: Money; currency: Currency; breakdown: string[] }
  | { ok: false; reason: string };

export type TripLine = {
  id: string;
  /** The consultant's own wording, exactly as typed. Never rewritten. */
  text: string;
  date: string | null;
  pax: number;
  dayPart: DayPart | null;
};

export type Trip = {
  id: string;
  fileName: string;
  client: string;
  title: string;
  cities: string[];
  from: string;
  to: string;
  pax: number;
  lines: TripLine[];
  /** In order. Consecutive stays may share a date: that day is a transfer day. */
  stays: Stay[];
};

/**
 * `total` is null unless `status` is "priced". The three states are kept
 * distinct rather than collapsed into "done / not done" because they need
 * different work from a person: nothing, a ten-second pick, or an email.
 */
export type CostedLine = {
  line: TripLine;
  status: "priced" | "needs_check" | "needs_quote";
  total: Money | null;
  currency: Currency | null;
  /** The matched item, when there is one. */
  itemId: string | null;
  itemName: string | null;
  /** How the matched item charges. Null until something is matched. */
  unit: CatalogItem["unit"] | null;
  /** The billable floor, when the matched item has one. */
  minBillablePax: number | null;
  breakdown: string[];
  /** Populated for "needs_check": what to offer, best guess first. */
  candidates: Candidate[];
  /** Populated for "needs_quote": the engine's own words for why it refused. */
  reason: string | null;
  /** Notes the consultant wrote into the wording, and this line priced under. */
  adjustments: Adjustment[];
  /**
   * Notes that were left alone because the parser did not recognise them.
   * Their presence is why nothing on this line was applied.
   */
  unreadNotes: string[];
};

export type CurrencyTotal = { currency: Currency; total: Money };

export type CostedTrip = {
  trip: Trip;
  lines: CostedLine[];
  /** One entry per currency. Currencies are never added together. */
  totals: CurrencyTotal[];
  counts: { priced: number; needsCheck: number; needsQuote: number };
};

/**
 * A hotel stay.
 *
 * Accommodation is NOT priced by the engine. The ported data model knows
 * per_person and per_group and has no concept of a night, and §4 of the
 * handoff says not to redesign it — so a stay carries its own rate, and every
 * screen that shows its money labels it as coming from the accommodation
 * booking rather than the rate sheet.
 */
export type Stay = {
  city: string;
  hotel: string;
  room: string;
  rooms: number;
  /** ISO date. */
  checkIn: string;
  /** ISO date. The night before this date is the last one charged. */
  checkOut: string;
  nightlyRate: Money;
  currency: Currency;
};
