/**
 * Costing a whole trip: match each line, price what matches unambiguously,
 * and route the rest to the right kind of human attention.
 *
 * The routing is the product. A line lands in exactly one of three places:
 *
 *   priced       nothing needed from anyone
 *   needs_check  two things could be meant, and they cost different money
 *   needs_quote  the engine refused, or there is no rate to refuse from
 *
 * "needs_check" and "needs_quote" are never merged into one list. One is a
 * ten-second pick; the other is an email to a supplier. Putting them
 * together trains a consultant to skim both.
 */
import { Decimal, roundMoney } from "./money";
import { parseAnnotations, type Annotated } from "./annotations";
import { Aliases, candidates, normalize } from "./match";
import { evaluate } from "./patterns";
import type {
  CatalogItem,
  CostedLine,
  CostedTrip,
  Currency,
  Trip,
  TripLine,
} from "./types";

export function costTrip(trip: Trip, catalog: CatalogItem[], aliases: Aliases): CostedTrip {
  const scoped = inCities(catalog, trip.cities);
  const lines = trip.lines.map((line) => costLine(line, scoped, aliases));
  return summarise(trip, lines);
}

/**
 * The real engine maps one region at a time, so an itinerary is only ever
 * matched against the rate sheets for the places the party actually goes.
 * Without this, ranking happily offers a same-sounding tour in a city three
 * hundred miles away — noise in the confirm modal, and a worse pick on offer
 * than the right one.
 */
function inCities(catalog: CatalogItem[], cities: string[]): CatalogItem[] {
  if (cities.length === 0) return catalog;
  return catalog.filter((item) => cities.includes(item.city));
}

/**
 * Record the consultant's decision about one line and re-cost it.
 * `itemId` of null means "neither of these" — the line goes for a supplier
 * quote, and nothing is remembered, because nothing was confirmed.
 */
export function resolveLine(
  costed: CostedTrip,
  lineId: string,
  itemId: string | null,
  catalog: CatalogItem[],
  aliases: Aliases,
): CostedTrip {
  const lines = costed.lines.map((costedLine) => {
    if (costedLine.line.id !== lineId) return costedLine;

    if (itemId === null) {
      return {
        ...costedLine,
        status: "needs_quote" as const,
        total: null,
        currency: null,
        breakdown: [],
        unit: null,
        minBillablePax: null,
        adjustments: [],
        reason: "Marked as something the rate sheet doesn't cover. It needs a supplier quote.",
      };
    }

    const item = catalog.find((candidate) => candidate.id === itemId);
    if (!item) return costedLine;

    const annotated = parseAnnotations(costedLine.line.text);
    aliases.add(annotated.name, item.id);
    return priceAgainst(costedLine.line, item, costedLine.candidates, annotated);
  });

  return summarise(costed.trip, lines);
}

const OFFERED = 3;

function costLine(line: TripLine, catalog: CatalogItem[], aliases: Aliases): CostedLine {
  // Notes the consultant wrote are lifted off the wording before matching —
  // but only ones the parser positively recognises. An unrecognised note is
  // left in place, which stops the line matching and sends it to a person.
  const annotated = parseAnnotations(line.text);

  // Ask for more than will be shown, so the relevance filter below has room
  // to work rather than simply shortening the list.
  const found = candidates(annotated.name, catalog, aliases, OFFERED * 4);
  const best = found[0];

  // Exact normalised name, or a wording already confirmed. Nothing else.
  if (best?.autoAccept) {
    const item = catalog.find((candidate) => candidate.id === best.itemId);
    if (item) {
      return priceAgainst(line, item, relevantTo(annotated.name, found), annotated);
    }
  }

  return {
    line,
    status: "needs_check",
    total: null,
    currency: null,
    itemId: null,
    itemName: null,
    unit: null,
    minBillablePax: null,
    breakdown: [],
    candidates: relevantTo(annotated.name, found),
    reason: null,
    adjustments: annotated.adjustments,
    unreadNotes: annotated.unrecognised,
  };
}

/**
 * Trim the ranked list to what is worth putting in front of a person.
 *
 * Ranking returns a best-N whatever their scores, so an obscure line pads its
 * list with experiences that share nothing with it — and being asked "which of
 * these did you mean?" about an experience you plainly did not mean is noise.
 *
 * This keeps only candidates sharing at least one word with the consultant's
 * own wording. It is a rule about what to DISPLAY, not a threshold that
 * decides anything: auto-accept is settled before this runs and never consults
 * the list, so no price can turn on it. Where nothing shares a word, the best
 * guess is still offered, and "Neither" covers the rest.
 */
function relevantTo(text: string, found: CostedLine["candidates"]): CostedLine["candidates"] {
  const words = new Set(normalize(text).split(" ").filter(Boolean));
  const sharing = found.filter((candidate) =>
    normalize(candidate.name).split(" ").some((word) => words.has(word)),
  );
  return (sharing.length > 0 ? sharing : found.slice(0, 1)).slice(0, OFFERED);
}

function priceAgainst(
  line: TripLine,
  item: CatalogItem,
  fallback: CostedLine["candidates"],
  annotated: Annotated,
): CostedLine {
  const { adjustments } = annotated;
  // A party-size note replaces the line's own count; a percentage rides with
  // the engine's multiply step so the result is still rounded exactly once.
  const pax = adjustments.find((entry) => entry.kind === "pax")?.pax ?? line.pax;
  const factors = adjustments
    .filter((entry) => entry.kind === "percent")
    .map((entry) => ({ factor: entry.factor, note: entry.note }));

  const result = evaluate(item, {
    pax,
    date: line.date,
    dayPart: line.dayPart,
    adjustments: factors,
  });

  if (result.ok) {
    return {
      line,
      status: "priced",
      total: result.total,
      currency: result.currency,
      itemId: item.id,
      itemName: item.name,
      unit: item.unit,
      minBillablePax: item.minBillablePax ?? null,
      breakdown: result.breakdown,
      candidates: [],
      reason: null,
      adjustments,
      unreadNotes: annotated.unrecognised,
    };
  }

  return {
    line,
    status: "needs_quote",
    total: null,
    currency: null,
    itemId: item.id,
    itemName: item.name,
    unit: item.unit,
    minBillablePax: item.minBillablePax ?? null,
    breakdown: [],
    candidates: fallback,
    reason: result.reason,
    adjustments,
    unreadNotes: annotated.unrecognised,
  };
}

function summarise(trip: Trip, lines: CostedLine[]): CostedTrip {
  // Currencies are never added together. There is no exchange rate in this
  // system, and inventing one would be exactly the kind of quiet guess the
  // rest of the engine exists to refuse.
  const sums = new Map<Currency, Decimal>();
  for (const line of lines) {
    if (line.status !== "priced" || !line.currency || !line.total) continue;
    sums.set(line.currency, (sums.get(line.currency) ?? new Decimal(0)).plus(line.total));
  }

  const totals = [...sums.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([currency, sum]) => ({ currency, total: roundMoney(sum) }));

  return {
    trip,
    lines,
    totals,
    counts: {
      priced: lines.filter((line) => line.status === "priced").length,
      needsCheck: lines.filter((line) => line.status === "needs_check").length,
      needsQuote: lines.filter((line) => line.status === "needs_quote").length,
    },
  };
}
