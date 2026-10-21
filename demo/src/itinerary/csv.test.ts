/**
 * The costed copy. This file is the thing that leaves the building, so what
 * it says about each line matters as much as what the screen says.
 */
import { describe, expect, test } from "vitest";
import { toCsvRows } from "./csv";
import { costTrip } from "../engine/cost";
import { Aliases } from "../engine/match";
import { CATALOG } from "../data/catalog";
import { demoTrip, hardTrip } from "../data/trips";

const rowsFor = (trip: typeof demoTrip, own: Record<string, string> = {}) =>
  toCsvRows(costTrip(trip, CATALOG, new Aliases()), own);

const cell = (rows: string[][], match: string, column: number) =>
  rows.find((row) => row.some((value) => value.includes(match)))?.[column];

describe("the costed copy", () => {
  test("names its columns", () => {
    expect(rowsFor(demoTrip)[0]).toEqual([
      "Day", "Date", "Place", "Time", "Item", "Pax", "Net Cost", "Notes",
    ]);
  });

  test("runs day by day, in the same order as the screen", () => {
    const days = rowsFor(demoTrip).slice(1).map((row) => Number(row[0]));
    expect(days).toEqual([...days].sort((a, b) => a - b));
  });

  test("carries the hotel, its nights, and where its money came from", () => {
    const rows = rowsFor(demoTrip);
    const checkIn = rows.find((row) => row[4].startsWith("Check in: Villa Dubrovnik"))!;
    expect(checkIn[6]).toBe("4740.00");
    expect(checkIn[7]).toMatch(/not the rate sheet/i);
  });

  test("writes a priced line's cost and what it was priced as", () => {
    const rows = rowsFor(demoTrip);
    expect(cell(rows, "Game of Thrones Walking Tour", 6)).toBe("152.00"); // note: only 4 people
    expect(cell(rows, "Game of Thrones Walking Tour", 7)).toContain("Priced as:");
  });

  test("leaves a refused line's cost empty and says why, in the engine's words", () => {
    const rows = rowsFor(hardTrip);
    expect(cell(rows, "Catacombs of San Callisto", 6)).toBe("");
    expect(cell(rows, "Catacombs of San Callisto", 7)).toContain("blackout");
  });

  test("keeps a line you have not confirmed apart from one a supplier owes you", () => {
    const rows = rowsFor(hardTrip);
    const unconfirmed = cell(rows, "uffizi gallery private tour", 7)!;
    expect(unconfirmed).toContain("Confirm which one");
    expect(unconfirmed).not.toContain("supplier quote");
  });

  test("marks a figure entered by hand as exactly that", () => {
    const rows = rowsFor(hardTrip, { h11: "450.00" });
    expect(cell(rows, "Chef's Table Dinner", 6)).toBe("450.00");
    expect(cell(rows, "Chef's Table Dinner", 7)).toMatch(/not from the rate sheet/i);
  });

  test("records the days with nothing booked, rather than skipping them", () => {
    expect(rowsFor(hardTrip).some((row) => row[4] === "At leisure")).toBe(true);
  });

  test("never writes a zero where there is no price", () => {
    for (const trip of [demoTrip, hardTrip]) {
      for (const row of rowsFor(trip).slice(1)) {
        expect(row[6]).not.toBe("0.00");
        expect(row[6]).not.toBe("0");
      }
    }
  });
});

describe("a price overridden by hand", () => {
  test("is the cost that goes in the file, and is named as yours", () => {
    const rows = rowsFor(demoTrip, { d3: "150.00" });
    expect(cell(rows, "Game of Thrones Walking Tour", 6)).toBe("150.00");
    expect(cell(rows, "Game of Thrones Walking Tour", 7)).toMatch(/not from the rate sheet/i);
  });

  test("says what the rate sheet had said, so the change is visible", () => {
    const rows = rowsFor(demoTrip, { d3: "150.00" });
    expect(cell(rows, "Game of Thrones Walking Tour", 7)).toContain("152.00");
  });
});
