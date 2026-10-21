/**
 * The sample catalog is the bulk of the demo's credibility, so its shape is
 * asserted rather than eyeballed. Every rule here comes from handoff §6.
 *
 * The point of the coverage rules is that a catalog of flat per-person rates
 * would show a tool doing nothing interesting. The range is the evidence.
 */
import { describe, expect, test } from "vitest";
import { CATALOG, CITIES } from "./catalog";
import { normalize } from "../engine/match";
import type { CatalogItem } from "../engine/types";

const inCity = (city: string) => CATALOG.filter((item) => item.city === city);
const tokens = (name: string) => new Set(normalize(name).split(" "));

function jaccard(a: Set<string>, b: Set<string>): number {
  const shared = [...a].filter((token) => b.has(token)).length;
  return shared / (a.size + b.size - shared);
}

describe("cities", () => {
  test("there are fourteen, all European", () => {
    expect(CITIES).toHaveLength(14);
    expect(CITIES.map((c) => c.name)).toEqual([
      "Athens", "Barcelona", "Dubrovnik", "Florence", "Lisbon", "London",
      "Paris", "Porto", "Prague", "Rome", "Santorini", "Seville", "Split", "Venice",
    ]);
  });

  test("each carries the currency its country actually uses", () => {
    const byName = Object.fromEntries(CITIES.map((c) => [c.name, c.currency]));
    expect(byName.London).toBe("GBP");
    expect(byName.Prague).toBe("CZK");
    expect(byName.Rome).toBe("EUR");
  });

  test("every item's currency agrees with its city", () => {
    for (const city of CITIES) {
      for (const item of inCity(city.name)) {
        expect(`${item.name}: ${item.currency}`).toBe(`${item.name}: ${city.currency}`);
      }
    }
  });
});

describe("catalog size", () => {
  test("every city has twelve to fifteen experiences", () => {
    for (const city of CITIES) {
      expect({ city: city.name, count: inCity(city.name).length }).toEqual({
        city: city.name,
        count: expect.any(Number),
      });
      expect(inCity(city.name).length).toBeGreaterThanOrEqual(12);
      expect(inCity(city.name).length).toBeLessThanOrEqual(15);
    }
  });

  test("every id is unique", () => {
    const ids = CATALOG.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("pricing-shape coverage, per city", () => {
  const hasPerGroup = (items: CatalogItem[]) => items.some((i) => i.unit === "per_group");
  const hasTiered = (items: CatalogItem[]) =>
    items.some((i) => i.pricing?.pattern === "tiered_by_pax" && i.pricing.tiers.length >= 2);
  const hasDayPart = (items: CatalogItem[]) =>
    items.some((i) => i.modifiers.some((m) => m.type === "day_part"));

  test("every city has a per-group rate", () => {
    for (const city of CITIES) expect({ [city.name]: hasPerGroup(inCity(city.name)) }).toEqual({ [city.name]: true });
  });

  test("every city has a tiered-by-pax rate with at least two bands", () => {
    for (const city of CITIES) expect({ [city.name]: hasTiered(inCity(city.name)) }).toEqual({ [city.name]: true });
  });

  test("every city has a time-of-day supplement", () => {
    for (const city of CITIES) expect({ [city.name]: hasDayPart(inCity(city.name)) }).toEqual({ [city.name]: true });
  });
});

describe("pricing-shape coverage, across the dataset", () => {
  const withModifier = (type: string) =>
    CATALOG.filter((item) => item.modifiers.some((m) => m.type === type));

  test("at least ten seasonal supplements", () => {
    expect(withModifier("seasonal").length).toBeGreaterThanOrEqual(10);
  });

  test("at least six minimum-billable experiences", () => {
    expect(CATALOG.filter((i) => i.minBillablePax).length).toBeGreaterThanOrEqual(6);
  });

  test("at least six with a blackout date", () => {
    expect(withModifier("blackout").length).toBeGreaterThanOrEqual(6);
  });

  test("at least three multiply modifiers", () => {
    const multipliers = CATALOG.filter((i) => i.modifiers.some((m) => "op" in m && m.op === "multiply"));
    expect(multipliers.length).toBeGreaterThanOrEqual(3);
  });

  test("two or three experiences are deliberately unpriceable", () => {
    const onRequest = CATALOG.filter((item) => !item.pricing);
    expect(onRequest.length).toBeGreaterThanOrEqual(2);
    expect(onRequest.length).toBeLessThanOrEqual(3);
    for (const item of onRequest) expect(item.note).toMatch(/on request/i);
  });
});

describe("naming traps", () => {
  test("every city has a near-identical pair, or the confirm flow has nothing to show", () => {
    for (const city of CITIES) {
      const items = inCity(city.name);
      let found = false;
      for (let i = 0; i < items.length && !found; i += 1) {
        for (let j = i + 1; j < items.length && !found; j += 1) {
          const overlap = jaccard(tokens(items[i].name), tokens(items[j].name));
          if (overlap >= 0.5 && normalize(items[i].name) !== normalize(items[j].name)) found = true;
        }
      }
      expect({ [city.name]: found }).toEqual({ [city.name]: true });
    }
  });

  test("no two experiences normalise to the same name", () => {
    // A genuine duplicate would make the ambiguity guard refuse both forever.
    const seen = new Map<string, string>();
    for (const item of CATALOG) {
      const key = normalize(item.name);
      expect(seen.has(key) ? `${seen.get(key)} vs ${item.name}` : null).toBeNull();
      seen.set(key, item.name);
    }
  });
});

describe("the Dubrovnik items agree with the deck", () => {
  // Ported from samples/build_reference_catalog.py, which is what the
  // stakeholder deck's figures were generated from.
  test("the private Old Town guide is per group, 180 up to six", () => {
    const item = CATALOG.find((i) => i.name === "Old Town Walking Tour — Private Guide")!;
    expect(item.unit).toBe("per_group");
    expect(item.pricing).toEqual({
      pattern: "tiered_by_pax",
      tiers: [{ maxPax: 6, amount: "180" }, { maxPax: 15, amount: "260" }],
    });
  });

  test("the small-group alternative is 45 a head", () => {
    const item = CATALOG.find((i) => i.name === "Old Town Walking Tour — Small Group")!;
    expect(item.unit).toBe("per_person");
    expect(item.pricing).toEqual({ pattern: "flat", amount: "45" });
  });

  test("the yacht charter is blacked out on 15 August", () => {
    const item = CATALOG.find((i) => i.name === "Private Yacht Charter — Full Day")!;
    expect(item.modifiers).toContainEqual({ type: "blackout", dates: ["2026-08-15"] });
  });

  test("the cooking class bills a minimum of four", () => {
    const item = CATALOG.find((i) => i.name.startsWith("Cooking Class — Gruž"))!;
    expect(item.minBillablePax).toBe(4);
  });

  test("sea kayaking carries a PM supplement of 12 on a 48 base", () => {
    const item = CATALOG.find((i) => i.name === "Sea Kayaking — Old Town Walls")!;
    expect(item.pricing).toEqual({ pattern: "flat", amount: "48" });
    expect(item.modifiers).toContainEqual({
      type: "day_part", when: ["PM"], op: "add_per_unit", amount: "12",
    });
  });
});
