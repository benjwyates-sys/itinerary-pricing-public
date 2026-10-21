/**
 * The three sample trips, and the story each one has to tell (handoff §6).
 *
 * Every total here was worked out by hand from the catalog rates and is
 * asserted against the ported evaluator. A demo that shows arithmetic a CEO
 * could check and get a different answer for is worse than no demo.
 */
import { describe, expect, test } from "vitest";
import { CATALOG } from "./catalog";
import { SAMPLE_TRIPS, cleanTrip, demoTrip, hardTrip } from "./trips";
import { costTrip, resolveLine } from "../engine/cost";
import { evaluate } from "../engine/patterns";
import { Decimal } from "../engine/money";
import { Aliases } from "../engine/match";
import { nightsOf, stayTotal } from "../itinerary/build";
import type { CostedTrip } from "../engine/types";

const cost = (trip: Parameters<typeof costTrip>[0], aliases = new Aliases()) =>
  costTrip(trip, CATALOG, aliases);

const sumOfPriced = (costed: CostedTrip) =>
  costed.lines
    .filter((line) => line.status === "priced")
    .reduce((total, line) => total.plus(line.total!), new Decimal(0))
    .toFixed(2);

describe("every sample trip", () => {
  test("there are three of them", () => {
    expect(SAMPLE_TRIPS).toHaveLength(3);
  });

  test("shows a total that is exactly the sum of the lines it priced", () => {
    for (const trip of SAMPLE_TRIPS) {
      const costed = cost(trip);
      expect({ [trip.id]: costed.totals[0].total }).toEqual({ [trip.id]: sumOfPriced(costed) });
    }
  });

  test("stays inside one currency, because there is no exchange rate in this system", () => {
    for (const trip of SAMPLE_TRIPS) {
      expect({ [trip.id]: cost(trip).totals.length }).toEqual({ [trip.id]: 1 });
    }
  });

  test("gives every line a date, so no line refuses merely for want of one", () => {
    for (const trip of SAMPLE_TRIPS) {
      expect(trip.lines.every((line) => line.date !== null)).toBe(true);
    }
  });
});

describe("the clean trip — this is the normal day", () => {
  test("prices with zero questions", () => {
    const costed = cost(cleanTrip);
    expect(costed.counts).toEqual({ priced: 8, needsCheck: 0, needsQuote: 0 });
  });

  test("totals €1,550.00", () => {
    expect(cost(cleanTrip).totals).toEqual([{ currency: "EUR", total: "1550.00" }]);
  });
});

describe("the main demo trip — the one the CEO walks through", () => {
  test("asks three quick checks and sends one line to a supplier", () => {
    expect(cost(demoTrip).counts).toEqual({ priced: 8, needsCheck: 3, needsQuote: 1 });
  });

  test("totals €1,826.25 before anything is confirmed", () => {
    expect(cost(demoTrip).totals).toEqual([{ currency: "EUR", total: "1826.25" }]);
  });

  test("offers both Old Town options, and they are different money for five", () => {
    // §8.6 — the consultant is choosing between amounts, not between catalog
    // entries. A third candidate (Trogir, in Split) is legitimately plausible
    // on a two-city trip; what matters is that both real options are offered
    // with what each would actually cost this party.
    const costed = cost(demoTrip);
    const line = costed.lines.find((l) => l.line.text === "Old Town walking tour (private)")!;
    expect(line.status).toBe("needs_check");

    const offered = line.candidates.map((c) => c.itemId);
    expect(offered).toContain("HR-DBV-0001");
    expect(offered).toContain("HR-DBV-0008");
    expect(offered[0]).toBe("HR-DBV-0001");

    const priceFor = (itemId: string) => {
      const item = CATALOG.find((i) => i.id === itemId)!;
      const result = evaluate(item, { pax: 5, date: "2026-06-09", dayPart: null });
      return result.ok ? result.total : null;
    };
    expect(priceFor("HR-DBV-0001")).toBe("180.00"); // charged once for the group
    expect(priceFor("HR-DBV-0008")).toBe("225.00"); // 5 x 45.00
  });

  test("confirming the private options brings it to €2,721.25", () => {
    const aliases = new Aliases();
    let costed = cost(demoTrip, aliases);
    costed = resolveLine(costed, "d2", "HR-DBV-0001", CATALOG, aliases); // private guide, 180 per group
    costed = resolveLine(costed, "d6", "HR-DBV-0005", CATALOG, aliases); // cooking class, 5 x 110
    costed = resolveLine(costed, "d9", "HR-SPU-0001", CATALOG, aliases); // private palace guide, 165

    expect(costed.counts).toEqual({ priced: 11, needsCheck: 0, needsQuote: 1 });
    expect(costed.totals).toEqual([{ currency: "EUR", total: "2721.25" }]);
  });

  test("re-running it after those confirmations asks nothing", () => {
    const aliases = new Aliases();
    let costed = cost(demoTrip, aliases);
    costed = resolveLine(costed, "d2", "HR-DBV-0001", CATALOG, aliases);
    costed = resolveLine(costed, "d6", "HR-DBV-0005", CATALOG, aliases);
    costed = resolveLine(costed, "d9", "HR-SPU-0001", CATALOG, aliases);

    const rerun = cost(demoTrip, aliases);
    expect(rerun.counts.needsCheck).toBe(0);
    expect(rerun.totals).toEqual([{ currency: "EUR", total: "2721.25" }]);
  });
});

