import { ON_REQUEST, blackout, city, evening, flat, season, tiered } from "../define";

const it = city({ name: "Paris", country: "France", currency: "EUR", prefix: "FR-PAR" });

export const PARIS = [
  it(1, "Louvre Museum — Private Guided Tour", {
    unit: "per_group",
    pricing: tiered([6, "320"], [12, "440"]),
  }),
  it(2, "Louvre Museum — Small Group Tour", { pricing: flat("72") }),
  it(3, "Eiffel Tower — Summit Access with Host", { pricing: flat("95") }),
  it(4, "Musée d'Orsay — Skip the Line", { pricing: flat("34") }),
  it(5, "Seine Dinner Cruise", { pricing: flat("145"), modifiers: [evening("20")] }),
  it(6, "Versailles Palace & Gardens Day Trip", { pricing: tiered([8, "135"], [20, "112"]) }),
  it(7, "Private Transfer — Charles de Gaulle (CDG) to the 1st Arrondissement", {
    unit: "per_group",
    pricing: tiered([3, "95"], [8, "135"]),
  }),
  it(8, "Private Transfer — the 1st Arrondissement to Charles de Gaulle (CDG)", {
    unit: "per_group",
    pricing: tiered([3, "95"], [8, "135"]),
  }),
  it(9, "Montmartre & Sacré-Cœur Walking Tour", { pricing: flat("42") }),
  it(10, "Provence Lavender Fields Excursion", {
    pricing: flat("210"),
    modifiers: [season("2026-06-20", "2026-08-10", "25")],
  }),
  it(11, "Le Marais Food & Wine Walk", {
    pricing: flat("98"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(12, "Sainte-Chapelle & Conciergerie Entry", {
    pricing: flat("22"),
    modifiers: [blackout("2026-07-14")],
  }),
  it(13, "Private Jet Transfer — Paris to Nice", { unit: "per_group", note: ON_REQUEST }),
  it(14, "Macaron Baking Class — Saint-Germain", { pricing: flat("85") }),
];
