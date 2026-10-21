import { blackout, city, evening, flat, season, tiered, weekendSurcharge } from "../define";

const it = city({ name: "London", country: "United Kingdom", currency: "GBP", prefix: "GB-LON" });

export const LONDON = [
  it(1, "Tower of London — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "340"], [12, "470"]),
  }),
  it(2, "Tower of London — Small Group Tour", { pricing: flat("78") }),
  it(3, "Westminster Abbey Entry", { pricing: flat("32") }),
  it(4, "Thames Evening River Cruise", { pricing: flat("45"), modifiers: [evening("12")] }),
  it(5, "Windsor Castle Half-Day Trip", { pricing: tiered([8, "105"], [20, "88"]) }),
  it(6, "Private Transfer — Heathrow (LHR) to Mayfair", {
    unit: "per_group",
    pricing: tiered([3, "95"], [8, "140"]),
  }),
  it(7, "West End Theatre — Premium Seats", {
    pricing: flat("145"),
    modifiers: [weekendSurcharge("1.2")],
  }),
  it(8, "Borough Market Food Walk", {
    pricing: flat("68"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(9, "British Museum — Highlights Private Guide", { unit: "per_group", pricing: flat("280") }),
  it(10, "Churchill War Rooms Entry", { pricing: flat("34") }),
  it(11, "Cotswolds Full-Day Trip", {
    pricing: flat("165"),
    modifiers: [season("2026-06-01", "2026-08-31", "18")],
  }),
  it(12, "Greenwich & Royal Observatory Half Day", { pricing: flat("55") }),
  it(13, "Afternoon Tea at a Mayfair Hotel", {
    pricing: flat("95"),
    modifiers: [blackout("2026-12-25")],
  }),
];
