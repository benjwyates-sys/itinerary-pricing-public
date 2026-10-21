/**
 * Arranging a costed trip into an itinerary: one block per day, in the order
 * the day happens.
 *
 * This is presentation structure, not pricing. It never computes a rate-sheet
 * price and never alters one — it places what the engine already returned, and
 * a line the engine refused stays refused wherever it lands.
 */
import { money, roundMoney } from "../engine/money";
import type { CostedLine, CostedTrip, Currency, Money, Stay, Trip, TripLine } from "../engine/types";

export type DaySlot = "AM" | "PM" | "EVENING";

/** Morning, afternoon, evening — the order a day is lived in. */
const SLOTS: DaySlot[] = ["AM", "PM", "EVENING"];

const DAY_MS = 86_400_000;

export type SlotBlock<T> = {
  slot: DaySlot;
  lines: T[];
  /** An empty half of an otherwise booked day: worth showing as free time. */
  free: boolean;
};

export type Day<T> = {
  date: string;
  number: number;
  city: string | null;
  checkIn: Stay | null;
  checkOut: Stay | null;
  slots: SlotBlock<T>[];
  /** Lines the itinerary gave no time for. Kept, never guessed into a slot. */
  untimed: T[];
  atLeisure: boolean;
};

/** A day of the trip once it has been costed. */
export type ItineraryDay = Day<CostedLine>;

/** A day of the trip as it arrived, before anything was priced. */
export type PreviewDay = Day<TripLine>;

/** Nights actually charged: the last night is the one before check-out. */
export function nightsOf(stay: Stay): number {
  return Math.max(0, Math.round((dayOf(stay.checkOut) - dayOf(stay.checkIn)) / DAY_MS));
}

/**
 * Nights × rooms × rate, in exact decimal.
 *
 * This is not a rate-sheet price and every screen that shows it says so — but
 * it is still money in a quote, so it gets the same arithmetic as everything
 * else rather than a float.
 */
export function stayTotal(stay: Stay): Money {
  return roundMoney(money(stay.nightlyRate).times(nightsOf(stay)).times(stay.rooms));
}

export function buildItinerary(costed: CostedTrip): ItineraryDay[] {
  return layOutDays(costed.trip, costed.lines, (entry) => entry.line);
}

/**
 * The itinerary as it arrived, before anything has been priced.
 *
 * Same days, same hotels, same free time — but the consultant's own wording
 * and no money anywhere, because none of it has been worked out yet. Sharing
 * the layout with the costed view is the point: what a visitor sees first is
 * demonstrably the same trip they see priced a moment later.
 */
export function previewItinerary(trip: Trip): PreviewDay[] {
  return layOutDays(trip, trip.lines, (entry) => entry);
}

function layOutDays<T>(trip: Trip, items: T[], lineOf: (item: T) => TripLine): Day<T>[] {
  // A line dated outside the trip's own range is a mistake in the itinerary,
  // not a reason to hide it — give it a day of its own rather than dropping it.
  const strays = items
    .map((item) => lineOf(item).date)
    .filter((date): date is string => Boolean(date));
  const dates = [...new Set([...datesBetween(trip.from, trip.to), ...strays])].sort();

  // The last check-out is the party going home. Nothing after it is free time.
  const departure = trip.stays.at(-1)?.checkOut ?? null;

  return dates.map((date, index) => {
    const onDay = items.filter((item) => lineOf(item).date === date);
    const checkIn = trip.stays.find((stay) => stay.checkIn === date) ?? null;
    const checkOut = trip.stays.find((stay) => stay.checkOut === date) ?? null;

    const slots: SlotBlock<T>[] = SLOTS.map((slot) => ({
      slot,
      lines: onDay.filter((item) => lineOf(item).dayPart === slot),
      free: false,
    }));
    const untimed = onDay.filter((item) => !lineOf(item).dayPart);

    // Free time is only meaningful against a day that has a shape to it. A day
    // whose bookings carry no time has nothing to be free *around*, and a day
    // the party spends flying home has no afternoon to spend.
    if (date !== departure && slots.some((block) => block.lines.length > 0)) {
      for (const block of slots) {
        if (block.slot !== "EVENING" && block.lines.length === 0) block.free = true;
      }
    }

    return {
      date,
      number: index + 1,
      city: placeOn(date, trip.stays, checkIn, checkOut),
      checkIn,
      checkOut,
      slots,
      untimed,
      atLeisure: onDay.length === 0 && !checkIn && !checkOut,
    };
  });
}

function placeOn(
  date: string,
  stays: Stay[],
  checkIn: Stay | null,
  checkOut: Stay | null,
): string | null {
  // Leaving one hotel and arriving at another on the same day is a move, and
  // reads better as one than as either end of it.
  if (checkIn && checkOut && checkIn.city !== checkOut.city) {
    return `${checkOut.city} → ${checkIn.city}`;
  }
  const staying = stays.find((stay) => stay.checkIn <= date && date < stay.checkOut);
  if (staying) return staying.city;
  // The final morning still belongs to the hotel being left.
  return checkOut?.city ?? null;
}

function datesBetween(from: string, to: string): string[] {
  const dates: string[] = [];
  for (let day = dayOf(from); day <= dayOf(to); day += DAY_MS) {
    dates.push(new Date(day).toISOString().slice(0, 10));
  }
  return dates;
}

function dayOf(iso: string): number {
  return Date.parse(`${iso}T00:00:00Z`);
}

export type TripMoney = {
  currency: Currency;
  /** Priced by the engine, from the rate sheet. */
  experiences: Money;
  /** From the accommodation booking. Never a rate-sheet price. */
  accommodation: Money;
  /** Typed in by the consultant against a line the engine refused. */
  own: Money | null;
  total: Money;
};

/**
 * The three kinds of money in a quote, held apart and then added.
 *
 * They are added because an itinerary needs a bottom line, and they are kept
 * separate because only the first of them came from the rate sheet. Every
 * screen showing `total` shows the composition beside it.
 */
export function tripMoney(costed: CostedTrip, ownPrices: Record<string, Money>): TripMoney {
  const currency = costed.totals[0]?.currency ?? costed.trip.stays[0]?.currency ?? "EUR";

  // Summed from the lines rather than taken from the engine's own total,
  // because a line the consultant has overridden is no longer the rate
  // sheet's money — it is hers, and it moves across to `own`.
  const experiences = costed.lines
    .filter(
      (line) =>
        line.status === "priced" &&
        line.currency === currency &&
        ownPrices[line.line.id] === undefined,
    )
    .reduce((sum, line) => sum.plus(line.total!), money("0"));
  const accommodation = costed.trip.stays
    .filter((stay) => stay.currency === currency)
    .reduce((sum, stay) => sum.plus(stayTotal(stay)), money("0"));

  const ownAmounts = Object.values(ownPrices);
  const own = ownAmounts.length
    ? ownAmounts.reduce((sum, amount) => sum.plus(money(amount)), money("0"))
    : null;

  return {
    currency,
    experiences: roundMoney(experiences),
    accommodation: roundMoney(accommodation),
    own: own ? roundMoney(own) : null,
    total: roundMoney(experiences.plus(accommodation).plus(own ?? money("0"))),
  };
}
