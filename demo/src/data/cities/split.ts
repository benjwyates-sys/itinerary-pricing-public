import { afternoon, blackout, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Split", country: "Croatia", currency: "EUR", prefix: "HR-SPU" });

export const SPLIT = [
  it(1, "Diocletian's Palace — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "165"], [14, "240"]),
  }),
  it(2, "Diocletian's Palace — Small Group Tour", { pricing: flat("42") }),
  it(3, "Blue Cave & Hvar Speedboat Day Trip", { pricing: tiered([8, "135"], [16, "118"]) }),
  it(4, "Krka Waterfalls Day Trip", {
    pricing: flat("89"),
    modifiers: [season("2026-06-01", "2026-09-15", "12")],
  }),
  it(5, "Marjan Hill Sunset Walk", { pricing: flat("32"), modifiers: [evening("9")] }),
  it(6, "Konoba Dinner & Dalmatian Wine Tasting", {
    pricing: flat("74"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(7, "Private Transfer — Split Airport (SPU) to the Riva", {
    unit: "per_group",
    pricing: tiered([3, "38"], [8, "62"]),
  }),
  it(8, "Private Transfer — the Riva to Split Airport (SPU)", {
    unit: "per_group",
    pricing: tiered([3, "38"], [8, "62"]),
  }),
  it(9, "Salona & Klis Fortress Half Day", { pricing: flat("58") }),
  it(10, "Game of Thrones Filming Locations Walk", { pricing: flat("35") }),
  it(11, "Sea Kayaking — Marjan Peninsula", {
    pricing: flat("46"),
    modifiers: [afternoon("11")],
  }),
  it(12, "Trogir Old Town Walking Tour", { pricing: flat("28") }),
  it(13, "Private Sailing Charter — Full Day", {
    unit: "per_group",
    pricing: flat("1450"),
    modifiers: [blackout("2026-08-15")],
  }),
];
