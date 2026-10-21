import { blackout, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Athens", country: "Greece", currency: "EUR", prefix: "GR-ATH" });

export const ATHENS = [
  it(1, "Acropolis & Parthenon — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "230"], [12, "325"]),
  }),
  it(2, "Acropolis & Parthenon — Small Group Tour", { pricing: flat("55") }),
  it(3, "Acropolis Museum Entry", { pricing: flat("20") }),
  it(4, "Ancient Agora & Kerameikos Walk", { pricing: flat("42") }),
  it(5, "Cape Sounion Sunset Trip", {
    pricing: tiered([8, "78"], [20, "64"]),
    modifiers: [evening("12")],
  }),
  it(6, "Plaka & Monastiraki Food Walk", { pricing: flat("85") }),
  it(7, "Private Transfer — Athens Airport (ATH) to Syntagma", {
    unit: "per_group",
    pricing: tiered([3, "55"], [8, "80"]),
  }),
  it(8, "Delphi Full-Day Trip", {
    pricing: flat("125"),
    modifiers: [season("2026-06-01", "2026-09-15", "15")],
  }),
  it(9, "Temple of Poseidon Entry", { pricing: flat("12") }),
  it(10, "Greek Cooking Class — Psyri", { pricing: flat("92") }),
  it(11, "Athens Riviera Private Boat — Half Day", {
    unit: "per_group",
    pricing: flat("690"),
    modifiers: [blackout("2026-12-25")],
  }),
  it(12, "National Archaeological Museum — Guided Visit", { pricing: flat("48") }),
  it(13, "Street Art Walking Tour — Exarchia", { pricing: flat("32") }),
];
