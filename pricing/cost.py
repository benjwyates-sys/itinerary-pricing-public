"""Orchestration: itinerary lines in, priced lines out.

Nothing here decides a price — patterns.py does that. Nothing here reads a
rate — catalog.py does that. This module's job is to hold the loop together
and to make every not-priced outcome explicit.

AUTO-ACCEPT IS NOT A SCORE THRESHOLD (see pricing/match.py's module
docstring for the full history — three rounds of tuning a similarity
threshold each produced a different silent mispricing: a reversed-direction
transfer auto-accepting, "Unguided Visit" matching "Guided Visit", adjacent
SKU codes matching each other). A line is priced without asking only when
`candidates()` returns a top candidate whose `auto_accept` flag is True —
set in exactly two cases: the names are identical after normalisation, or
the query hit a saved alias. `score` exists only to order candidates for
display and must never be compared to a number here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from pricing.catalog import Catalog, FingerprintMismatch, PriceChange, resolve_rates
from pricing.itinerary_profile import ItineraryTemplate
from pricing.match import Aliases, candidates
from pricing.patterns import NeedsQuote, PricingRequest, evaluate
from pricing.workbook import CellRef, Workbook, missing_sheet_name


@dataclass
class ItineraryLine:
    row: int
    raw_name: str
    date: Date | None
    pax: int
    day_part: str | None
    # "parsed" (normal case: an unambiguous integer party size, 1-200),
    # "unparseable" (pax cell has content that is not one of the narrow
    # accepted forms -- e.g. a range, an open count, extra words, or text
    # with no leading number at all) or "out_of_range" (the cell IS an
    # unambiguous integer, but it's 0, negative, or above the plausibility
    # ceiling). Both non-"parsed", non-"blank" kinds mean the same thing to
    # every caller: the line must be kept and asked about, never dropped
    # and never priced with a guessed or substituted default. Blank cells
    # never reach here as a line at all: they're filtered out in
    # parse_itinerary, either by using template.default_pax or by being
    # treated as a section heading.
    pax_kind: str = "parsed"
    pax_raw: str | None = None


@dataclass
class PricedLine:
    row: int
    raw_name: str
    item_id: str | None = None
    status: str = "unmatched"
    total: Decimal | None = None
    currency: str | None = None
    reason: str | None = None
    breakdown: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)


def parse_itinerary(
    wb: Workbook, template: ItineraryTemplate
) -> tuple[list[ItineraryLine], list[dict]]:
    """Returns (lines, skipped_rows).

    skipped_rows is every row that had a name but was left out of `lines`
    because its pax cell was blank and no default_pax was configured --
    the heuristic that tells a real line item ("Uffizi Gallery private
    tour") apart from a section heading ("DAY 1 -- FLORENCE"). That
    heuristic cannot actually tell the two apart; it only guesses from an
    empty cell. A genuine heading and a real line item whose party size
    was left blank (an uncached formula, a stale template pointed at the
    wrong column, "same party throughout" never being filled in) look
    identical to it. Silently dropping either one is a line that vanishes
    from the client's quote with no signal anywhere (see design review
    finding C3) -- so nothing is ever dropped without a trace any more.
    Every row this happens to is reported here, by row number and name,
    so a human can say which of them are real.
    """
    max_row, _ = wb.dimensions(template.sheet)
    lines: list[ItineraryLine] = []
    skipped_rows: list[dict] = []

    for row in range(template.first_data_row, max_row + 1):
        name = _role(wb, template, "name", row)
        if name is None or not str(name).strip():
            continue

        raw_pax = _role(wb, template, "pax", row)
        pax_value, pax_kind = _read_pax(raw_pax)

        if pax_kind == "blank":
            if template.default_pax:
                pax = template.default_pax
            else:
                # A row with a name but nobody travelling might be a
                # section heading, or it might be a real line item whose
                # party size never made it into this cell. We cannot tell
                # the difference from here -- so the row is left out of
                # `lines` (never priced with a guessed pax) but recorded
                # in skipped_rows instead of vanishing silently.
                skipped_rows.append({"row": row, "name": str(name).strip()})
                continue
            pax_raw = None
        elif pax_kind == "parsed":
            pax = pax_value
            pax_raw = None
        else:  # "unparseable" or "out_of_range" -- content is present but
            # not one of the narrow unambiguous forms, or it parsed to a
            # number outside 1-200. Never dropped, and never defaulted: a
            # row that names a real experience but whose party size is
            # ambiguous is a silent mispricing waiting to happen if we
            # guess. price_lines() turns this into an explicit needs_quote
            # instead, quoting the cell's actual text.
            pax = 0
            pax_raw = str(raw_pax).strip()

        lines.append(ItineraryLine(
            row=row,
            raw_name=str(name).strip(),
            date=_as_date(_role(wb, template, "date", row)),
            pax=pax,
            day_part=_as_day_part(_role(wb, template, "day_part", row)),
            pax_kind=pax_kind,
            pax_raw=pax_raw,
        ))
    return lines, skipped_rows


def price_lines(lines: list[ItineraryLine], catalog: Catalog, aliases: Aliases,
                wb_rates: Workbook,
                resolutions: dict[int, str] | None = None
                ) -> tuple[list[PricedLine], list[PriceChange]]:
    resolutions = resolutions or {}
    priced: list[PricedLine] = []
    all_changes: list[PriceChange] = []

    for line in lines:
        result = PricedLine(row=line.row, raw_name=line.raw_name)

        if line.pax_kind in ("unparseable", "out_of_range"):
            # Keep the line, ask the operator -- never guess a party size
            # and never drop a real experience from the quote.
            result.status = "needs_quote"
            result.reason = _pax_reason(line.pax_kind, line.pax_raw)
            priced.append(result)
            continue

        item_id = resolutions.get(line.row)

        if item_id is None:
            ranked = candidates(line.raw_name, catalog.items, aliases)
            result.candidates = [vars(c) for c in ranked]
            if ranked and ranked[0].auto_accept:
                item_id = ranked[0].item_id
            else:
                result.reason = "No confident match — please choose."
                priced.append(result)
                continue

        result.item_id = item_id
        # I1 (code review): this used to be one `except KeyError` wrapped
        # around catalog.get, resolve_rates AND evaluate. A KeyError from
        # a renamed sheet or a malformed catalog item (missing "when",
        # "currency", "unit", or "cell") was reported as "Catalog has no
        # item {item_id!r}" -- a plainly false reason, since the item is
        # right there. /map is an AI writing catalog entries across
        # sessions, so a malformed entry is the expected failure mode, not
        # a rare one, and the reason it's given has to point at the actual
        # problem or the operator just re-runs /map and reproduces the
        # same broken entry. Only catalog.get's own KeyError (a genuinely
        # missing item id) gets the "no item" message now; every other
        # KeyError -- from resolve_rates or evaluate -- gets a distinct
        # reason naming what looks malformed.
        try:
            item = catalog.get(item_id)
        except KeyError:
            result.status = "unmatched"
            result.reason = f"Catalog has no item {item_id!r}."
            priced.append(result)
            continue

        try:
            rates, changes = resolve_rates(item, wb_rates)
            all_changes.extend(changes)
            outcome = evaluate(item.to_dict(), rates,
                               PricingRequest(line.pax, line.date, line.day_part))
        except KeyError as exc:
            result.status = "unmatched"
            result.reason = (
                f"The catalog entry {item_id!r} looks malformed -- it is "
                f"missing {_describe_key_error(exc)}. Re-run /map for this "
                "item to fix it."
            )
        except (NeedsQuote, FingerprintMismatch) as exc:
            result.status = "needs_quote"
            result.reason = getattr(exc, "reason", str(exc))
        else:
            result.status = "priced"
            result.total = outcome.total
            result.currency = outcome.currency
            result.breakdown = outcome.breakdown

        priced.append(result)

    return priced, all_changes


def _describe_key_error(exc: KeyError) -> str:
    """I2-regression (code review): a KeyError surfacing from inside
    resolve_rates (e.g. a mapped cell whose sheet was renamed out from
    under it) is openpyxl's raw KeyError("Worksheet <name> does not
    exist."), and `f"missing {exc}"` used to read that whole sentence
    back inside another sentence -- "...it is missing 'Worksheet Italy
    does not exist.'". If it's that specific shape, name just the sheet
    cleanly instead; any other KeyError (e.g. a catalog item's "pricing"
    dict missing a "cell" key) is reported as before, via str(exc).
    """
    sheet = missing_sheet_name(exc)
    if sheet is not None:
        return f"sheet {sheet!r}"
    return str(exc)


def _role(wb: Workbook, template: ItineraryTemplate, role: str, row: int) -> object:
    letter = template.roles.get(role)
    if not letter:
        return None
    return wb.read(CellRef(template.sheet, letter, row))


def _as_date(value: object) -> Date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, Date):
        return value
    try:
        return datetime.fromisoformat(str(value).strip()).date()
    except ValueError:
        return None


_BARE_DIGITS = re.compile(r"^\d+$")
_DIGITS_WITH_NOUN = re.compile(r"^(\d+)\s+([A-Za-z]+)$")
_PAX_NOUNS = frozenset({
    "pax", "adult", "adults", "person", "persons", "people",
    "guest", "guests", "traveller", "travellers",
    "traveler", "travelers", "pp",
})
_MIN_PAX = 1
_MAX_PAX = 200


def _read_pax(value: object) -> tuple[int | None, str]:
    """Read a party size STRICTLY -- a cell is only ever "parsed" when it
    is unambiguous. Anything else is asked about, never guessed at, even
    when it contains a number.

    Returns (parsed_value, kind) where kind is one of:
      "blank"         -- cell is empty/None. Might be a section heading.
      "parsed"        -- an integer-valued number cell, or text that is
                          EXACTLY a bare run of digits (optionally with a
                          single trailing "," or "."), or EXACTLY
                          "<digits> <noun>" (e.g. "4 adults", "4 pax") --
                          and the resulting integer is 1-200 inclusive.
      "out_of_range"  -- the cell unambiguously names an integer, but it
                          is 0, negative, or above 200 (e.g. "0", "99999").
      "unparseable"   -- there is content, but it is not one of the forms
                          above -- a range ("4-6"), an open count ("4+"),
                          extra words ("2 adults + 1 child", "4 (TBC)"), a
                          non-integer ("4.5"), a date, or text with no
                          number in it at all ("four", "TBC"). This is a
                          real line item; the party size just isn't safe
                          to guess from it.

    "unparseable" and "out_of_range" both mean the same thing to every
    caller downstream: keep the line, never price it, ask the operator.
    They are kept distinct only so the question we ask can be worded
    precisely (see _pax_reason).
    """
    if value is None:
        return None, "blank"

    if isinstance(value, bool):
        # A checkbox-style cell is never a sane party size, and bool is a
        # subclass of int in Python -- guard explicitly so True/False
        # never sneak through the int branch below as pax 1/0.
        return None, "unparseable"

    if isinstance(value, int):
        return _bounded_pax(value)

    if isinstance(value, float):
        if value.is_integer():
            return _bounded_pax(int(value))
        return None, "unparseable"

    text = str(value).strip()
    if not text:
        return None, "blank"

    candidate = text[:-1] if text and text[-1] in ",." else text
    if _BARE_DIGITS.match(candidate):
        return _bounded_pax(int(candidate))

    noun_match = _DIGITS_WITH_NOUN.match(text)
    if noun_match and noun_match.group(2).lower() in _PAX_NOUNS:
        return _bounded_pax(int(noun_match.group(1)))

    return None, "unparseable"


def _bounded_pax(n: int) -> tuple[int, str]:
    if _MIN_PAX <= n <= _MAX_PAX:
        return n, "parsed"
    return n, "out_of_range"


def _pax_reason(kind: str, raw: str | None) -> str:
    if kind == "out_of_range":
        if raw == "0":
            return f'Party size reads "{raw}" — please confirm how many travellers.'
        return f'Party size reads "{raw}", which looks wrong — please confirm.'
    return (
        f'Could not read the number of travellers from '
        f'"{raw}" — please confirm the party size.'
    )


def _as_day_part(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None
