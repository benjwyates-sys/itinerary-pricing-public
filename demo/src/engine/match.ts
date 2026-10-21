/**
 * Resolving an itinerary's phrasing to a catalog item.
 * Ported from `pricing/match.py`.
 *
 * DESIGN: a similarity score never gates a pricing decision. There is no
 * threshold anywhere in this module. `autoAccept` is true in exactly two
 * cases, both unambiguous:
 *
 *   1. The query and the item name are IDENTICAL after normalisation.
 *   2. The query hits a saved alias — the consultant explicitly confirmed
 *      that this exact phrase means this exact item, previously.
 *
 * Everything else is false, no matter how high `score` is. `score` exists
 * only to order the candidates so the best guess is listed first; nothing
 * downstream may branch on its value. Earlier versions used a 0.85 gate and
 * auto-accepted "Private Transfer — FCO to Rome Centre" against "Private
 * Transfer — Rome Centre to FCO", and "Unguided Visit" against "Guided
 * Visit" — different products at different prices.
 *
 * That makes normalisation the entire safety boundary, so it is conservative
 * in two specific ways: plural folding applies only to an allowlist of domain
 * nouns, and marker punctuation is preserved rather than deleted.
 *
 * The one intentional divergence from the Python: `score` there is built on
 * `difflib.SequenceMatcher`. Here it is a bigram-Dice blend. Since nothing
 * branches on the number, the two need only agree on ordering, not on value.
 */
import type { CatalogItem } from "./types";

/**
 * Characters a rate sheet uses to flag something that changes the price — a
 * percentage, a footnote asterisk, a plus for a supplement, a currency sign.
 * Each is wrapped in spaces so it survives as its own token, rather than
 * being erased like ordinary connective punctuation. "Deposit 50%" is not
 * "Deposit 50".
 */
const MARKER_RE = /([%*+€$£])/gu;

/**
 * Everything else non-word/non-space (hyphens, en/em dashes, slashes,
 * parentheses, colons) collapses to a *space*, not to nothing — which is
 * what makes "Skip-the-Line" equal "Skip the Line" rather than merging into
 * one token. `\p{L}` rather than `\w` so non-ASCII letters survive: "Gruž"
 * must keep its ž.
 */
const PUNCT_RE = /[^\p{L}\p{N}_\s%*+€$£]/gu;
const SPACE_RE = /\s+/gu;

/**
 * Plural folding is restricted to this allowlist — never applied to an
 * arbitrary token. Folding any trailing "s" merges proper nouns and
 * genuinely different services: "Rhodes Island" would equal "Rhode Island".
 * "guide" is deliberately excluded: the number of guides on a booking
 * changes its price, so "Private Guides" must not equal "Private Guide".
 */
const PLURAL_ALLOWLIST = new Set([
  "tour", "ride", "museum", "ticket", "transfer", "gallery", "garden",
  "cruise", "class", "night", "day", "hour", "visit", "entry", "lesson",
  "tasting", "walk", "trip", "package", "seat", "room", "adult", "child",
  "person", "bike",
]);

export function normalize(text: string): string {
  const lowered = String(text).toLowerCase().replace(/&/gu, "and");
  const marked = lowered.replace(MARKER_RE, " $1 ");
  const folded = marked.replace(PUNCT_RE, " ").replace(SPACE_RE, " ").trim();
  return folded.split(" ").filter(Boolean).map(singularize).join(" ");
}

function singularize(token: string): string {
  if (
    token.length >= 4 &&
    token.endsWith("s") &&
    !token.endsWith("ss") &&
    PLURAL_ALLOWLIST.has(token.slice(0, -1))
  ) {
    return token.slice(0, -1);
  }
  return token;
}

export type Candidate = {
  itemId: string;
  name: string;
  score: number;
  reason: string;
  autoAccept: boolean;
};

export type AliasEntry = { id: string; hits: number };

export class Aliases {
  entries: Record<string, AliasEntry>;

  constructor(entries: Record<string, AliasEntry> = {}) {
    this.entries = { ...entries };
  }

  /**
   * Rebuild from stored data. Anything of an unexpected shape degrades to an
   * empty store rather than throwing on first lookup — a corrupted
   * localStorage entry must not brick the demo mid-walkthrough.
   */
  static fromJSON(raw: unknown): Aliases {
    if (!isAliasStore(raw)) return new Aliases();
    return new Aliases(raw);
  }

