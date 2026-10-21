import { city, evening, flat, season, tiered, weekendSurcharge } from "../define";

const it = city({ name: "Porto", country: "Portugal", currency: "EUR", prefix: "PT-OPO" });

export const PORTO = [
  it(1, "Douro Valley Wine Tour — Full Day", {
    pricing: tiered([8, "145"], [16, "122"]),
    modifiers: [season("2026-05-01", "2026-10-15", "18")],
  }),
  it(2, "Douro Valley Wine Tour — Half Day", { pricing: tiered([8, "95"], [16, "80"]) }),
  it(3, "Port Cellar Tasting — Vila Nova de Gaia", { pricing: flat("42") }),
  it(4, "Livraria Lello & Clérigos Walk", { pricing: flat("28") }),
  it(5, "Six Bridges River Cruise", {
    pricing: flat("22"),
    modifiers: [weekendSurcharge("1.12")],
  }),
  it(6, "Private Transfer — Francisco Sá Carneiro (OPO) to Ribeira", {
    unit: "per_group",
    pricing: tiered([3, "40"], [8, "62"]),
  }),
  it(7, "Ribeira Food & Wine Evening Walk", {
    pricing: flat("72"),
    modifiers: [evening("10")],
  }),
  it(8, "Bolhão Market Cooking Class", {
    pricing: flat("88"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(9, "Private Guided Tour — Porto Old Town", {
    unit: "per_group",
    pricing: tiered([6, "170"], [14, "245"]),
  }),
  it(10, "Serralves Museum & Gardens Entry", { pricing: flat("20") }),
  it(11, "Guimarães & Braga Day Trip", { pricing: flat("105") }),
  it(12, "São Bento Station & Azulejo Walk", { pricing: flat("26") }),
];
