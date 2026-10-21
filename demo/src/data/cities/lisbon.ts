import { city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Lisbon", country: "Portugal", currency: "EUR", prefix: "PT-LIS" });

export const LISBON = [
  it(1, "Alfama & Fado Evening Walk", {
    pricing: flat("78"),
    minBillablePax: 4,
    modifiers: [evening("12")],
    note: "Billed for 4 minimum",
  }),
  it(2, "Belém Tower & Jerónimos Monastery — Private Guide", {
    unit: "per_group",
    pricing: tiered([6, "195"], [12, "270"]),
  }),
  it(3, "Belém Tower & Jerónimos Monastery — Small Group", { pricing: flat("48") }),
  it(4, "Sintra & Pena Palace Day Trip", { pricing: tiered([8, "98"], [20, "82"]) }),
  it(5, "Tram 28 & Graça Viewpoints Walk", { pricing: flat("32") }),
  it(6, "Time Out Market Food Tour", { pricing: flat("65") }),
  it(7, "Private Transfer — Humberto Delgado (LIS) to Baixa", {
    unit: "per_group",
    pricing: tiered([3, "45"], [8, "70"]),
  }),
  it(8, "Tagus River Sailing — Sunset", { pricing: flat("55"), modifiers: [evening("10")] }),
  it(9, "Cascais & Estoril Half Day", {
    pricing: flat("72"),
    modifiers: [season("2026-06-01", "2026-09-15", "10")],
  }),
  it(10, "LX Factory & Street Art Walk", { pricing: flat("30") }),
  it(11, "Pastel de Nata Baking Class", { pricing: flat("58") }),
  it(12, "Oceanário de Lisboa Entry", { pricing: flat("25") }),
  it(13, "Óbidos & Nazaré Full Day", { pricing: flat("115") }),
];