  add(phrase: string, itemId: string): void {
    const key = normalize(phrase);
    const existing = this.entries[key];
    if (existing && existing.id === itemId) {
      existing.hits += 1;
    } else {
      this.entries[key] = { id: itemId, hits: 1 };
    }
  }

  lookup(phrase: string): string | null {
    return this.entries[normalize(phrase)]?.id ?? null;
  }
}

function isAliasStore(raw: unknown): raw is Record<string, AliasEntry> {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return false;
  return Object.values(raw as Record<string, unknown>).every((value) => {
    if (typeof value !== "object" || value === null) return false;
    const entry = value as Record<string, unknown>;
    return typeof entry.id === "string" && Number.isInteger(entry.hits);
  });
}

export function candidates(
  query: string,
  items: CatalogItem[],
  aliases: Aliases,
  limit = 3,
): Candidate[] {
  const aliasId = aliases.lookup(query);
  if (aliasId) {
    const item = items.find((candidate) => candidate.id === aliasId);
    // An alias pointing at a removed item falls through to ordinary ranking.
    if (item) {
      return [{ itemId: item.id, name: item.name, score: 1, reason: "saved alias", autoAccept: true }]
        .slice(0, limit);
    }
  }

  const normalisedQuery = normalize(query);
  const scored: Candidate[] = items.map((item) => ({
    itemId: item.id,
    name: item.name,
    score: round3(similarity(normalisedQuery, normalize(item.name))),
    reason: "name similarity",
    autoAccept: normalisedQuery === normalize(item.name) && normalisedQuery !== "",
  }));

  // An unresolvable tie must never be broken by alphabetical id. If more than
  // one item comes back identical to the query, none of them auto-accept —
  // ambiguity always goes to the consultant.
  if (scored.filter((candidate) => candidate.autoAccept).length > 1) {
    for (const candidate of scored) candidate.autoAccept = false;
  }

  scored.sort((a, b) => b.score - a.score || a.itemId.localeCompare(b.itemId));
  return scored.slice(0, limit);
}

/**
 * Display-ordering similarity only — never gates a decision. A blend of
 * order-aware whole-string similarity and order-insensitive token overlap.
 * Simple on purpose: since nothing branches on the number, there is no need
 * to chase edge cases.
 */
function similarity(a: string, b: string): number {
  return (dice(a, b) + fuzzyJaccard(a.split(" "), b.split(" "))) / 2;
}

function dice(a: string, b: string): number {
  if (a === b) return 1;
  if (a.length < 2 || b.length < 2) return 0;
  const counts = new Map<string, number>();
  for (const gram of bigrams(a)) counts.set(gram, (counts.get(gram) ?? 0) + 1);
  let hits = 0;
  const bGrams = bigrams(b);
  for (const gram of bGrams) {
    const seen = counts.get(gram) ?? 0;
    if (seen > 0) {
      counts.set(gram, seen - 1);
      hits += 1;
    }
  }
  return (2 * hits) / (bigrams(a).length + bGrams.length);
}

function bigrams(text: string): string[] {
  const grams: string[] = [];
  for (let i = 0; i < text.length - 1; i += 1) grams.push(text.slice(i, i + 2));
  return grams;
}

/** Fuzzy one-to-one token matching, then matched / union. */
function fuzzyJaccard(tokensA: string[], tokensB: string[], threshold = 0.8): number {
  const a = [...new Set(tokensA.filter(Boolean))].sort();
  const b = [...new Set(tokensB.filter(Boolean))].sort();
  if (a.length === 0 && b.length === 0) return 1;
  if (a.length === 0 || b.length === 0) return 0;

  const used = new Set<number>();
  let matched = 0;
  for (const tokenA of a) {
    let bestIndex: number | null = null;
    let bestRatio = threshold - 1e-9;
    for (let i = 0; i < b.length; i += 1) {
      if (used.has(i)) continue;
      const ratio = dice(tokenA, b[i]);
      if (ratio > bestRatio) {
        bestRatio = ratio;
        bestIndex = i;
      }
    }
    if (bestIndex !== null) {
      used.add(bestIndex);
      matched += 1;
    }
  }

  const union = a.length + b.length - matched;
  return union > 0 ? matched / union : 1;
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000;
}
