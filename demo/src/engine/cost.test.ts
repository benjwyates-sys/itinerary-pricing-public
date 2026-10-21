/**
 * Costing a whole trip: match each line, price what matches unambiguously,
 * and route everything else to the right kind of human attention.
 *
 * The two kinds are deliberately not merged (handoff §8.5): "which
 * experience did you mean?" is a ten-second pick, "the supplier doesn't sail
 * that day" is an email. A single list trains people to skim both.
 */
import { describe, expect, test } from "vitest";
import { costTrip, resolveLine } from "./cost";
import { Aliases } from "./match";
import type { CatalogItem, Trip } from "./types";

const CATALOG: CatalogItem[] = [
  {
    id: "HR-DBV-0001", name: "Old Town Walking Tour — Private Guide",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_group",
    pricing: { pattern: "tiered_by_pax", tiers: [{ maxPax: 6, amount: "180" }, { maxPax: 15, amount: "260" }] },
    modifiers: [],
  },
  {
    id: "HR-DBV-0008", name: "Old Town Walking Tour — Small Group",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_person",
    pricing: { pattern: "flat", amount: "45" }, modifiers: [],
  },
  {
    id: "HR-DBV-0009", name: "Game of Thrones Walking Tour",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_person",
    pricing: { pattern: "flat", amount: "38" }, modifiers: [],
  },
  {
    id: "HR-DBV-0013", name: "Private Yacht Charter — Full Day",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_group",
    pricing: { pattern: "flat", amount: "1850" },
    modifiers: [{ type: "blackout", dates: ["2026-08-15"] }],
  },
  {
    id: "HR-DBV-0005", name: "Cooking Class — Gruž Market & Lunch",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_person",
    pricing: { pattern: "flat", amount: "110" }, modifiers: [], minBillablePax: 4,
  },
  {
    id: "HR-DBV-0012", name: "Bespoke Photography Session",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_person",
    modifiers: [], note: "on request",
  },
];

const trip = (lines: Trip["lines"]): Trip => ({
  id: "trip-test", fileName: "Trip_Test.xlsx", client: "Test party",
  title: "Test party — Dubrovnik", cities: ["Dubrovnik"],
  from: "2026-06-08", to: "2026-06-12", pax: 5, stays: [], lines,
});

const line = (id: string, text: string, over: Partial<Trip["lines"][number]> = {}) => ({
  id, text, date: "2026-06-09", pax: 5, dayPart: null, ...over,
});

