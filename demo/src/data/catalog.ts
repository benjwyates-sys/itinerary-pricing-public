/**
 * The sample catalog: fourteen European cities, twelve to fifteen
 * experiences each. Invented rates, plausible shapes.
 *
 * The coverage rules this satisfies are asserted in `catalog.test.ts` rather
 * than trusted — a catalog of flat per-person rates would show a tool that
 * appears to do nothing, and the naming traps are what give the confirm-a-
 * match flow anything to demonstrate.
 */
import type { CatalogItem, Currency } from "../engine/types";
import { ATHENS } from "./cities/athens";
import { BARCELONA } from "./cities/barcelona";
import { DUBROVNIK } from "./cities/dubrovnik";
import { FLORENCE } from "./cities/florence";
import { LISBON } from "./cities/lisbon";
import { LONDON } from "./cities/london";
import { PARIS } from "./cities/paris";
import { PORTO } from "./cities/porto";
import { PRAGUE } from "./cities/prague";
import { ROME } from "./cities/rome";
import { SANTORINI } from "./cities/santorini";
import { SEVILLE } from "./cities/seville";
import { SPLIT } from "./cities/split";
import { VENICE } from "./cities/venice";

export type City = { name: string; country: string; currency: Currency };

/** Alphabetical, so the admin screen has a stable order. */
export const CITIES: City[] = [
  { name: "Athens", country: "Greece", currency: "EUR" },
  { name: "Barcelona", country: "Spain", currency: "EUR" },
  { name: "Dubrovnik", country: "Croatia", currency: "EUR" },
  { name: "Florence", country: "Italy", currency: "EUR" },
  { name: "Lisbon", country: "Portugal", currency: "EUR" },
  { name: "London", country: "United Kingdom", currency: "GBP" },
  { name: "Paris", country: "France", currency: "EUR" },
  { name: "Porto", country: "Portugal", currency: "EUR" },
  { name: "Prague", country: "Czechia", currency: "CZK" },
  { name: "Rome", country: "Italy", currency: "EUR" },
  { name: "Santorini", country: "Greece", currency: "EUR" },
  { name: "Seville", country: "Spain", currency: "EUR" },
  { name: "Split", country: "Croatia", currency: "EUR" },
  { name: "Venice", country: "Italy", currency: "EUR" },
];

export const CATALOG: CatalogItem[] = [
  ...ATHENS, ...BARCELONA, ...DUBROVNIK, ...FLORENCE, ...LISBON, ...LONDON,
  ...PARIS, ...PORTO, ...PRAGUE, ...ROME, ...SANTORINI, ...SEVILLE,
  ...SPLIT, ...VENICE,
];

export function itemsInCity(cityName: string): CatalogItem[] {
  return CATALOG.filter((item) => item.city === cityName);
}
