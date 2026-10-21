/**
 * Ported from `tests/test_patterns.py`, case for case.
 *
 * The expected totals are the Python suite's hand-verified figures. If this
 * evaluator disagrees with any of them, this evaluator is wrong — these
 * numbers are the only guarantee that what the demo shows a CEO is what the
 * real engine would have quoted.
 *
 * The one structural change is the handoff's: rates are literal `amount`
 * strings rather than cell references into a workbook, so the `rates` map
 * the Python signature takes has no counterpart here.
 */
import { describe, expect, test } from "vitest";
import { evaluate } from "./patterns";
import type { CatalogItem, PricingResult } from "./types";

const anItem = (over: Partial<CatalogItem>): CatalogItem => ({
  id: "XX-TST-0001",
  name: "Test experience",
  city: "Rome",
  country: "Italy",
  currency: "EUR",
  unit: "per_person",
  pricing: { pattern: "flat", amount: "100" },
  modifiers: [],
  ...over,
});

function priced(result: PricingResult) {
  if (!result.ok) throw new Error(`expected a price, got a refusal: ${result.reason}`);
  return result;
}

function refused(result: PricingResult) {
  if (result.ok) throw new Error(`expected a refusal, got ${result.total}`);
  return result;
}

/** tests/test_patterns.py::UFFIZI */
const UFFIZI = anItem({
  id: "IT-FLR-0032",
  unit: "per_person",
  pricing: {
    pattern: "tiered_by_pax",
    tiers: [
      { maxPax: 4, amount: "285" },
      { maxPax: 10, amount: "240" },
    ],
  },
  modifiers: [{ type: "day_part", when: ["PM"], op: "add_per_unit", amount: "40" }],
});

describe("tiered pricing", () => {
  test("picks the right bracket", () => {
    const result = priced(evaluate(UFFIZI, { pax: 4, dayPart: "AM" }));
    expect(result.total).toBe("1140.00");
    expect(result.currency).toBe("EUR");
  });

  test("higher pax uses the cheaper tier", () => {
    expect(priced(evaluate(UFFIZI, { pax: 6, dayPart: "AM" })).total).toBe("1440.00");
  });

  test("pax above the top tier needs a quote", () => {
    const result = refused(evaluate(UFFIZI, { pax: 14, dayPart: "AM" }));
    expect(result.reason).toContain("14");
    expect(result.reason).toContain("10");
  });

  test("an unmapped tier list needs a quote", () => {
    const item = anItem({ pricing: { pattern: "tiered_by_pax", tiers: [] } });
    const result = refused(evaluate(item, { pax: 2 }));
    expect(result.reason.toLowerCase()).toContain("no rates mapped");
  });
});

describe("modifiers", () => {
  test("a day-part supplement is added per person", () => {
    // (285 + 40) * 4
    expect(priced(evaluate(UFFIZI, { pax: 4, dayPart: "PM" })).total).toBe("1300.00");
  });

  test("a missing day part needs a quote when a supplement exists", () => {
    const result = refused(evaluate(UFFIZI, { pax: 4, dayPart: null }));
    expect(result.reason.toLowerCase()).toContain("time of day");
  });

  test("a weekend multiplier applies to the subtotal, not the unit rate", () => {
    const item = anItem({
      modifiers: [
        { type: "day_of_week", when: ["SAT", "SUN"], op: "multiply", factor: "1.15" },
      ],
    });
    const saturday = "2026-06-20";
    expect(priced(evaluate(item, { pax: 2, date: saturday })).total).toBe("230.00");
  });

  test("a day-of-week rule needs a date", () => {
    const item = anItem({
      modifiers: [
        { type: "day_of_week", when: ["SAT"], op: "multiply", factor: "1.15" },
      ],
    });
    expect(refused(evaluate(item, { pax: 2, date: null })).reason.toLowerCase()).toContain("date");
  });

  test("a seasonal modifier needs a date", () => {
    const item = anItem({
      modifiers: [
        {
          type: "seasonal",
          from: "2026-06-01",
          to: "2026-08-31",
          op: "add_per_unit",
          amount: "20",
        },
      ],
    });
    expect(refused(evaluate(item, { pax: 2, date: null })).reason.toLowerCase()).toContain("date");
  });

  test("a seasonal window is inclusive at both ends", () => {
    const item = anItem({
      modifiers: [
        {
          type: "seasonal",
          from: "2026-06-01",
          to: "2026-08-31",
          op: "add_per_unit",
          amount: "20",
        },
      ],
    });
    expect(priced(evaluate(item, { pax: 1, date: "2026-06-01" })).total).toBe("120.00");
    expect(priced(evaluate(item, { pax: 1, date: "2026-08-31" })).total).toBe("120.00");
    expect(priced(evaluate(item, { pax: 1, date: "2026-09-01" })).total).toBe("100.00");
  });
});

describe("units", () => {
  test("a per-group rate does not multiply by pax", () => {
    const transfer = anItem({
      unit: "per_group",
      pricing: { pattern: "flat", amount: "110" },
    });
    expect(priced(evaluate(transfer, { pax: 3 })).total).toBe("110.00");
  });

  test("a minimum billable pax raises the floor", () => {
    const cookingClass = anItem({
      unit: "per_person",
      minBillablePax: 6,
      pricing: { pattern: "flat", amount: "50" },
    });
    // billed for 6, not 2
    expect(priced(evaluate(cookingClass, { pax: 2 })).total).toBe("300.00");
  });

  test("an unrecognised unit needs a quote", () => {
    const item = anItem({ unit: "per_prson" as CatalogItem["unit"] });
    expect(refused(evaluate(item, { pax: 2 })).reason).toContain("per_prson");
  });
});

