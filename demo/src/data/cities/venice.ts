import { blackout, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Venice", country: "Italy", currency: "EUR", prefix: "IT-VCE" });

export const VENICE = [
  it(1, "St Mark's Basilica — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "240"], [12, "340"]),
  }),
  it(2, "St Mark's Basilica — Skip the Line Entry", { pricing: flat("32") }),
  it(3, "Doge's Palace — Secret Itineraries Tour", { pricing: flat("58") }),
  it(4, "Private Gondola Serenade — 35 Minutes", {
    unit: "per_group",
    pricing: tiered([5, "180"], [10, "320"]),
    modifiers: [evening("40")],
  }),
  it(5, "Murano & Burano Islands Half Day", {
    pricing: flat("46"),
    modifiers: [season("2026-06-01", "2026-09-15", "8")],
  }),
  it(6, "Cicchetti & Wine Evening Walk", {
    pricing: flat("78"),
    minBillablePax: 4,
    modifiers: [evening("12")],
    note: "Billed for 4 minimum",
  }),
  it(7, "Water Taxi Transfer — Marco Polo (VCE) to San Marco", {
    unit: "per_group",
    pricing: tiered([4, "140"], [8, "195"]),
  }),
  it(8, "Water Taxi Transfer — San Marco to Marco Polo (VCE)", {
    unit: "per_group",
    pricing: tiered([4, "140"], [8, "195"]),
  }),
  it(9, "Peggy Guggenheim Collection Entry", { pricing: flat("19") }),
  it(10, "Rowing Lesson — Venetian Voga", { pricing: flat("95") }),
  it(11, "Torcello & Lagoon Private Boat", {
    unit: "per_group",
    pricing: flat("480"),
    modifiers: [blackout("2026-05-01")],
  }),
  it(12, "Carnival Mask Workshop", { pricing: flat("55") }),
  it(13, "Teatro La Fenice Guided Visit", { pricing: flat("25") }),
];
