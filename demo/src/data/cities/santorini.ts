import { blackout, city, evening, flat, season, tiered, weekendSurcharge } from "../define";

const it = city({ name: "Santorini", country: "Greece", currency: "EUR", prefix: "GR-JTR" });

export const SANTORINI = [
  it(1, "Caldera Catamaran Cruise — Day", { pricing: tiered([10, "135"], [20, "112"]) }),
  it(2, "Caldera Catamaran Cruise — Sunset", {
    pricing: tiered([10, "165"], [20, "138"]),
    modifiers: [evening("18")],
  }),
  it(3, "Oia Sunset Walking Tour", { pricing: flat("45"), modifiers: [evening("10")] }),
  it(4, "Akrotiri Archaeological Site — Guided Visit", { pricing: flat("52") }),
  it(5, "Santorini Wine Road Tasting", {
    pricing: flat("88"),
    modifiers: [season("2026-06-15", "2026-09-15", "14")],
  }),
  it(6, "Private Transfer — Santorini Airport (JTR) to Oia", {
    unit: "per_group",
    pricing: tiered([4, "65"], [8, "95"]),
  }),
  it(7, "Volcano & Hot Springs Boat Trip", {
    pricing: flat("42"),
    modifiers: [weekendSurcharge("1.15")],
  }),
  it(8, "Fira to Oia Cliffside Hike — Guided", { pricing: flat("55") }),
  it(9, "Private Photo Shoot at the Blue Domes", { unit: "per_group", pricing: flat("320") }),
  it(10, "Cooking Class — Santorinian Meze", {
    pricing: flat("95"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(11, "Pyrgos Village & Monastery Half Day", { pricing: flat("58") }),
  it(12, "Red Beach & Perissa Beach Day", { pricing: flat("38") }),
  it(13, "Helicopter Transfer — Santorini to Mykonos", {
    unit: "per_group",
    pricing: flat("2400"),
    modifiers: [blackout("2026-08-15")],
  }),
];
