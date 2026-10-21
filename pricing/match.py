"""Resolving an itinerary's phrasing to a catalog item.

DESIGN (post three failed tuning rounds — see task-9-report.md "Redesign"
section for the full history): a similarity score never gates a pricing
decision. There is no threshold anywhere in this module.

`auto_accept` is `True` in exactly two cases, both unambiguous:

  1. The query and the item name are IDENTICAL after normalisation
     (case, punctuation, dash, "&"/"and", plural folding all collapsed).
  2. The query hits a saved alias — an operator explicitly confirmed this
     exact phrase means this exact item, previously.

Everything else is `False`, no matter how high `score` is. `score` exists
only to order `candidates()` so the operator's best guess is listed first;
nothing downstream may branch on its value. A close-but-unconfirmed match
(e.g. "Uffizi Gallery private tour" vs "Uffizi Gallery — Private Guided
Tour") ranks first and gets picked with one keystroke — but it is *she*
who confirms it, not a number.

Normalisation is now the entire safety boundary (fix round after the
redesign), so it has to be conservative in two specific ways:

  - Plural folding only applies to a small allowlist of domain nouns
    (tour, museum, ride, ...), never to any token blindly. Folding *any*
    trailing "s" merges proper nouns and genuinely different services
    ("Rhodes Island Tour" == "Rhode Island Tour"; "Blues Cruise" ==
    "Blue Cruise"; "Private Guides" == "Private Guide", two guides
    priced differently from one).
  - A small set of "marker" punctuation characters (%, *, +, and a few
    currency symbols) is never silently deleted — a rate sheet uses
    exactly these to flag something that changes the price ("Deposit
    50%" is not "Deposit 50"; "Colosseum Tour *" flags a footnote the
    plain name doesn't have). Everything else (hyphens, dashes, slashes,
    parentheses, ordinary sentence punctuation) still collapses to a
    plain separator space, same as before.

`candidates()` also guards against ambiguity: if normalisation makes more
than one catalog item come back identical to the query (e.g. two rows
that are genuine duplicates), auto_accept is forced to False on all of
them — an unresolvable tie must never be broken by alphabetical item_id.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from pricing.catalog import CatalogItem

# Marker punctuation: characters a rate sheet uses to flag something that
# changes the price or terms (a percentage, a footnote asterisk, a plus for
# a supplement, a currency symbol). These must never be silently deleted —
# each is wrapped in spaces so it survives normalisation as its own token,
# rather than being erased like ordinary connective punctuation.
_MARKERS = "%*+€$£"
_MARKER_RE = re.compile(f"([{re.escape(_MARKERS)}])")

# Everything else non-word/non-space (hyphens, en/em dashes, slashes,
# parentheses, colons, ordinary sentence punctuation) still collapses to a
# plain separator space, same as before — this is what makes
# "Skip-the-Line" equal "Skip the Line" and en dash equal a hyphen.
_PUNCT = re.compile(rf"[^\w\s{re.escape(_MARKERS)}]", flags=re.UNICODE)
_SPACE = re.compile(r"\s+")
_AMPERSAND = re.compile(r"&")

# Plural folding is restricted to this allowlist of domain nouns — never
# applied to an arbitrary token. Only a word whose singular form is in
# this set gets its trailing "s" stripped. Deliberately excludes "guide":
# the number of guides on a booking changes its price, so "Private
# Guides" must NOT normalise the same as "Private Guide".
_PLURAL_ALLOWLIST = {
    "tour", "ride", "museum", "ticket", "transfer", "gallery", "garden",
    "cruise", "class", "night", "day", "hour", "visit", "entry", "lesson",
    "tasting", "walk", "trip", "package", "seat", "room", "adult", "child",
    "person", "bike",
}


def normalize(text: str) -> str:
    """Fold case, punctuation, dashes, '&', whitespace, and simple plurals.

    '&' becomes 'and' first. Marker punctuation (%, *, +, currency symbols)
    is preserved as its own token; every other punctuation character
    (including en dash '–' and em dash '—') becomes a space, not nothing,
    so "Skip-the-Line" and "Skip the Line" both become "skip the line"
    rather than merging into one token. A token of 4+ characters that ends
    in a single trailing 's' (not 'ss') is folded to its singular form
    only when that singular is in `_PLURAL_ALLOWLIST`, so "rides"/"ride"
    and "museums"/"museum" normalise identically while "class", "bus",
    and proper nouns like "Rhodes" are left alone.
    """
    lowered = _AMPERSAND.sub("and", str(text).lower())
    marked = _MARKER_RE.sub(r" \1 ", lowered)
    folded = _SPACE.sub(" ", _PUNCT.sub(" ", marked)).strip()
    tokens = [_singularize(tok) for tok in folded.split(" ") if tok]
    return " ".join(tokens)


def _singularize(token: str) -> str:
    if (
        len(token) >= 4
        and token.endswith("s")
        and not token.endswith("ss")
        and token[:-1] in _PLURAL_ALLOWLIST
    ):
        return token[:-1]
    return token


@dataclass
class Candidate:
    item_id: str
    name: str
    score: float
    reason: str
    auto_accept: bool = False


class Aliases:
    def __init__(self, entries: dict | None = None, load_error: str | None = None) -> None:
        self.entries: dict = dict(entries or {})
        self.load_error: str | None = load_error

    @classmethod
    def load(cls, path: Path) -> "Aliases":
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            # Corrupted aliases file; return empty with error marker so caller can report it
            return cls(load_error=f"Corrupted aliases file: {e}")
        except IOError as e:
            # File read error
            return cls(load_error=f"Failed to read aliases file: {e}")

        if not _is_valid_alias_store(raw):
            # Syntactically valid JSON but the wrong shape (e.g. a list, or
            # entries missing "id"/"hits") — degrade the same way a
            # corrupted file does rather than crashing on first lookup.
            return cls(load_error="Aliases file has an unexpected structure")
        return cls(raw)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.entries, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, phrase: str, item_id: str) -> None:
        key = normalize(phrase)
        entry = self.entries.get(key)
        if entry and entry["id"] == item_id:
            entry["hits"] += 1
        else:
            self.entries[key] = {"id": item_id, "hits": 1}

    def lookup(self, phrase: str) -> str | None:
        entry = self.entries.get(normalize(phrase))
        return entry["id"] if entry else None


def _is_valid_alias_store(raw: object) -> bool:
    """A valid alias store is a dict of {str: {"id": str, "hits": int}}."""
    if not isinstance(raw, dict):
        return False
    for key, value in raw.items():
        if not isinstance(key, str):
            return False
        if not isinstance(value, dict):
            return False
        if not isinstance(value.get("id"), str):
            return False
        hits = value.get("hits")
        if not isinstance(hits, int) or isinstance(hits, bool):
            return False
    return True


def candidates(query: str, items: list[CatalogItem], aliases: Aliases,
               limit: int = 3) -> list[Candidate]:
    alias_id = aliases.lookup(query)
    if alias_id:
        for item in items:
            if item.id == alias_id:
                return [Candidate(item.id, item.name, 1.0, "saved alias", auto_accept=True)][:limit]
        # Alias points at a deleted item id: fall through to ordinary scoring.

    normalised_query = normalize(query)
    scored = [
        Candidate(
            item.id,
            item.name,
            round(_score(normalised_query, normalize(item.name)), 3),
            "name similarity",
            auto_accept=(normalised_query == normalize(item.name) and normalised_query != ""),
        )
        for item in items
    ]

    # An unresolvable tie must never be broken by alphabetical item_id. If
    # normalisation makes more than one catalog item come back identical to
    # the query (genuine duplicate rows, a seasonal variant entered twice),
    # none of them auto-accept — ambiguity always goes to the operator.
    if sum(1 for c in scored if c.auto_accept) > 1:
        for c in scored:
            c.auto_accept = False

    scored.sort(key=lambda c: (-c.score, c.item_id))
    return scored[:limit]


def _score(a: str, b: str) -> float:
    """Display-ordering similarity only — never gates a decision.

    Blend of order-aware whole-string similarity and order-insensitive
    fuzzy token overlap. Simple on purpose: since nothing branches on the
    number any more, there is no need to chase edge cases with special-case
    rules (no directional-preposition rule, no low-score rescue, no
    threshold constants).
    """
    sequence = SequenceMatcher(None, a, b).ratio()
    overlap = _fuzzy_jaccard(a.split(), b.split())
    return (sequence + overlap) / 2


def _fuzzy_jaccard(tokens_a: list[str], tokens_b: list[str],
                    threshold: float = 0.8) -> float:
    """Order-insensitive similarity: fuzzy one-to-one token matching, then
    matched / union (Jaccard). Two empty token lists are trivially identical;
    one empty and one non-empty share nothing.
    """
    tokens_a = sorted(set(tokens_a))
    tokens_b = sorted(set(tokens_b))
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    used_b: set[int] = set()
    matched = 0
    for ta in tokens_a:
        best_idx, best_ratio = None, threshold - 1e-9
        for i, tb in enumerate(tokens_b):
            if i in used_b:
                continue
            ratio = SequenceMatcher(None, ta, tb).ratio()
            if ratio > best_ratio:
                best_ratio, best_idx = ratio, i
        if best_idx is not None:
            used_b.add(best_idx)
            matched += 1

    union = len(tokens_a) + len(tokens_b) - matched
    return matched / union if union else 1.0