describe("the hard trip — this is what refusing looks like", () => {
  test("refuses a party above the top tier", () => {
    const line = cost(hardTrip).lines.find((l) => l.line.id === "h1")!;
    expect(line.status).toBe("needs_quote");
    expect(line.reason).toContain("above the highest mapped tier");
  });

  test("refuses a blackout date", () => {
    const line = cost(hardTrip).lines.find((l) => l.line.id === "h2")!;
    expect(line.status).toBe("needs_quote");
    expect(line.reason).toContain("blackout");
  });

  test("bills two travellers for the four-person minimum", () => {
    const line = cost(hardTrip).lines.find((l) => l.line.id === "h3")!;
    expect(line.status).toBe("priced");
    expect(line.line.pax).toBe(2);
    expect(line.total).toBe("380.00"); // 4 x 95, not 2 x 95
  });

  test("sends the on-request dinner to a supplier", () => {
    expect(cost(hardTrip).lines.find((l) => l.line.id === "h11")!.status).toBe("needs_quote");
  });

  test("still totals what it could price, and says so", () => {
    const costed = cost(hardTrip);
    expect(costed.counts).toEqual({ priced: 6, needsCheck: 2, needsQuote: 3 });
    expect(costed.totals).toEqual([{ currency: "EUR", total: "4170.00" }]);
  });
});

describe("where the party sleeps", () => {
  test("every trip has a stay covering every one of its nights", () => {
    for (const trip of SAMPLE_TRIPS) {
      const nights = trip.stays.reduce((total, stay) => total + nightsOf(stay), 0);
      const tripNights =
        (Date.parse(`${trip.to}T00:00:00Z`) - Date.parse(`${trip.from}T00:00:00Z`)) / 86_400_000;
      expect({ [trip.id]: nights }).toEqual({ [trip.id]: tripNights });
    }
  });

  test("stays run consecutively, with no gap and no overlap", () => {
    for (const trip of SAMPLE_TRIPS) {
      expect(trip.stays[0].checkIn).toBe(trip.from);
      expect(trip.stays.at(-1)!.checkOut).toBe(trip.to);
      for (let i = 1; i < trip.stays.length; i += 1) {
        expect(trip.stays[i].checkIn).toBe(trip.stays[i - 1].checkOut);
      }
    }
  });

  test("a stay is in the same currency as the experiences around it", () => {
    for (const trip of SAMPLE_TRIPS) {
      const costed = cost(trip);
      for (const stay of trip.stays) {
        expect(stay.currency).toBe(costed.totals[0].currency);
      }
    }
  });

  test("accommodation totals what the nights actually come to", () => {
    // 4 nights x 2 rooms x 480.00
    expect(cleanTrip.stays.map(stayTotal)).toEqual(["3840.00"]);
    // 4 x 3 x 395.00, then 3 x 3 x 265.00
    expect(demoTrip.stays.map(stayTotal)).toEqual(["4740.00", "2385.00"]);
    // 4 x 7 x 430.00, then 2 x 7 x 385.00
    expect(hardTrip.stays.map(stayTotal)).toEqual(["12040.00", "5390.00"]);
  });

  test("every line falls on a day the party is actually somewhere", () => {
    for (const trip of SAMPLE_TRIPS) {
      for (const line of trip.lines) {
        expect({ [line.id]: line.date! >= trip.from && line.date! <= trip.to }).toEqual({
          [line.id]: true,
        });
      }
    }
  });
});

describe("every line says when in the day it happens", () => {
  test("so the itinerary reads as a plan rather than a list", () => {
    for (const trip of SAMPLE_TRIPS) {
      const untimed = trip.lines.filter((line) => line.dayPart === null);
      expect({ [trip.id]: untimed.map((line) => line.id) }).toEqual({ [trip.id]: [] });
    }
  });

  test("the party can get to its first hotel and home again", () => {
    for (const trip of SAMPLE_TRIPS) {
      const transfers = trip.lines.filter((line) => /transfer/i.test(line.text));
      expect({ [trip.id]: transfers.length > 0 }).toEqual({ [trip.id]: true });
    }
  });
});

describe("notes a consultant wrote into a line", () => {
  test("a partial group prices for the people who actually go", () => {
    const line = cost(demoTrip).lines.find((entry) => entry.line.id === "d3")!;
    expect(line.status).toBe("priced");
    expect(line.total).toBe("152.00"); // 4 x 38.00, though five are travelling
    expect(line.adjustments).toEqual([{ kind: "pax", pax: 4, note: "only 4 people" }]);
  });

  test("an agreed discount comes off, and the working is on the line", () => {
    const line = cost(demoTrip).lines.find((entry) => entry.line.id === "d10")!;
    // 89.00 + 12.00 seasonal = 101.00, x 5 = 505.00, less 15% = 429.25
    expect(line.total).toBe("429.25");
    expect(line.breakdown.join(" ")).toContain("15% discount");
  });

  test("a note it cannot read changes nothing and asks a person", () => {
    const line = cost(hardTrip).lines.find((entry) => entry.line.id === "h5")!;
    expect(line.status).toBe("needs_check");
    expect(line.total).toBeNull();
    expect(line.adjustments).toEqual([]);
  });

  test("and the note it cannot read is still there for the person to read", () => {
    const line = cost(hardTrip).lines.find((entry) => entry.line.id === "h5")!;
    expect(line.line.text).toContain("check with Marco");
  });
});
