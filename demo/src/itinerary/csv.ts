/**
 * The costed copy of the itinerary.
 *
 * A CSV rather than an .xlsx: the handoff allows either, and a real workbook
 * writer earns its weight only once there is a real workbook to preserve.
 *
 * It is written day by day, in the same order as the screen, so the file and
 * the itinerary read as the same document. A line with no price gets an empty
 * cost cell and a sentence saying why — never a zero, which in a client's
 * quote reads as "free".
 */
import { buildItinerary, nightsOf, stayTotal } from "./build";
import type { CostedLine, CostedTrip, Money } from "../engine/types";

export const CSV_HEADERS = [
  "Day", "Date", "Place", "Time", "Item", "Pax", "Net Cost", "Notes",
];

export function toCsvRows(
  costed: CostedTrip,
  ownPrices: Record<string, Money>,
): string[][] {
  const rows: string[][] = [CSV_HEADERS];

  for (const day of buildItinerary(costed)) {
    const head = [String(day.number), day.date, day.city ?? ""];

    if (day.checkOut) {
      rows.push([...head, "", `Check out: ${day.checkOut.hotel}`, "", "", ""]);
    }
    if (day.checkIn) {
      rows.push([
        ...head,
        "",
        `Check in: ${day.checkIn.hotel} (${day.checkIn.room} × ${day.checkIn.rooms})`,
        "",
        stayTotal(day.checkIn),
        `${nightsOf(day.checkIn)} nights at ${day.checkIn.nightlyRate} a room. ` +
          `From the accommodation booking, not the rate sheet.`,
      ]);
    }
    if (day.atLeisure) {
      rows.push([...head, "", "At leisure", "", "", ""]);
    }

    type Entry = { time: string; line: CostedLine } | { time: string; free: true };
    const entries: Entry[] = [
      ...day.slots.flatMap<Entry>((block) =>
        block.free
          ? [{ time: block.slot, free: true }]
          : block.lines.map((line) => ({ time: block.slot, line })),
      ),
      ...day.untimed.map<Entry>((line) => ({ time: "", line })),
    ];

    for (const entry of entries) {
      if ("free" in entry) {
        rows.push([...head, entry.time, "At leisure", "", "", ""]);
        continue;
      }
      const { line, time } = entry;
      const own = ownPrices[line.line.id];
      rows.push([
        ...head,
        time,
        line.line.text,
        String(line.line.pax),
        own ?? (line.status === "priced" ? line.total! : ""),
        noteFor(line, own),
      ]);
    }
  }

  return rows;
}

export function toCsv(rows: string[][]): string {
  return rows
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\r\n");
}

/** Why a line has the cost it has — or none. The two reasons stay distinct. */
function noteFor(line: CostedLine, own?: Money): string {
  if (own) {
    // An override has to say what it replaced, or the change is invisible.
    return line.status === "priced"
      ? `Entered by hand, not from the rate sheet. The rate sheet priced this at ${line.total}.`
      : "Entered by hand, not from the rate sheet";
  }
  if (line.status === "priced") return `Priced as: ${line.itemName}`;
  if (line.status === "needs_check") {
    return "Not costed. More than one rate could match this wording. Confirm which one.";
  }
  return `Needs a supplier quote. ${line.reason ?? ""}`.trim();
}
