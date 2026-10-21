/**
 * Three sample trips, each telling a different story (handoff §6).
 *
 * The wording of each line is what matters. A line worded exactly as the
 * catalog has it prices itself; a line worded the way a consultant actually
 * types stops and asks. That difference is the whole demo, so the phrasing
 * here is deliberate, not incidental.
 *
 * Line-level `pax` exists because a party of fourteen does not all do the
 * cooking class. It is also how the hard trip demonstrates a minimum-billable
 * line and an above-top-tier refusal in the same itinerary.
 */
import type { Stay, Trip, TripLine } from "../engine/types";

/**
 * Where the party sleeps. Rates are invented like everything else here, and
 * are deliberately NOT rate-sheet rates — the engine prices experiences, and
 * every screen that shows a stay total says where it came from.
 */
const stay = (
  city: string,
  hotel: string,
  room: string,
  rooms: number,
  checkIn: string,
  checkOut: string,
  nightlyRate: string,
): Stay => ({ city, hotel, room, rooms, checkIn, checkOut, nightlyRate, currency: "EUR" });

const line = (
  id: string,
  text: string,
  date: string,
  pax: number,
  dayPart: TripLine["dayPart"] = null,
): TripLine => ({ id, text, date, pax, dayPart });

/**
 * Trip one: every line's wording matches the catalog exactly. Prices
 * instantly, asks nothing. Show this first — it is the normal day.
 */
export const cleanTrip: Trip = {
  id: "hartley-rome",
  fileName: "Trip_Hartley_Rome.xlsx",
  client: "Hartley party",
  title: "Hartley party — Rome",
  cities: ["Rome"],
  from: "2026-05-11",
  to: "2026-05-15",
  pax: 4,
  stays: [stay("Rome", "Hotel de Russie", "Classic Double", 2, "2026-05-11", "2026-05-15", "480")],
  lines: [
    line("c1", "Private Transfer — Fiumicino (FCO) to Rome Centre", "2026-05-11", 4, "AM"),
    line("c2", "Colosseum & Roman Forum — Small Group Tour", "2026-05-12", 4, "AM"),
    line("c3", "Vatican Museums — Skip the Line", "2026-05-12", 4, "PM"),
    line("c4", "Borghese Gallery Timed Entry", "2026-05-13", 4, "AM"),
    line("c5", "Trastevere Food Walk", "2026-05-13", 4, "EVENING"),
    line("c6", "Castel Sant'Angelo Entry", "2026-05-14", 4, "AM"),
    line("c7", "Ostia Antica Half-Day Trip", "2026-05-14", 4, "PM"),
    line("c8", "Private Transfer — Rome Centre to Fiumicino (FCO)", "2026-05-15", 4, "AM"),
  ],
};

/**
 * Trip two: the walkthrough. Worded the way a consultant types — lowercase,
 * abbreviated, reordered — so three lines stop and ask, and one genuinely
 * cannot be priced from the sheet at all.
 */
export const demoTrip: Trip = {
  id: "novak-dalmatia",
  fileName: "Trip_Novak_Dalmatia.xlsx",
  client: "Novak party",
  title: "Novak party — Dubrovnik & Split",
  cities: ["Dubrovnik", "Split"],
  from: "2026-06-08",
  to: "2026-06-15",
  pax: 5,
  stays: [
    stay("Dubrovnik", "Villa Dubrovnik", "Sea View Room", 3, "2026-06-08", "2026-06-12", "395"),
    stay("Split", "Hotel Ambasador", "Superior Sea View", 3, "2026-06-12", "2026-06-15", "265"),
  ],
  lines: [
    line("d1", "Private Transfer — Dubrovnik Airport (DBV) to Old Town", "2026-06-08", 5, "AM"),
    // Two things in the rate sheet could be this, and they price differently.
    line("d2", "Old Town walking tour (private)", "2026-06-09", 5, "AM"),
    // A note the tool recognises: four of the five go.
    line("d3", "Game of Thrones Walking Tour (only 4 people)", "2026-06-09", 5, "PM"),
    line("d4", "Elafiti Islands Full-Day Cruise", "2026-06-10", 5, "AM"),
    line("d5", "Sea Kayaking — Old Town Walls", "2026-06-10", 5, "PM"),
    // Close to one experience, but not worded the same way.
    line("d6", "Cooking class at Gruž market", "2026-06-11", 5, "AM"),
    line("d7", "Cable Car & Fort Imperial Entry", "2026-06-11", 5, "PM"),
    // No rate at all — this one can only ever come from the supplier.
    line("d8", "Bespoke Photography Session", "2026-06-12", 5, "AM"),
    line("d9", "palace walking tour, private guide", "2026-06-13", 5, "AM"),
    line("d10", "Krka Waterfalls Day Trip (15% discount)", "2026-06-14", 5, "AM"),
    line("d11", "marjan hill sunset walk", "2026-06-14", 5, "EVENING"),
    line("d12", "Private Transfer — the Riva to Split Airport (SPU)", "2026-06-15", 5, "AM"),
  ],
};

/**
 * Trip three: the refusals. A party above the top tier, a blackout date, an
 * on-request experience, and a two-person booking billed at the four-person
 * minimum — all in one itinerary.
 */
export const hardTrip: Trip = {
  id: "whitaker-italy",
  fileName: "Trip_Whitaker_Italy.xlsx",
  client: "Whitaker party",
  title: "Whitaker party — Rome & Florence",
  cities: ["Rome", "Florence"],
  from: "2026-08-12",
  to: "2026-08-18",
  pax: 14,
  stays: [
    stay("Rome", "Palazzo Manfredi", "Classic Room", 7, "2026-08-12", "2026-08-16", "430"),
    stay("Florence", "Villa Cora", "Deluxe Room", 7, "2026-08-16", "2026-08-18", "385"),
  ],
  lines: [
    // Fourteen is above the twelve-person top tier. The engine will not
    // extend the top band to cover it.
    line("h1", "Colosseum & Roman Forum — Private Guided Tour", "2026-08-13", 14, "AM"),
    // 15 August is a public holiday across Catholic Europe.
    line("h2", "Catacombs of San Callisto — Guided Visit", "2026-08-15", 14, "AM"),
    // Two people, billed for the four-person minimum.
    line("h3", "Cooking Class — Pasta & Tiramisù", "2026-08-14", 2, "PM"),
    line("h4", "Vatican Museums — Skip the Line", "2026-08-13", 14, "PM"),
    line("h5", "Borghese Gallery Timed Entry (check with Marco)", "2026-08-14", 14, "AM"),
    line("h6", "Uffizi Gallery — Small Group Tour", "2026-08-16", 14, "PM"),
    line("h7", "Chianti Wine Tour — Half Day", "2026-08-17", 14, "AM"),
    line("h8", "Private Transfer — Florence to Siena", "2026-08-17", 14, "PM"),
    line("h9", "uffizi gallery private tour", "2026-08-16", 6, "AM"),
    line("h10", "Piazzale Michelangelo Sunset Walk", "2026-08-16", 14, "EVENING"),
    line("h11", "Chef's Table Dinner — Private Villa", "2026-08-17", 14, "EVENING"),
  ],
};

export const SAMPLE_TRIPS: Trip[] = [cleanTrip, demoTrip, hardTrip];