describe("blackouts", () => {
  test("a blackout date needs a quote", () => {
    const item = anItem({ modifiers: [{ type: "blackout", dates: ["2026-12-25"] }] });
    const result = refused(evaluate(item, { pax: 2, date: "2026-12-25" }));
    expect(result.reason.toLowerCase()).toContain("blackout");
  });

  test("a blackout item with no date at all needs a quote", () => {
    const item = anItem({ modifiers: [{ type: "blackout", dates: ["2026-12-25"] }] });
    expect(refused(evaluate(item, { pax: 2, date: null })).reason.toLowerCase()).toContain("date");
  });
});

describe("rounding", () => {
  test("happens once, at the end", () => {
    const item = anItem({
      pricing: { pattern: "flat", amount: "33.33" },
      modifiers: [
        { type: "day_of_week", when: ["MON"], op: "multiply", factor: "1.005" },
      ],
    });
    const monday = "2026-06-15";
    // 33.33 * 3 = 99.99 -> * 1.005 = 100.48995 -> 100.49
    expect(priced(evaluate(item, { pax: 3, date: monday })).total).toBe("100.49");
  });
});

describe("a non-positive total is never a price", () => {
  const monday = "2026-06-15";

  test("a zero multiplier needs a quote", () => {
    const item = anItem({
      modifiers: [{ type: "day_of_week", when: ["MON"], op: "multiply", factor: "0" }],
    });
    expect(refused(evaluate(item, { pax: 2, date: monday })).reason).toContain("0");
  });

  test("a zero rate needs a quote", () => {
    const item = anItem({ pricing: { pattern: "flat", amount: "0" } });
    expect(refused(evaluate(item, { pax: 4 })).reason).toContain("0");
  });

  test("a negative rate needs a quote", () => {
    const item = anItem({ pricing: { pattern: "flat", amount: "-50" } });
    expect(refused(evaluate(item, { pax: 4 })).reason).toContain("-200");
  });

  test("a negative total from a negative per-booking amount needs a quote", () => {
    // The guard is on the final total, not on any one input.
    const item = anItem({
      pricing: { pattern: "flat", amount: "10" },
      modifiers: [
        { type: "day_of_week", when: ["MON"], op: "add_per_booking", amount: "-100" },
      ],
    });
    expect(refused(evaluate(item, { pax: 2, date: monday })).ok).toBe(false);
  });

  test("a pax of zero needs a quote", () => {
    expect(refused(evaluate(anItem({}), { pax: 0 })).ok).toBe(false);
  });
});

describe("an on-request experience", () => {
  test("has no pricing and needs a supplier quote", () => {
    const item = anItem({ pricing: undefined, note: "on request" });
    expect(refused(evaluate(item, { pax: 2 })).reason.toLowerCase()).toContain("no rates mapped");
  });
});

describe("the breakdown", () => {
  test("explains the arithmetic", () => {
    const joined = priced(evaluate(UFFIZI, { pax: 4, dayPart: "PM" })).breakdown.join(" ");
    expect(joined).toContain("285");
    expect(joined).toContain("40");
    expect(joined).toContain("4");
  });
});

describe("a consultant's own adjustment", () => {
  /**
   * An addition to the engine's INPUT, not to the catalog model — the shape
   * in `pricing/catalog.py` is untouched. It rides with the multiply step so
   * that rounding still happens exactly once and the non-positive guard still
   * governs the result.
   */
  test("multiplies the subtotal", () => {
    const item = anItem({ pricing: { pattern: "flat", amount: "100" } });
    const result = priced(
      evaluate(item, { pax: 5, adjustments: [{ factor: "0.85", note: "15% discount" }] }),
    );
    expect(result.total).toBe("425.00");
  });

  test("applies after the rate sheet's own multipliers, and rounds once", () => {
    const item = anItem({
      pricing: { pattern: "flat", amount: "33.33" },
      modifiers: [
        { type: "day_of_week", when: ["MON"], op: "multiply", factor: "1.005" },
      ],
    });
    // 33.33 x 3 = 99.99 -> x 1.005 = 100.48995 -> x 0.85 = 85.4164575 -> 85.42
    const result = priced(
      evaluate(item, {
        pax: 3,
        date: "2026-06-15",
        adjustments: [{ factor: "0.85", note: "15% discount" }],
      }),
    );
    expect(result.total).toBe("85.42");
  });

  test("cannot discount a line to nothing", () => {
    const item = anItem({ pricing: { pattern: "flat", amount: "100" } });
    const result = refused(
      evaluate(item, { pax: 5, adjustments: [{ factor: "0", note: "100% discount" }] }),
    );
    expect(result.reason).toContain("0");
  });

  test("is named in the breakdown, so the arithmetic can be followed", () => {
    const item = anItem({ pricing: { pattern: "flat", amount: "100" } });
    const result = priced(
      evaluate(item, { pax: 5, adjustments: [{ factor: "0.85", note: "15% discount" }] }),
    );
    expect(result.breakdown.join(" ")).toContain("15% discount");
  });

  test("changes nothing when there is none", () => {
    const item = anItem({ pricing: { pattern: "flat", amount: "100" } });
    expect(priced(evaluate(item, { pax: 5, adjustments: [] })).total).toBe("500.00");
  });
});