describe("costTrip", () => {
  test("prices a line whose wording matches the catalog exactly", () => {
    const costed = costTrip(trip([line("l1", "Game of Thrones Walking Tour")]), CATALOG, new Aliases());
    expect(costed.lines[0].status).toBe("priced");
    expect(costed.lines[0].total).toBe("190.00");
  });

  test("asks about a line that is close but not identical", () => {
    const costed = costTrip(trip([line("l1", "Old Town walking tour (private)")]), CATALOG, new Aliases());
    const [only] = costed.lines;
    expect(only.status).toBe("needs_check");
    expect(only.total).toBeNull();
    expect(only.candidates.map((c) => c.itemId)).toContain("HR-DBV-0001");
  });

  test("sends a refused match to the supplier-quote group, not the check group", () => {
    const costed = costTrip(
      trip([line("l1", "Private Yacht Charter — Full Day", { date: "2026-08-15" })]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].status).toBe("needs_quote");
    expect(costed.lines[0].reason).toContain("blackout");
  });

  test("sends an on-request experience to the supplier-quote group", () => {
    const costed = costTrip(trip([line("l1", "Bespoke Photography Session")]), CATALOG, new Aliases());
    expect(costed.lines[0].status).toBe("needs_quote");
  });

  test("never reports a total for a line it could not price", () => {
    const costed = costTrip(
      trip([
        line("l1", "Old Town walking tour (private)"),
        line("l2", "Bespoke Photography Session"),
      ]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines.every((l) => l.status === "priced" || l.total === null)).toBe(true);
  });

  test("totals only the lines it actually priced", () => {
    const costed = costTrip(
      trip([
        line("l1", "Game of Thrones Walking Tour"),        // 5 x 38 = 190
        line("l2", "Old Town Walking Tour — Small Group"), // 5 x 45 = 225
        line("l3", "Bespoke Photography Session"),         // no price
      ]),
      CATALOG, new Aliases(),
    );
    expect(costed.totals).toEqual([{ currency: "EUR", total: "415.00" }]);
  });

  test("keeps currencies apart rather than adding them together", () => {
    const withGbp: CatalogItem[] = [
      ...CATALOG,
      {
        id: "GB-LON-0001", name: "Tower of London — Private Guide",
        city: "London", country: "United Kingdom", currency: "GBP", unit: "per_group",
        pricing: { pattern: "flat", amount: "300" }, modifiers: [],
      },
    ];
    const costed = costTrip(
      { ...trip([
        line("l1", "Game of Thrones Walking Tour"),
        line("l2", "Tower of London — Private Guide"),
      ]), cities: ["Dubrovnik", "London"] },
      withGbp, new Aliases(),
    );
    expect(costed.totals).toEqual([
      { currency: "EUR", total: "190.00" },
      { currency: "GBP", total: "300.00" },
    ]);
  });

  test("counts each kind of attention separately", () => {
    const costed = costTrip(
      trip([
        line("l1", "Game of Thrones Walking Tour"),
        line("l2", "Old Town walking tour (private)"),
        line("l3", "Bespoke Photography Session"),
      ]),
      CATALOG, new Aliases(),
    );
    expect(costed.counts).toEqual({ priced: 1, needsCheck: 1, needsQuote: 1 });
  });

  test("a saved alias means the same trip asks nothing the second time", () => {
    const aliases = new Aliases();
    const asked = costTrip(trip([line("l1", "Old Town walking tour (private)")]), CATALOG, aliases);
    expect(asked.lines[0].status).toBe("needs_check");

    aliases.add("Old Town walking tour (private)", "HR-DBV-0001");

    const again = costTrip(trip([line("l1", "Old Town walking tour (private)")]), CATALOG, aliases);
    expect(again.lines[0].status).toBe("priced");
    expect(again.lines[0].total).toBe("180.00"); // per group, not per person
  });
});

describe("notes the consultant wrote into a line", () => {
  test("prices for the party size the note gives, not the trip's", () => {
    const costed = costTrip(
      trip([line("l1", "Game of Thrones Walking Tour (only 4 people)")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].status).toBe("priced");
    expect(costed.lines[0].total).toBe("152.00"); // 4 x 38.00, not 5
  });

  test("takes an agreed discount off, and shows the working", () => {
    const costed = costTrip(
      trip([line("l1", "Game of Thrones Walking Tour (15% discount)")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].total).toBe("161.50"); // 5 x 38.00, less 15%
    expect(costed.lines[0].breakdown.join(" ")).toContain("15% discount");
  });

  test("reports what it applied, so a screen can say so", () => {
    const costed = costTrip(
      trip([line("l1", "Game of Thrones Walking Tour (only 4 people)")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].adjustments).toEqual([
      { kind: "pax", pax: 4, note: "only 4 people" },
    ]);
  });

  test("reports the note it could not read, so a screen can explain itself", () => {
    const costed = costTrip(
      trip([line("l1", "Game of Thrones Walking Tour (check with Marco)")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].unreadNotes).toEqual(["check with Marco"]);
  });

  test("reports nothing unread when every note was understood", () => {
    const costed = costTrip(
      trip([line("l1", "Game of Thrones Walking Tour (only 4 people)")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].unreadNotes).toEqual([]);
  });

  test("a note it does not recognise stops the line instead of changing it", () => {
    const costed = costTrip(
      trip([line("l1", "Game of Thrones Walking Tour (check with Marco)")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].status).toBe("needs_check");
    expect(costed.lines[0].total).toBeNull();
  });

  test("a wording confirmed once covers the same experience at any party size", () => {
    const aliases = new Aliases();
    const first = costTrip(
      trip([line("l1", "GoT walking tour (only 4 people)")]),
      CATALOG, aliases,
    );
    expect(first.lines[0].status).toBe("needs_check");

    const resolved = resolveLine(first, "l1", "HR-DBV-0009", CATALOG, aliases);
    expect(resolved.lines[0].total).toBe("152.00");

    // A different party size, same wording — nothing to ask about.
    const later = costTrip(
      trip([line("l2", "GoT walking tour (only 2 people)")]),
      CATALOG, aliases,
    );
    expect(later.lines[0].status).toBe("priced");
    expect(later.lines[0].total).toBe("76.00"); // 2 x 38.00
  });
});

describe("a priced line carries enough to describe itself", () => {
  test("reports how the rate is charged, so a party of one is not called a group", () => {
    const solo = costTrip(
      { ...trip([line("l1", "Game of Thrones Walking Tour", { pax: 1 })]), pax: 1 },
      CATALOG, new Aliases(),
    );
    expect(solo.lines[0].unit).toBe("per_person");
    expect(solo.lines[0].total).toBe("38.00");

    const group = costTrip(
      trip([line("l1", "Old Town Walking Tour — Private Guide")]),
      CATALOG, new Aliases(),
    );
    expect(group.lines[0].unit).toBe("per_group");
  });

  test("reports the billable floor when one applies", () => {
    const costed = costTrip(
      trip([line("l1", "Cooking Class — Gruž Market & Lunch", { pax: 2 })]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].minBillablePax).toBe(4);
  });

  test("leaves them empty when nothing was matched", () => {
    const costed = costTrip(
      trip([line("l1", "Old Town walking tour (private)")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].unit).toBeNull();
    expect(costed.lines[0].minBillablePax).toBeNull();
  });
});

describe("what the confirm modal is offered", () => {
  test("does not offer a candidate that shares no wording with the line", () => {
    // Ranking returns a best-three whatever their score, so without this the
    // modal pads itself with unrelated experiences. The consultant is asked
    // "which of these did you mean?" — an option she plainly did not mean is
    // noise, and "Neither" already covers the case where none of them fit.
    const costed = costTrip(
      trip([line("l1", "Cooking class at Gruž market")]),
      CATALOG, new Aliases(),
    );
    const offered = costed.lines[0].candidates.map((c) => c.name);
    expect(offered).not.toContain("Private Yacht Charter — Full Day");
    expect(offered).not.toContain("Game of Thrones Walking Tour");
  });

  test("still offers something to choose from when nothing shares a word", () => {
    const costed = costTrip(
      trip([line("l1", "Helicopter to the villa")]),
      CATALOG, new Aliases(),
    );
    expect(costed.lines[0].status).toBe("needs_check");
    expect(costed.lines[0].candidates.length).toBeGreaterThanOrEqual(1);
  });

  test("offers every real alternative, not just the first three ranked overall", () => {
    const costed = costTrip(
      trip([line("l1", "Old Town walking tour (private)")]),
      CATALOG, new Aliases(),
    );
    const offered = costed.lines[0].candidates.map((c) => c.itemId);
    expect(offered).toContain("HR-DBV-0001");
    expect(offered).toContain("HR-DBV-0008");
  });
});

describe("matching is scoped to the cities the trip visits", () => {
  // The real engine maps one region at a time, so a Dubrovnik itinerary is
  // never offered a Split experience. Without this, ranking pulls in
  // same-sounding tours from cities the party is nowhere near.
  const withSplit: CatalogItem[] = [
    ...CATALOG,
    {
      id: "HR-SPU-0012", name: "Trogir Old Town Walking Tour",
      city: "Split", country: "Croatia", currency: "EUR", unit: "per_person",
      pricing: { pattern: "flat", amount: "28" }, modifiers: [],
    },
  ];

  test("does not offer a candidate from a city the trip never visits", () => {
    const costed = costTrip(
      trip([line("l1", "Old Town walking tour (private)")]),
      withSplit, new Aliases(),
    );
    expect(costed.lines[0].candidates.map((c) => c.itemId)).not.toContain("HR-SPU-0012");
  });

  test("offers candidates from every city the trip does visit", () => {
    const costed = costTrip(
      { ...trip([line("l1", "Old Town walking tour (private)")]), cities: ["Dubrovnik", "Split"] },
      withSplit, new Aliases(),
    );
    expect(costed.lines[0].candidates.map((c) => c.itemId)).toContain("HR-SPU-0012");
  });
});

describe("resolveLine", () => {
  test("confirming a candidate saves the wording and prices the line", () => {
    const aliases = new Aliases();
    const costed = costTrip(trip([line("l1", "Old Town walking tour (private)")]), CATALOG, aliases);

    const next = resolveLine(costed, "l1", "HR-DBV-0001", CATALOG, aliases);

    expect(next.lines[0].status).toBe("priced");
    expect(next.lines[0].total).toBe("180.00");
    expect(aliases.lookup("Old Town walking tour (private)")).toBe("HR-DBV-0001");
  });

  test("choosing 'neither' sends the line for a supplier quote and saves no alias", () => {
    const aliases = new Aliases();
    const costed = costTrip(trip([line("l1", "Old Town walking tour (private)")]), CATALOG, aliases);

    const next = resolveLine(costed, "l1", null, CATALOG, aliases);

    expect(next.lines[0].status).toBe("needs_quote");
    expect(aliases.lookup("Old Town walking tour (private)")).toBeNull();
  });

  test("confirming a candidate the engine then refuses does not invent a price", () => {
    const aliases = new Aliases();
    const costed = costTrip(
      trip([line("l1", "yacht charter, full day", { date: "2026-08-15" })]),
      CATALOG, aliases,
    );
    expect(costed.lines[0].status).toBe("needs_check");

    const next = resolveLine(costed, "l1", "HR-DBV-0013", CATALOG, aliases);

    expect(next.lines[0].status).toBe("needs_quote");
    expect(next.lines[0].total).toBeNull();
  });
});
