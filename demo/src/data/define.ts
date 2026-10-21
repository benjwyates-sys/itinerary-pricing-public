/**
 * Small constructors for authoring the sample catalog.
 *
 * These exist only to keep ~180 hand-written experiences readable. They add
 * no behaviour — every one of them returns a plain `CatalogItem` or
 * `Modifier` exactly as `src/engine/types.ts` defines it.
 */
import type {
  CatalogItem,
  Currency,
  DayPart,
  Modifier,
  Pricing,
} from "../engine/types";

export type CitySpec = {
  name: string;
  country: string;
  currency: Currency;
  /** Id prefix, e.g. "HR-DBV". */
  prefix: string;
};

type Body = {
  unit?: CatalogItem["unit"];
  pricing?: Pricing;
  modifiers?: Modifier[];
  minBillablePax?: number;
  note?: string;
};

/** Returns an item builder bound to one city, so ids and currency can't drift. */
export function city(spec: CitySpec) {
  return (n: number, name: string, body: Body = {}): CatalogItem => ({
    id: `${spec.prefix}-${String(n).padStart(4, "0")}`,
    name,
    city: spec.name,
    country: spec.country,
    currency: spec.currency,
    unit: body.unit ?? "per_person",
    pricing: body.pricing,
    modifiers: body.modifiers ?? [],
    ...(body.minBillablePax === undefined ? {} : { minBillablePax: body.minBillablePax }),
    ...(body.note === undefined ? {} : { note: body.note }),
  });
}

export const flat = (amount: string): Pricing => ({ pattern: "flat", amount });

/** Bands ascending. Above the top band the engine refuses rather than extrapolates. */
export const tiered = (...bands: [maxPax: number, amount: string][]): Pricing => ({
  pattern: "tiered_by_pax",
  tiers: bands.map(([maxPax, amount]) => ({ maxPax, amount })),
});

export const timeOfDay = (when: DayPart[], amount: string): Modifier => ({
  type: "day_part",
  when,
  op: "add_per_unit",
  amount,
});

export const evening = (amount: string) => timeOfDay(["EVENING"], amount);
export const afternoon = (amount: string) => timeOfDay(["PM"], amount);

export const season = (from: string, to: string, amount: string): Modifier => ({
  type: "seasonal",
  from,
  to,
  op: "add_per_unit",
  amount,
});

/** A season that lands on the booking rather than per head, e.g. a charter. */
export const seasonPerBooking = (from: string, to: string, amount: string): Modifier => ({
  type: "seasonal",
  from,
  to,
  op: "add_per_booking",
  amount,
});

export const weekendSurcharge = (factor: string): Modifier => ({
  type: "day_of_week",
  when: ["SAT", "SUN"],
  op: "multiply",
  factor,
});

export const blackout = (...dates: string[]): Modifier => ({ type: "blackout", dates });

export const ON_REQUEST = "on request, supplier quotes this individually";
