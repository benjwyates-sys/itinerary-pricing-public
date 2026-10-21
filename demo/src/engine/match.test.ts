/**
 * Ported from `pricing/match.py` and `tests/test_match.py`.
 *
 * The rule this file exists to protect: a similarity score NEVER gates a
 * pricing decision. `autoAccept` is true in exactly two cases — an identical
 * normalised name, or a saved alias. Three earlier designs used a threshold
 * and each one auto-accepted a genuinely different product at a different
 * price. The capability was deleted rather than tuned.
 */
import { describe, expect, test } from "vitest";
import { Aliases, candidates, normalize } from "./match";
import type { CatalogItem } from "./types";

const anItem = (id: string, name: string): CatalogItem => ({
  id,
  name,
  city: "Dubrovnik",
  country: "Croatia",
  currency: "EUR",
  unit: "per_person",
  pricing: { pattern: "flat", amount: "50" },
  modifiers: [],
});

describe("normalize", () => {
  test("folds case and collapses whitespace", () => {
    expect(normalize("  Old TOWN   Walking  ")).toBe("old town walking");
  });

  test("turns an ampersand into 'and'", () => {
    expect(normalize("Cable Car & Fort")).toBe(normalize("Cable Car and Fort"));
  });

  test("collapses hyphens and dashes to a space rather than nothing", () => {
    expect(normalize("Skip-the-Line")).toBe("skip the line");
    expect(normalize("Vatican — Skip the Line")).toBe(normalize("Vatican Skip the Line"));
  });

  test("keeps non-ASCII letters as word characters", () => {
    // "Gruž" must not lose its ž to punctuation stripping.
    expect(normalize("Gruž Market")).toBe("gruž market");
  });

  describe("marker punctuation survives as its own token", () => {
    test("a percentage is not the same as a bare number", () => {
      expect(normalize("Deposit 50%")).not.toBe(normalize("Deposit 50"));
    });

    test("a footnote asterisk is not invisible", () => {
      expect(normalize("Colosseum Tour *")).not.toBe(normalize("Colosseum Tour"));
    });
  });

  describe("plural folding is allowlisted, never blanket", () => {
    test("folds a domain noun", () => {
      expect(normalize("Walking Tours")).toBe(normalize("Walking Tour"));
      expect(normalize("Vatican Museums")).toBe(normalize("Vatican Museum"));
    });

    test("does not fold a proper noun", () => {
      expect(normalize("Rhodes Island")).not.toBe(normalize("Rhode Island"));
    });

    test("does not fold 'guides' — two guides cost more than one", () => {
      expect(normalize("Private Guides")).not.toBe(normalize("Private Guide"));
    });

    test("does not strip a double s", () => {
      expect(normalize("Cooking Class")).toBe("cooking class");
    });

    test("leaves short words alone", () => {
      expect(normalize("Bus")).toBe("bus");
    });
  });
});

describe("candidates", () => {
  const items = [
    anItem("HR-DBV-0001", "Old Town Walking Tour — Private Guide"),
    anItem("HR-DBV-0008", "Old Town Walking Tour — Small Group"),
    anItem("IT-ROM-0007", "Private Transfer — Fiumicino (FCO) to Rome Centre"),
    anItem("IT-ROM-0008", "Private Transfer — Rome Centre to Fiumicino (FCO)"),
    anItem("IT-ROM-0011", "Guided Visit"),
    anItem("IT-ROM-0012", "Unguided Visit"),
  ];

  test("an identical normalised name auto-accepts", () => {
    const [best] = candidates("old town walking tour - private guide", items, new Aliases());
    expect(best.itemId).toBe("HR-DBV-0001");
    expect(best.autoAccept).toBe(true);
  });

  test("a close but different wording never auto-accepts", () => {
    const [best] = candidates("Old Town walking tour (private)", items, new Aliases());
    expect(best.itemId).toBe("HR-DBV-0001");
    expect(best.autoAccept).toBe(false);
  });

  test("a reversed transfer never auto-accepts", () => {
    const found = candidates("Private Transfer — Rome Centre to FCO", items, new Aliases());
    expect(found.every((c) => !c.autoAccept)).toBe(true);
  });

  test("'Unguided Visit' never auto-accepts against 'Guided Visit'", () => {
    const found = candidates("unguided visit tour", items, new Aliases());
    expect(found.every((c) => !c.autoAccept)).toBe(true);
  });

  test("an empty query never auto-accepts", () => {
    const found = candidates("", items, new Aliases());
    expect(found.every((c) => !c.autoAccept)).toBe(true);
  });

  test("two items normalising to the query make neither auto-accept", () => {
    const duplicated = [anItem("A-1", "Sunset Cruise"), anItem("A-2", "sunset cruise")];
    const found = candidates("Sunset Cruise", duplicated, new Aliases());
    expect(found.every((c) => !c.autoAccept)).toBe(true);
  });

  test("ranks the likeliest candidate first without deciding", () => {
    const found = candidates("old town walking tour, private", items, new Aliases());
    expect(found[0].itemId).toBe("HR-DBV-0001");
    expect(found[0].autoAccept).toBe(false);
  });

  test("returns at most the requested number of candidates", () => {
    expect(candidates("private transfer", items, new Aliases(), 2)).toHaveLength(2);
  });
});

describe("aliases", () => {
  test("a confirmed wording auto-accepts next time", () => {
    const items = [anItem("HR-DBV-0001", "Old Town Walking Tour — Private Guide")];
    const aliases = new Aliases();
    aliases.add("Old Town walking tour (private)", "HR-DBV-0001");

    const [best] = candidates("Old Town walking tour (private)", items, aliases);
    expect(best.itemId).toBe("HR-DBV-0001");
    expect(best.autoAccept).toBe(true);
    expect(best.reason).toBe("saved alias");
  });

  test("matches on the normalised phrase, not the literal one", () => {
    const aliases = new Aliases();
    aliases.add("Old Town Walking Tour (private)", "HR-DBV-0001");
    expect(aliases.lookup("old town   walking tour - private")).toBe("HR-DBV-0001");
  });

  test("counts repeat confirmations of the same phrase", () => {
    const aliases = new Aliases();
    aliases.add("sunset kayak", "HR-DBV-0003");
    aliases.add("sunset kayak", "HR-DBV-0003");
    expect(aliases.entries[normalize("sunset kayak")].hits).toBe(2);
  });

  test("an alias pointing at a removed item falls back to ordinary ranking", () => {
    const items = [anItem("HR-DBV-0001", "Old Town Walking Tour — Private Guide")];
    const aliases = new Aliases();
    aliases.add("old town walk", "HR-DBV-9999");

    const found = candidates("old town walk", items, aliases);
    expect(found[0].itemId).toBe("HR-DBV-0001");
    expect(found[0].autoAccept).toBe(false);
  });

  test("survives a round trip through storage", () => {
    const aliases = new Aliases();
    aliases.add("sunset kayak", "HR-DBV-0003");
    expect(Aliases.fromJSON(JSON.parse(JSON.stringify(aliases.entries))).lookup("Sunset Kayak")).toBe(
      "HR-DBV-0003",
    );
  });

  test("degrades to empty when stored data has the wrong shape", () => {
    expect(Aliases.fromJSON(["not", "a", "store"]).lookup("anything")).toBeNull();
    expect(Aliases.fromJSON({ phrase: { id: 5 } }).lookup("phrase")).toBeNull();
  });
});
