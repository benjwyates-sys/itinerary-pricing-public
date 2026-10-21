/**
 * Pricing semantics, ported from `pricing/patterns.py`.
 *
 * Pure functions — no storage, no network, no React. The evaluation order
 * below is load-bearing and is asserted by the ported test suite; changing
 * it changes what the tool quotes.
 *
 * A refusal ("needs a quote") is not an error. It is the engine declining
 * to guess, which is the whole point of the product. It travels back to the
 * caller as a value, so no screen can render a price the engine refused to
 * produce.
 */
import { Decimal, money, roundMoney } from "./money";
import { formatDate } from "../shared/dates";
import type {
  CatalogItem,
  Modifier,
  Op,
  PricingRequest,
  PricingResult,
  Weekday,
} from "./types";

/** Indexed by `Date#getUTCDay()`, which counts from Sunday. */
const DAY_NAMES: Weekday[] = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

/** Thrown internally, caught at the boundary of `evaluate`. Never escapes. */
class NeedsQuote extends Error {
  constructor(public readonly reason: string) {
    super(reason);
  }
}

export function evaluate(item: CatalogItem, request: PricingRequest): PricingResult {
  try {
    return price(item, request);
  } catch (error) {
    if (error instanceof NeedsQuote) return { ok: false, reason: error.reason };
    throw error;
  }
}

function price(item: CatalogItem, request: PricingRequest): PricingResult {
  const modifiers = item.modifiers ?? [];
  checkBlackout(modifiers, request);

  const { rate, lines } = baseRate(item, request);
  let unitRate = rate;
  const applicable = modifiers.filter((mod) => applies(mod, request));

  for (const mod of withOp(applicable, "add_per_unit")) {
    const amount = amountOf(mod);
    unitRate = unitRate.plus(amount);
    lines.push(`+ ${amount} per person (${mod.type})`);
  }

  const units = unitsFor(item, request);
  let subtotal = unitRate.times(units);
  lines.push(`= ${unitRate} x ${units} = ${subtotal}`);

  for (const mod of withOp(applicable, "add_per_booking")) {
    const amount = amountOf(mod);
    subtotal = subtotal.plus(amount);
    lines.push(`+ ${amount} per booking (${mod.type})`);
  }

  for (const mod of withOp(applicable, "multiply")) {
    const factor = amountOf(mod);
    subtotal = subtotal.times(factor);
    lines.push(`x ${factor} (${mod.type})`);
  }

  // The consultant's own adjustments go last, on top of whatever the rate
  // sheet produced — and still before the single rounding, so a discounted
  // line is rounded once rather than twice.
  for (const adjustment of request.adjustments ?? []) {
    const factor = money(adjustment.factor);
    subtotal = subtotal.times(factor);
    lines.push(`x ${factor} (your note: ${adjustment.note})`);
  }

  const total = roundMoney(subtotal);
  if (new Decimal(total).lessThanOrEqualTo(0)) {
    // A zero or negative total is never a real price — it is a placeholder
    // rate, a cleared cell, or a comped item. Writing it into a client's
    // quote reads as "free", and that is a silent mispricing. Refuse, and
    // let a human say which it was.
    throw new NeedsQuote(
      `This priced out to ${total} ${item.currency}. A zero or negative rate ` +
        `needs confirming before it can be quoted. It might be a placeholder, ` +
        `a cleared rate, or a genuinely comped item, but the tool won't guess which.`,
    );
  }

  return { ok: true, total, currency: item.currency, breakdown: lines };
}

function baseRate(
  item: CatalogItem,
  request: PricingRequest,
): { rate: Decimal; lines: string[] } {
  const pricing = item.pricing;
  if (!pricing) {
    throw new NeedsQuote(
      "This experience has no rates mapped yet. It can only be priced by asking the supplier.",
    );
  }

  if (pricing.pattern === "flat") {
    const rate = money(pricing.amount);
    return { rate, lines: [`base ${rate}`] };
  }

  if (pricing.pattern === "tiered_by_pax") {
    const tiers = [...pricing.tiers].sort((a, b) => a.maxPax - b.maxPax);
    if (tiers.length === 0) {
      throw new NeedsQuote(
        "This experience has no rates mapped yet. It can only be priced by asking the supplier.",
      );
    }
    for (const tier of tiers) {
      if (request.pax <= tier.maxPax) {
        const rate = money(tier.amount);
        return { rate, lines: [`base ${rate} (tier <= ${tier.maxPax} pax)`] };
      }
    }
    // Deliberately no extrapolation from the top tier.
    const ceiling = tiers[tiers.length - 1].maxPax;
    throw new NeedsQuote(
      `${request.pax} travellers is above the highest mapped tier (${ceiling} pax). ` +
        `Ask the supplier for a group rate.`,
    );
  }

  throw new NeedsQuote(`unknown pricing pattern ${JSON.stringify((pricing as { pattern: string }).pattern)}`);
}

function unitsFor(item: CatalogItem, request: PricingRequest): number {
  if (item.unit === "per_group") return 1;
  if (item.unit === "per_person") return Math.max(request.pax, item.minBillablePax ?? 0);
  throw new NeedsQuote(`unknown unit ${JSON.stringify(item.unit)}`);
}

function checkBlackout(modifiers: Modifier[], request: PricingRequest): void {
  const blackouts = modifiers.filter((mod) => mod.type === "blackout");
  if (blackouts.length === 0) return;
  if (!request.date) {
    throw new NeedsQuote("This experience has blackout dates, but this line has no date.");
  }
  for (const mod of blackouts) {
    if (mod.dates.includes(request.date)) {
      throw new NeedsQuote(
        `${formatDate(request.date)} is a blackout date for this experience. The supplier doesn't run it that day.`,
      );
    }
  }
}

function applies(mod: Modifier, request: PricingRequest): boolean {
  switch (mod.type) {
    case "blackout":
      return false;

    case "day_part": {
      if (!request.dayPart) {
        throw new NeedsQuote(
          "This experience is priced by time of day, but the itinerary doesn't say whether it is AM or PM.",
        );
      }
      const dayPart = request.dayPart.toUpperCase();
      return mod.when.some((w) => w.toUpperCase() === dayPart);
    }

    case "day_of_week": {
      if (!request.date) {
        throw new NeedsQuote("This experience is priced by day of week, but this line has no date.");
      }
      const day = DAY_NAMES[new Date(`${request.date}T00:00:00Z`).getUTCDay()];
      return mod.when.some((w) => w.toUpperCase() === day);
    }

    case "seasonal": {
      if (!request.date) {
        throw new NeedsQuote("This experience has seasonal rates, but this line has no date.");
      }
      // ISO dates compare correctly as strings; inclusive at both ends.
      return mod.from <= request.date && request.date <= mod.to;
    }

    default:
      throw new NeedsQuote(`unknown modifier type ${JSON.stringify((mod as { type: string }).type)}`);
  }
}

function withOp(modifiers: Modifier[], op: Op): Modifier[] {
  return modifiers.filter((mod) => "op" in mod && mod.op === op);
}

function amountOf(mod: Modifier): Decimal {
  if ("factor" in mod && mod.factor !== undefined) return money(mod.factor);
  if ("amount" in mod && mod.amount !== undefined) return money(mod.amount);
  throw new NeedsQuote(`no rate available for this ${mod.type} supplement`);
}
