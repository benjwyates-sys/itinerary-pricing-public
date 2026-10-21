import { blackout, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Rome", country: "Italy", currency: "EUR", prefix: "IT-ROM" });

export const ROME = [
  it(1, "Colosseum & Roman Forum — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "285"], [12, "395"]),
  }),
  it(2, "Colosseum & Roman Forum — Small Group Tour", { pricing: flat("69") }),
  it(3, "Vatican Museums — Skip the Line", { pricing: tiered([8, "58"], [20, "49"]) }),
  it(4, "Vatican Museums — Skip the Line (Evening)", {
    pricing: flat("78"),
    modifiers: [evening("15")],
  }),
  it(5, "Private Transfer — Fiumicino (FCO) to Rome Centre", {
    unit: "per_group",
    pricing: tiered([3, "65"], [8, "95"]),
  }),
  it(6, "Private Transfer — Rome Centre to Fiumicino (FCO)", {
    unit: "per_group",
    pricing: tiered([3, "65"], [8, "95"]),
  }),
  it(7, "Borghese Gallery Timed Entry", { pricing: flat("32") }),
  it(8, "Trastevere Food Walk", { pricing: flat("89") }),
  it(9, "Appian Way E-Bike Tour", {
    pricing: flat("62"),
    modifiers: [season("2026-06-01", "2026-08-31", "10")],
  }),
  it(10, "Castel Sant'Angelo Entry", { pricing: flat("18") }),
  it(11, "Cooking Class — Pasta & Tiramisù", {
    pricing: flat("95"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(12, "Ostia Antica Half-Day Trip", { pricing: flat("74") }),
  it(13, "Catacombs of San Callisto — Guided Visit", {
    pricing: flat("28"),
    modifiers: [blackout("2026-08-15")],
  }),
  it(14, "Rome by Night Vespa Sidecar Tour", {
    pricing: flat("110"),
    modifiers: [evening("20")],
  }),
];
