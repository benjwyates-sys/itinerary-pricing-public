/**
 * Ported from `samples/build_reference_catalog.py` rather than reinvented,
 * so the demo's Dubrovnik figures agree with the stakeholder deck. Rates
 * that are cell references in the real catalog are their last-seen values
 * here; nothing else differs.
 */
import { ON_REQUEST, blackout, afternoon, city, flat, season, tiered } from "../define";

const it = city({ name: "Dubrovnik", country: "Croatia", currency: "EUR", prefix: "HR-DBV" });

export const DUBROVNIK = [
  it(1, "Old Town Walking Tour — Private Guide", {
    unit: "per_group",
    pricing: tiered([6, "180"], [15, "260"]),
  }),
  it(2, "Elafiti Islands Full-Day Cruise", { pricing: tiered([8, "95"], [20, "82"]) }),
  it(3, "Sea Kayaking — Old Town Walls", {
    pricing: flat("48"),
    modifiers: [afternoon("12")],
  }),
  it(4, "Konavle Valley Wine Tasting — Half Day", {
    pricing: flat("78"),
    modifiers: [season("2026-06-15", "2026-09-15", "14")],
  }),
  it(5, "Cooking Class — Gruž Market & Lunch", {
    pricing: flat("110"),
    minBillablePax: 4,
    note: "Billed for 4 minimum",
  }),
  it(6, "Cable Car & Fort Imperial Entry", { pricing: flat("27") }),
  it(7, "Private Transfer — Dubrovnik Airport (DBV) to Old Town", {
    unit: "per_group",
    pricing: tiered([3, "42"], [8, "68"]),
  }),
  it(8, "Old Town Walking Tour — Small Group", { pricing: flat("45") }),
  it(9, "Game of Thrones Walking Tour", { pricing: flat("38") }),
  it(10, "Trsteno Arboretum Entry", { pricing: flat("12") }),
  it(11, "Ston Oysters & Walls Day Trip", { pricing: flat("85") }),
  it(12, "Bespoke Photography Session", { note: ON_REQUEST }),
  it(13, "Private Yacht Charter — Full Day", {
    unit: "per_group",
    pricing: flat("1850"),
    modifiers: [blackout("2026-08-15")],
  }),
  it(14, "Private Transfer — Old Town to Dubrovnik Airport (DBV)", {
    unit: "per_group",
    pricing: tiered([3, "42"], [8, "68"]),
  }),
];
