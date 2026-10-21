import { blackout, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Barcelona", country: "Spain", currency: "EUR", prefix: "ES-BCN" });

export const BARCELONA = [
  it(1, "Sagrada Família — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "260"], [12, "360"]),
  }),
  it(2, "Sagrada Família — Skip the Line Entry", { pricing: flat("42") }),
  it(3, "Park Güell Timed Entry", { pricing: flat("18") }),
  it(4, "Casa Batlló — Gold Ticket", { pricing: flat("45") }),
  it(5, "Gothic Quarter Walking Tour", { pricing: flat("34") }),
  it(6, "Tapas & Vermouth Evening Walk", {
    pricing: flat("82"),
    minBillablePax: 4,
    modifiers: [evening("10")],
    note: "Billed for 4 minimum",
  }),
  it(7, "Montserrat Half-Day Trip", { pricing: tiered([8, "95"], [20, "78"]) }),
  it(8, "Private Transfer — El Prat (BCN) to Eixample", {
    unit: "per_group",
    pricing: tiered([3, "58"], [8, "88"]),
  }),
  it(9, "Flamenco at Palau Dalmases", {
    pricing: flat("38"),
    modifiers: [blackout("2026-08-15")],
  }),
  it(10, "Costa Brava Sailing Day", {
    pricing: flat("145"),
    modifiers: [season("2026-06-01", "2026-09-15", "20")],
  }),
  it(11, "Picasso Museum — Small Group Tour", { pricing: flat("52") }),
  it(12, "Bike Tour — Barceloneta & Born", { pricing: flat("36") }),
  it(13, "Cooking Class — Paella & Boqueria Market", {
    pricing: flat("98"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(14, "Private Transfer — Eixample to El Prat (BCN)", {
    unit: "per_group",
    pricing: tiered([3, "58"], [8, "88"]),
  }),
];
