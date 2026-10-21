import { blackout, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Seville", country: "Spain", currency: "EUR", prefix: "ES-SVQ" });

export const SEVILLE = [
  it(1, "Half-Day Seville Walking Tour", { pricing: flat("38") }),
  it(2, "Full-Day Seville Walking Tour", { pricing: flat("68") }),
  it(3, "Real Alcázar — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "210"], [12, "290"]),
  }),
  it(4, "Real Alcázar — Skip the Line Entry", { pricing: flat("32") }),
  it(5, "Seville Cathedral & Giralda — Guided Visit", { pricing: flat("28") }),
  it(6, "Flamenco at Casa de la Memoria", { pricing: flat("35"), modifiers: [evening("8")] }),
  it(7, "Tapas Evening Walk — Santa Cruz", { pricing: flat("75"), modifiers: [evening("10")] }),
  it(8, "Private Transfer — Seville Airport (SVQ) to Santa Cruz", {
    unit: "per_group",
    pricing: tiered([3, "35"], [8, "55"]),
  }),
  it(9, "Córdoba Day Trip by Train", { pricing: tiered([8, "145"], [16, "125"]) }),
  it(10, "Guadalquivir River Cruise", { pricing: flat("22") }),
  it(11, "Plaza de España & María Luisa Park Walk", {
    pricing: flat("20"),
    modifiers: [blackout("2026-04-06")],
  }),
  it(12, "Horse Carriage Tour — Historic Centre", {
    unit: "per_group",
    pricing: flat("65"),
    modifiers: [season("2026-04-01", "2026-05-15", "15")],
  }),
  it(13, "Andalusian Cooking Class", { pricing: flat("88") }),
];
