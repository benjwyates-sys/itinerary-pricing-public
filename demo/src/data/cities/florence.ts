import { ON_REQUEST, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Florence", country: "Italy", currency: "EUR", prefix: "IT-FLR" });

export const FLORENCE = [
  it(1, "Uffizi Gallery — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "285"], [12, "380"]),
  }),
  it(2, "Uffizi Gallery — Small Group Tour", { pricing: flat("52") }),
  it(3, "Accademia Gallery — Skip the Line", { pricing: flat("34") }),
  it(4, "Duomo Complex — Brunelleschi Pass", { pricing: flat("38") }),
  it(5, "Chianti Wine Tour — Half Day", {
    pricing: tiered([8, "120"], [16, "98"]),
    modifiers: [season("2026-05-15", "2026-09-30", "18")],
  }),
  it(6, "Chianti Wine Tour — Full Day", { pricing: tiered([8, "185"], [16, "158"]) }),
  it(7, "Private Transfer — Florence to Siena", { unit: "per_group", pricing: flat("220") }),
  it(8, "Tuscan Cooking Class — Market & Lunch", {
    pricing: flat("115"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(9, "Oltrarno Artisan Workshops Walk", { pricing: flat("48") }),
  it(10, "Piazzale Michelangelo Sunset Walk", {
    pricing: flat("30"),
    modifiers: [evening("8")],
  }),
  it(11, "Leather School Private Demonstration", { unit: "per_group", pricing: flat("180") }),
  it(12, "Boboli Gardens Entry", { pricing: flat("16") }),
  it(13, "Chef's Table Dinner — Private Villa", { note: ON_REQUEST }),
];
