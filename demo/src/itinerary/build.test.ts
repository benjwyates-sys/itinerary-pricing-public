/**
 * Turning a costed trip into something that reads like an itinerary: one
 * block per day, in the order the day happens, with the hotel, the transfers,
 * the experiences and the gaps between them all in their place.
 *
 * This is presentation structure, not pricing. It never computes a rate-sheet
 * price and never changes one — it arranges what the engine already returned.
 */
import { describe, expect, test } from "vitest";
import { buildItinerary, nightsOf, previewItinerary, stayTotal, tripMoney } from "./build";
import { costTrip } from "../engine/cost";
import { Aliases } from "../engine/match";
import type { CatalogItem, Stay, Trip } from "../engine/types";

const CATALOG: CatalogItem[] = [
  {
    id: "HR-DBV-0007", name: "Private Transfer — Dubrovnik Airport (DBV) to Old Town",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_group",
    pricing: { pattern: "flat", amount: "68" }, modifiers: [],
  },
  {
    id: "HR-DBV-0009", name: "Game of Thrones Walking Tour",
    city: "Dubrovnik", country: "Croatia", currency: "EUR", unit: "per_person",
    pricing: { pattern: "flat", amount: "38" }, modifiers: [],
  },
  {
    id: "HR-SPU-0002", name: "Diocletian's Palace — Small Group Tour",
    city: "Split", country: "Croatia", currency: "EUR", unit: "per_person",
    pricing: { pattern: "flat", amount: "42" }, modifiers: [],
  },
];

const DUBROVNIK: Stay = {
  city: "Dubrovnik", hotel: "Villa Dubrovnik", room: "Sea View Room", rooms: 3,
  checkIn: "2026-06-08", checkOut: "2026-06-10", nightlyRate: "395", currency: "EUR",
};

const SPLIT: Stay = {
  city: "Split", hotel: "Hotel Ambasador", room: "Superior Sea View", rooms: 3,
  checkIn: "2026-06-10", checkOut: "2026-06-12", nightlyRate: "265", currency: "EUR",
};

const trip = (lines: Trip["lines"]): Trip => ({
  id: "t", fileName: "T.xlsx", client: "Test party", title: "Test party — Dalmatia",
  cities: ["Dubrovnik", "Split"], from: "2026-06-08", to: "2026-06-12", pax: 5,
  stays: [DUBROVNIK, SPLIT], lines,
});

const line = (id: string, text: string, date: string, dayPart: Trip["lines"][number]["dayPart"] = null) =>
  ({ id, text, date, pax: 5, dayPart });

const build = (lines: Trip["lines"]) =>
  buildItinerary(costTrip(trip(lines), CATALOG, new Aliases()));

describe("stays", () => {
  test("counts the nights actually charged, not the dates spanned", () => {
    expect(nightsOf(DUBROVNIK)).toBe(2);
  });

  test("totals nights by rooms by rate, exactly", () => {
    // 2 nights x 3 rooms x 395.00
    expect(stayTotal(DUBROVNIK)).toBe("2370.00");
  });

  test("does not lose precision on a fractional nightly rate", () => {
    expect(stayTotal({ ...DUBROVNIK, rooms: 3, nightlyRate: "333.33" })).toBe("1999.98");
  });
});

describe("days", () => {
  test("there is one for every date of the trip, inclusive", () => {
    const days = build([]);
    expect(days.map((day) => day.date)).toEqual([
      "2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12",
    ]);
  });

  test("they are numbered from one", () => {
    expect(build([]).map((day) => day.number)).toEqual([1, 2, 3, 4, 5]);
  });

  test("a day takes its place from the stay covering it", () => {
    const days = build([]);
    expect(days[0].city).toBe("Dubrovnik");
    expect(days[3].city).toBe("Split");
  });

  test("a day that changes hotel reads as a move between two places", () => {
    // 10 June is both the Dubrovnik check-out and the Split check-in.
    const moving = build([])[2];
    expect(moving.city).toBe("Dubrovnik → Split");
    expect(moving.checkOut?.hotel).toBe("Villa Dubrovnik");
    expect(moving.checkIn?.hotel).toBe("Hotel Ambasador");
  });

  test("the last day belongs to the hotel being left", () => {
    const last = build([]).at(-1)!;
    expect(last.city).toBe("Split");
    expect(last.checkOut?.hotel).toBe("Hotel Ambasador");
  });
});

