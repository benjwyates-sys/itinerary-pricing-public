/**
 * Notes a consultant writes into the wording of a line.
 *
 * §9 of the handoff is a list of five silent mispricings, and every one came
 * from reading a human's free text generously. "2 adults + 1 child" priced at
 * 2. A stray date in a pax column producing a verified €192,470.
 *
 * So this parser is deliberately mean. It recognises two things and nothing
 * else, and the moment a line carries a note it does NOT recognise, it stops
 * touching that line entirely — the note stays part of the wording, the
 * wording fails to match, and the line goes to a person. Recognising nothing
 * is always safe here; recognising something wrongly is not.
 */
import { describe, expect, test } from "vitest";
import { parseAnnotations } from "./annotations";

const parse = (text: string) => parseAnnotations(text);

describe("a line with no note at all", () => {
  test("is passed through untouched", () => {
    const parsed = parse("Game of Thrones Walking Tour");
    expect(parsed.name).toBe("Game of Thrones Walking Tour");
    expect(parsed.adjustments).toEqual([]);
    expect(parsed.unrecognised).toEqual([]);
  });

  test("keeps parentheses that are part of the experience's real name", () => {
    // The catalog genuinely contains these, and stripping them would stop
    // the line matching anything at all.
    const parsed = parse("Private Transfer — Fiumicino (FCO) to Rome Centre");
    expect(parsed.name).toBe("Private Transfer — Fiumicino (FCO) to Rome Centre");
    expect(parsed.adjustments).toEqual([]);
  });
});

describe("a party-size note", () => {
  test.each([
    "Game of Thrones Walking Tour (only 4 people)",
    "Game of Thrones Walking Tour (4 people only)",
    "Game of Thrones Walking Tour (4 pax)",
    "Game of Thrones Walking Tour (only 4)",
    "Game of Thrones Walking Tour (ONLY 4 TRAVELLERS)",
  ])("is read from %s", (text) => {
    const parsed = parse(text);
    expect(parsed.name).toBe("Game of Thrones Walking Tour");
    expect(parsed.adjustments).toEqual([
      { kind: "pax", pax: 4, note: "only 4 people" },
    ]);
  });

  test("refuses a party of nobody", () => {
    expect(parse("Some Tour (only 0 people)").adjustments).toEqual([]);
    expect(parse("Some Tour (only 0 people)").unrecognised).toEqual(["only 0 people"]);
  });

  test("refuses an implausible party rather than quoting for it", () => {
    expect(parse("Some Tour (4000 pax)").adjustments).toEqual([]);
  });
});

describe("a percentage note", () => {
  test.each([
    ["Krka Waterfalls Day Trip (15% discount)", "0.85"],
    ["Krka Waterfalls Day Trip (15% off)", "0.85"],
    ["Krka Waterfalls Day Trip (less 15%)", "0.85"],
    ["Krka Waterfalls Day Trip (7.5% discount)", "0.925"],
  ])("takes %s off the line", (text, factor) => {
    const parsed = parse(text);
    expect(parsed.name).toBe("Krka Waterfalls Day Trip");
    expect(parsed.adjustments[0]).toMatchObject({ kind: "percent", factor });
  });

  test.each([
    ["Krka Waterfalls Day Trip (+10%)", "1.1"],
    ["Krka Waterfalls Day Trip (10% surcharge)", "1.1"],
  ])("adds %s to the line", (text, factor) => {
    expect(parse(text).adjustments[0]).toMatchObject({ kind: "percent", factor });
  });

  test("refuses to take off everything, or more than everything", () => {
    expect(parse("Some Tour (100% discount)").adjustments).toEqual([]);
    expect(parse("Some Tour (150% off)").adjustments).toEqual([]);
  });
});

describe("a note it does not recognise", () => {
  test("is never applied, and never stripped", () => {
    const parsed = parse("Borghese Gallery Timed Entry (check with Marco)");
    expect(parsed.name).toBe("Borghese Gallery Timed Entry (check with Marco)");
    expect(parsed.adjustments).toEqual([]);
    expect(parsed.unrecognised).toEqual(["check with Marco"]);
  });

  test("poisons the whole line, even alongside one it does recognise", () => {
    // Half-understanding a line is worse than not understanding it: the part
    // it grasped would quietly change the money while the part it missed
    // vanished. Nothing is applied, and the wording goes to a person intact.
    const parsed = parse("Some Tour (only 4 people) (ask Marco about lunch)");
    expect(parsed.name).toBe("Some Tour (only 4 people) (ask Marco about lunch)");
    expect(parsed.adjustments).toEqual([]);
    expect(parsed.unrecognised).toContain("ask Marco about lunch");
  });

  test("is not fooled by a number sitting inside a sentence", () => {
    // This is the "2 adults + 1 child priced at 2" bug, in a new outfit.
    const parsed = parse("Some Tour (2 adults + 1 child)");
    expect(parsed.adjustments).toEqual([]);
    expect(parsed.name).toBe("Some Tour (2 adults + 1 child)");
  });

  test("is not fooled by an ambiguous European decimal", () => {
    expect(parse("Some Tour (1.250 pax)").adjustments).toEqual([]);
  });
});

describe("two notes it does recognise", () => {
  test("both apply, and both are named", () => {
    const parsed = parse("Some Tour (only 4 people) (15% discount)");
    expect(parsed.name).toBe("Some Tour");
    expect(parsed.adjustments).toEqual([
      { kind: "pax", pax: 4, note: "only 4 people" },
      { kind: "percent", factor: "0.85", note: "15% discount" },
    ]);
  });

  test("a second party size is refused rather than one of them being picked", () => {
    const parsed = parse("Some Tour (only 4 people) (6 pax)");
    expect(parsed.adjustments).toEqual([]);
    expect(parsed.name).toBe("Some Tour (only 4 people) (6 pax)");
  });
});
