import { blackout, city, evening, flat, season, tiered, weekendSurcharge } from "../define";

const it = city({ name: "Prague", country: "Czechia", currency: "CZK", prefix: "CZ-PRG" });

export const PRAGUE = [
  it(1, "Prague Castle — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "4800"], [14, "6900"]),
  }),
  it(2, "Prague Castle — Small Group Tour", { pricing: flat("1150") }),
  it(3, "Old Town & Astronomical Clock Walk", { pricing: flat("680") }),
  it(4, "Vltava River Evening Cruise with Dinner", {
    pricing: flat("1450"),
    modifiers: [evening("280")],
  }),
  it(5, "Jewish Quarter — Guided Visit", { pricing: flat("950") }),
  it(6, "Christmas Markets Evening Walk", {
    pricing: flat("750"),
    modifiers: [season("2026-11-28", "2026-12-23", "220"), evening("180")],
  }),
  it(7, "Private Transfer — Václav Havel (PRG) to the Old Town", {
    unit: "per_group",
    pricing: tiered([3, "950"], [8, "1400"]),
  }),
  it(8, "Kutná Hora & Bone Church Day Trip", { pricing: tiered([8, "2100"], [20, "1750"]) }),
  it(9, "Czech Beer Tasting — Five Breweries", {
    pricing: flat("1250"),
    modifiers: [weekendSurcharge("1.15")],
  }),
  it(10, "Petřín Hill & Lookout Tower", { pricing: flat("420") }),
  it(11, "Klementinum Library & Tower Tour", { pricing: flat("580") }),
  it(12, "Municipal House Concert — Smetana Hall", {
    pricing: flat("1650"),
    modifiers: [blackout("2026-04-24")],
  }),
  it(13, "Bohemian Glass Workshop", {
    pricing: flat("1350"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(14, "Private Transfer — the Old Town to Václav Havel (PRG)", {
    unit: "per_group",
    pricing: tiered([3, "950"], [8, "1400"]),
  }),
];