describe("what sits inside a day", () => {
  test("a line lands on its date, in its part of the day", () => {
    const days = build([
      line("l1", "Game of Thrones Walking Tour", "2026-06-09", "AM"),
    ]);
    const slot = days[1].slots.find((entry) => entry.slot === "AM")!;
    expect(slot.lines).toHaveLength(1);
    expect(slot.lines[0].itemName).toBe("Game of Thrones Walking Tour");
  });

  test("slots run morning, afternoon, evening", () => {
    const days = build([
      line("l1", "Game of Thrones Walking Tour", "2026-06-09", "EVENING"),
      line("l2", "Private Transfer — Dubrovnik Airport (DBV) to Old Town", "2026-06-09", "AM"),
    ]);
    expect(days[1].slots.map((entry) => entry.slot)).toEqual(["AM", "PM", "EVENING"]);
  });

  test("a line with no stated time is kept, not dropped or guessed into a slot", () => {
    const days = build([line("l1", "Game of Thrones Walking Tour", "2026-06-09")]);
    expect(days[1].untimed).toHaveLength(1);
    expect(days[1].slots.every((entry) => entry.lines.length === 0)).toBe(true);
  });

  test("an empty half of a booked day reads as free time", () => {
    const days = build([
      line("l1", "Game of Thrones Walking Tour", "2026-06-09", "AM"),
    ]);
    const [morning, afternoon, evening] = days[1].slots;
    expect(morning.free).toBe(false);
    expect(afternoon.free).toBe(true);
    // An empty evening is not worth calling out.
    expect(evening.free).toBe(false);
  });

  test("a day with nothing booked at all is a day at leisure", () => {
    const days = build([
      line("l1", "Game of Thrones Walking Tour", "2026-06-09", "AM"),
    ]);
    expect(days[3].atLeisure).toBe(true);
    expect(days[3].slots.every((entry) => entry.free)).toBe(false);
  });

  test("a day is not at leisure just because its bookings carry no time", () => {
    const days = build([line("l1", "Game of Thrones Walking Tour", "2026-06-11")]);
    expect(days[3].atLeisure).toBe(false);
    expect(days[3].slots.every((entry) => entry.free)).toBe(false);
  });

  test("a day is not at leisure when the party is changing hotels", () => {
    expect(build([])[2].atLeisure).toBe(false);
  });

  test("every costed line appears exactly once across the whole itinerary", () => {
    const lines = [
      line("l1", "Private Transfer — Dubrovnik Airport (DBV) to Old Town", "2026-06-08", "AM"),
      line("l2", "Game of Thrones Walking Tour", "2026-06-09", "PM"),
      line("l3", "Diocletian's Palace — Small Group Tour", "2026-06-11"),
      line("l4", "something nobody can price", "2026-06-12", "AM"),
    ];
    const days = build(lines);
    const placed = days.flatMap((day) => [
      ...day.slots.flatMap((entry) => entry.lines),
      ...day.untimed,
    ]);
    expect(placed.map((entry) => entry.line.id).sort()).toEqual(["l1", "l2", "l3", "l4"]);
  });

  test("a line dated outside the trip is still shown rather than silently dropped", () => {
    const days = build([line("l1", "Game of Thrones Walking Tour", "2026-07-02", "AM")]);
    const placed = days.flatMap((day) => [
      ...day.slots.flatMap((entry) => entry.lines),
      ...day.untimed,
    ]);
    expect(placed.map((entry) => entry.line.id)).toContain("l1");
  });
});

