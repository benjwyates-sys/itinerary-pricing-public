/**
 * The blank itinerary a consultant downloads, fills in, and drops back.
 *
 * "Optimised for this application" means shaped so the real engine's profiler
 * reads it without having to guess: the five headers it looks for, in row one,
 * on a single sheet, with no title block and no merged band above them. The
 * sample workbook in `samples/build_samples.py` deliberately has all of those
 * traps; this is the opposite of that file.
 */
import { describe, expect, test } from "vitest";
import { HEADERS, buildItineraryTemplate, templateParts } from "./workbook";

const parts = templateParts();
const sheet = parts["xl/worksheets/sheet1.xml"];

describe("the columns", () => {
  test("are the five the engine looks for", () => {
    expect(HEADERS).toEqual(["Experience", "Date", "Pax", "Time", "Net Cost"]);
  });

  test("sit in row one, so no header row has to be guessed at", () => {
    const rowOne = /<row r="1"[^>]*>(.*?)<\/row>/s.exec(sheet)?.[1] ?? "";
    for (const header of HEADERS) expect(rowOne).toContain(`<t>${header}</t>`);
  });

  test("are in the order the engine's own sample uses", () => {
    const order = [...sheet.matchAll(/<t>([^<]+)<\/t>/g)].map((match) => match[1]);
    expect(order).toEqual(HEADERS);
  });

  test("name the cost column in words the profiler recognises", () => {
    // `pricing/itinerary_profile.py` requires a name column and a cost column;
    // "Experience" and "Net Cost" are both in its ROLE_WORDS.
    expect(HEADERS[0].toLowerCase()).toBe("experience");
    expect(HEADERS[4].toLowerCase()).toContain("cost");
  });
});

describe("the sheet", () => {
  test("carries no content but the headers, because it is a blank", () => {
    expect([...sheet.matchAll(/<t>/g)]).toHaveLength(5);
    expect(sheet).not.toContain("<v>");
  });

  test("still has rows beneath the header, which the profiler requires", () => {
    // find_header_candidates skips a row with nothing under it, so a sheet of
    // headers alone would be a template the tool itself could not read.
    const rows = [...sheet.matchAll(/<row r="(\d+)"/g)].map((match) => Number(match[1]));
    expect(rows[0]).toBe(1);
    expect(rows.length).toBeGreaterThan(20);
    expect(rows.every((row, index) => row === index + 1)).toBe(true);
  });

  test("leaves the cost column empty — that is the column the tool fills", () => {
    const rowOne = /<row r="1"[^>]*>(.*?)<\/row>/s.exec(sheet)?.[1] ?? "";
    expect(rowOne).toContain('r="E1"');
    // Every cell below the header is present but holds nothing: no value, no
    // inline string, nothing that could be mistaken for a price.
    const belowHeader = sheet.slice(sheet.indexOf('<row r="2"'));
    expect(belowHeader).toMatch(/^(<row r="\d+">(<c r="[A-E]\d+"\/>)+<\/row>)+<\/sheetData><\/worksheet>$/);
  });

  test("freezes the header row so it stays put on a long itinerary", () => {
    expect(sheet).toContain('state="frozen"');
  });

  test("is the only sheet, and is named for what it holds", () => {
    expect(parts["xl/workbook.xml"]).toContain('name="Itinerary"');
    expect([...parts["xl/workbook.xml"].matchAll(/<sheet /g)]).toHaveLength(1);
  });
});

describe("the package", () => {
  test("declares every part it contains", () => {
    const types = parts["[Content_Types].xml"];
    expect(types).toContain("/xl/workbook.xml");
    expect(types).toContain("/xl/worksheets/sheet1.xml");
    expect(types).toContain("/xl/styles.xml");
  });

  test("points at the workbook from the package root", () => {
    expect(parts["_rels/.rels"]).toContain("xl/workbook.xml");
  });

  test("points at the sheet and the styles from the workbook", () => {
    const rels = parts["xl/_rels/workbook.xml.rels"];
    expect(rels).toContain("worksheets/sheet1.xml");
    expect(rels).toContain("styles.xml");
  });

  test("is a zip that opens with a local file header", () => {
    expect([...buildItineraryTemplate().slice(0, 4)]).toEqual([0x50, 0x4b, 0x03, 0x04]);
  });

  test("is the same file every time it is built", () => {
    expect([...buildItineraryTemplate()]).toEqual([...buildItineraryTemplate()]);
  });
});
