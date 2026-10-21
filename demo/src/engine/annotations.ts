/**
 * Notes a consultant writes into the wording of an itinerary line, such as
 * "Game of Thrones Walking Tour (only 4 people)" when two of the party sit
 * one out, or "(15% discount)" when the supplier has agreed one.
 *
 * This parser is deliberately mean, because §9 of the handoff is a list of
 * five silent mispricings and every one of them came from reading a human's
 * free text generously — "2 adults + 1 child" priced at 2, a stray date in a
 * pax column producing a verified €192,470, "1.250" read as €1.25.
 *
 * Two rules keep it honest:
 *
 *   1. It recognises exactly two kinds of note and nothing else. Every
 *      pattern is anchored end to end; a number sitting inside a sentence is
 *      not a party size.
 *   2. If ANY note on a line is not recognised, nothing on that line is
 *      applied and nothing is stripped. Half-understanding a line is worse
 *      than not understanding it: the half it grasped would quietly change
 *      the money while the half it missed disappeared. The wording goes to a
 *      person intact instead.
 *
 * Because an unrecognised note is left in place, it also stops the line
 * matching the catalog — so it reaches a person by the route that already
 * exists, rather than needing one of its own.
 */
import { Decimal } from "./money";

export type Adjustment =
  | { kind: "pax"; pax: number; note: string }
  | { kind: "percent"; factor: string; note: string };

export type Annotated = {
  /** The wording to match against the catalog, with recognised notes removed. */
  name: string;
  adjustments: Adjustment[];
  /** Notes that were left alone. Their presence means nothing was applied. */
  unrecognised: string[];
};

const GROUP = /\(([^()]*)\)/g;

/** At most three digits: a party of four thousand is a typo, not a booking. */
const PAX_PATTERNS = [
  /^only\s+(\d{1,3})$/,
  /^(?:only\s+)?(\d{1,3})\s*(?:people|pax|persons|travellers|travelers|guests)$/,
  /^(\d{1,3})\s*(?:people|pax|persons|travellers|travelers|guests)\s+only$/,
];

/** At most two digits: 100% off is not a discount, it is a comp, and the
 *  engine refuses a total of zero for exactly that reason. */
const DISCOUNT_PATTERNS = [
  /^(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:discount|off)$/,
  /^less\s+(\d{1,2}(?:\.\d{1,2})?)\s*%$/,
];

const SURCHARGE_PATTERNS = [
  /^\+\s*(\d{1,2}(?:\.\d{1,2})?)\s*%$/,
  /^(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:surcharge|supplement)$/,
];

export function parseAnnotations(text: string): Annotated {
  const groups = [...text.matchAll(GROUP)].map((match) => ({
    inner: match[1].trim(),
    start: match.index,
    end: match.index + match[0].length,
  }));

  if (groups.length === 0) return { name: text, adjustments: [], unrecognised: [] };

  const adjustments: Adjustment[] = [];
  const unrecognised: string[] = [];

  for (const group of groups) {
    const adjustment = recognise(group.inner);
    if (adjustment) adjustments.push(adjustment);
    else unrecognised.push(group.inner);
  }

  const paxNotes = adjustments.filter((entry) => entry.kind === "pax").length;
  const percentNotes = adjustments.filter((entry) => entry.kind === "percent").length;

  // Anything unrecognised, or two notes of the same kind arguing with each
  // other, and the line is handed over untouched.
  if (unrecognised.length > 0 || paxNotes > 1 || percentNotes > 1) {
    return { name: text, adjustments: [], unrecognised };
  }

  let name = text;
  for (const group of [...groups].reverse()) {
    name = name.slice(0, group.start) + name.slice(group.end);
  }

  return { name: name.replace(/\s+/g, " ").trim(), adjustments, unrecognised: [] };
}

function recognise(inner: string): Adjustment | null {
  const text = inner.trim().toLowerCase();

  for (const pattern of PAX_PATTERNS) {
    const found = pattern.exec(text);
    if (!found) continue;
    const pax = Number(found[1]);
    if (pax < 1) return null;
    return { kind: "pax", pax, note: `only ${pax} ${pax === 1 ? "person" : "people"}` };
  }

  for (const pattern of DISCOUNT_PATTERNS) {
    const found = pattern.exec(text);
    if (!found) continue;
    return percentAdjustment(found[1], "discount");
  }

  for (const pattern of SURCHARGE_PATTERNS) {
    const found = pattern.exec(text);
    if (!found) continue;
    return percentAdjustment(found[1], "surcharge");
  }

  return null;
}

function percentAdjustment(raw: string, kind: "discount" | "surcharge"): Adjustment | null {
  const percent = new Decimal(raw);
  if (percent.lessThanOrEqualTo(0)) return null;

  const factor =
    kind === "discount"
      ? new Decimal(100).minus(percent).dividedBy(100)
      : new Decimal(100).plus(percent).dividedBy(100);

  return { kind: "percent", factor: factor.toString(), note: `${raw}% ${kind}` };
}