describe("what a trip comes to", () => {
  const costed = costTrip(
    trip([line("l1", "Game of Thrones Walking Tour", "2026-06-09", "AM")]),
    CATALOG,
    new Aliases(),
  );

  test("keeps the rate sheet's money and the hotel's money apart", () => {
    const total = tripMoney(costed, {});
    expect(total.experiences).toBe("190.00"); // 5 x 38.00
    expect(total.accommodation).toBe("3960.00"); // 2370.00 + 1590.00
    expect(total.own).toBeNull();
  });

  test("adds them into one trip total, so the itinerary has a bottom line", () => {
    expect(tripMoney(costed, {}).total).toBe("4150.00");
  });

  test("counts a figure the consultant typed in, and keeps it named", () => {
    const total = tripMoney(costed, { l9: "450.00" });
    expect(total.own).toBe("450.00");
    expect(total.experiences).toBe("190.00");
    expect(total.total).toBe("4600.00");
  });

  test("takes its currency from the priced lines, never from a guess", () => {
    expect(tripMoney(costed, {}).currency).toBe("EUR");
  });
});

describe("the day the party flies home", () => {
  test("does not offer them an afternoon free, because they have gone", () => {
    const days = build([
      line("l1", "Private Transfer — Dubrovnik Airport (DBV) to Old Town", "2026-06-12", "AM"),
    ]);
    const departure = days.at(-1)!;
    expect(departure.date).toBe("2026-06-12");
    expect(departure.slots.every((block) => !block.free)).toBe(true);
  });

  test("but an ordinary day with a single booking still does", () => {
    const days = build([
      line("l1", "Game of Thrones Walking Tour", "2026-06-09", "AM"),
    ]);
    expect(days[1].slots.find((block) => block.slot === "PM")!.free).toBe(true);
  });
});

describe("a price the consultant overrode by hand", () => {
  const costed = costTrip(
    trip([
      line("l1", "Game of Thrones Walking Tour", "2026-06-09", "AM"),
      line("l2", "Diocletian's Palace — Small Group Tour", "2026-06-11", "AM"),
    ]),
    CATALOG,
    new Aliases(),
  );

  test("stops counting as the rate sheet's money", () => {
    // l1 priced at 190.00; overridden to 160.00.
    const total = tripMoney(costed, { l1: "160.00" });
    expect(total.experiences).toBe("210.00"); // l2 alone, 5 x 42.00
    expect(total.own).toBe("160.00");
  });

  test("leaves the trip total right, wherever the money came from", () => {
    const untouched = tripMoney(costed, {});
    const overridden = tripMoney(costed, { l1: "160.00" });
    // 30.00 was taken off one line, and off the trip.
    expect(untouched.total).toBe("4360.00");
    expect(overridden.total).toBe("4330.00");
  });

  test("is not double-counted when several lines are overridden", () => {
    const total = tripMoney(costed, { l1: "160.00", l2: "200.00" });
    expect(total.experiences).toBe("0.00");
    expect(total.own).toBe("360.00");
    expect(total.total).toBe("4320.00"); // 3960.00 of hotel, plus your 360.00
  });
});

describe("the itinerary before anything has been priced", () => {
  const raw = previewItinerary(trip([
    line("l1", "Private Transfer — Dubrovnik Airport (DBV) to Old Town", "2026-06-08", "AM"),
    line("l2", "Old Town walking tour (private)", "2026-06-09", "AM"),
    line("l3", "Bespoke Photography Session", "2026-06-11"),
  ]));

  test("lays out the same days as the costed one", () => {
    expect(raw.map((day) => day.date)).toEqual([
      "2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12",
    ]);
    expect(raw[2].city).toBe("Dubrovnik → Split");
  });

  test("keeps the consultant's own wording, untouched", () => {
    const morning = raw[1].slots.find((block) => block.slot === "AM")!;
    expect(morning.lines[0].text).toBe("Old Town walking tour (private)");
  });

  test("still knows where the party is sleeping", () => {
    expect(raw[0].checkIn?.hotel).toBe("Villa Dubrovnik");
    expect(raw[2].checkOut?.hotel).toBe("Villa Dubrovnik");
  });

  test("marks free time and days at leisure the same way", () => {
    expect(raw[0].slots.find((block) => block.slot === "PM")!.free).toBe(true);
    expect(raw[3].atLeisure).toBe(false);
  });

  test("holds no prices of any kind — that is the point of it", () => {
    const everything = JSON.stringify(raw.map((day) => [...day.slots, ...day.untimed]));
    expect(everything).not.toContain("total");
    expect(everything).not.toContain("status");
  });
});
