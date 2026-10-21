"""Trust-building reports.

verify_itinerary re-costs work the operator already did by hand and diffs
it — the acceptance test that neither developer nor model can run, because
only she has the data.

refresh sweeps the catalog against the live workbook and reports what moved.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from pricing.catalog import Catalog, FingerprintMismatch, resolve_rates
from pricing.cost import parse_itinerary, price_lines
from pricing.itinerary_profile import ItineraryTemplate
from pricing.match import Aliases, candidates
from pricing.money import MoneyParseError, parse_money
from pricing.workbook import CellRef, Workbook


@dataclass
class LineDiff:
    row: int
    name: str
    expected: Decimal | None
    computed: Decimal | None
    delta: Decimal | None
    status: str
    # Which catalog item was actually priced, and how confident the match
    # was -- see match_confidence below. None only when nothing was priced
    # at all (e.g. an empty catalog: match_confidence == "none").
    item_id: str | None
    # "auto_accept": the top candidate had Candidate.auto_accept True
    #   (identical-after-normalisation, or a saved alias). A mismatch here
    #   means the RATE is wrong -- the match itself is confirmed.
    # "top_guess": forced onto the top candidate despite auto_accept being
    #   False. A mismatch here means CHECK THE MATCH FIRST -- the computed
    #   total may be right for the wrong catalog item, or wrong because the
    #   guess was wrong, and a match doesn't rule that out either (the guess
    #   was probably right, but unconfirmed).
    # "none": no candidate at all -- nothing was priced.
    match_confidence: str


def verify_itinerary(src: Path, template: ItineraryTemplate, catalog: Catalog,
                     aliases: Aliases, wb_rates: Workbook) -> tuple[list[LineDiff], dict]:
    wb = Workbook(src)
    lines, skipped_rows = parse_itinerary(wb, template)

    # verify re-costs work the operator already did by hand -- it is not a
    # live quote, so unlike a normal costing run it does not stop to ask
    # about an unconfident match (see pricing/match.py's module docstring
    # for why auto_accept exists at all). It takes the catalog's best guess
    # for every line instead. Forcing a guess is necessary -- otherwise
    # verify could never price the very lines it most needs to check -- but
    # the confidence of that guess is recorded per line (match_confidence)
    # rather than thrown away, so a mismatch caused by a bad MATCH is never
    # indistinguishable from a mismatch caused by a bad RATE.
    forced_resolutions: dict[int, str] = {}
    match_confidence: dict[int, str] = {}
    for line in lines:
        ranked = candidates(line.raw_name, catalog.items, aliases)
        if ranked:
            forced_resolutions[line.row] = ranked[0].item_id
            match_confidence[line.row] = "auto_accept" if ranked[0].auto_accept else "top_guess"
        else:
            match_confidence[line.row] = "none"

    priced, _ = price_lines(lines, catalog, aliases, wb_rates, forced_resolutions)
    cost_column = template.roles["cost"]

    diffs: list[LineDiff] = []
    for line in priced:
        raw = wb.read(CellRef(template.sheet, cost_column, line.row))
        try:
            expected = parse_money(raw)
        except MoneyParseError:
            expected = None
        if expected is not None:
            # Quantised to cents for display consistency with `computed`
            # and `delta`, which are already cents -- this is purely a
            # presentation fix and does not change any comparison above,
            # since Decimal("1300") == Decimal("1300.00").
            expected = expected.quantize(Decimal("0.01"))

        computed = line.total
        if computed is None:
            status, delta = "not_priced", None
        elif expected is None:
            status, delta = "no_expected", None
        elif expected == computed:
            status, delta = "match", Decimal("0.00")
        else:
            status, delta = "mismatch", abs(computed - expected)

        # item_id comes from forced_resolutions, not from line.item_id: a
        # line whose pax cell is unparseable (e.g. "4-6") short-circuits in
        # price_lines before it ever sets PricedLine.item_id, even though a
        # candidate was found and forced above. Reading it back off the
        # PricedLine would leave item_id None while match_confidence claims
        # "auto_accept"/"top_guess" -- a contradiction this field's own
        # docstring rules out.
        diffs.append(LineDiff(line.row, line.raw_name, expected, computed, delta, status,
                              forced_resolutions.get(line.row), match_confidence.get(line.row, "none")))

    summary = {
        "matches": sum(1 for d in diffs if d.status == "match"),
        "mismatches": sum(1 for d in diffs if d.status == "mismatch"),
        "not_priced": sum(1 for d in diffs if d.status == "not_priced"),
        "no_expected": sum(1 for d in diffs if d.status == "no_expected"),
        "top_guesses": sum(1 for d in diffs if d.match_confidence == "top_guess"),
        # C3 (code review): a row parse_itinerary left out because its pax
        # cell was blank must stay visible here too -- verify is the trust
        # step, and a line silently missing from it is exactly the failure
        # mode it exists to catch.
        "skipped_rows": skipped_rows,
    }
    return diffs, summary


def refresh(catalog: Catalog, wb_rates: Workbook) -> dict:
    changes: list[dict] = []
    broken: list[dict] = []
    unprotected: list[dict] = []

    for item in catalog.items:
        # C2 (code review): an item with no fingerprints resolves rates
        # just fine -- resolve_rates skips verification when a fingerprint
        # is empty (that is what "unverified" means) -- but it is silently
        # exposed to structural drift the next time the sheet changes
        # shape. catalog-add now refuses to save one without an explicit
        # --unprotected (see pricing/cli.py), but items saved before that
        # existed, or saved deliberately unprotected, still need to be
        # visible here -- in their own list, not mixed into broken_items
        # (which means "cannot price at all right now") or price_changes
        # (purely informational).
        if not item.row_fingerprint or not item.structure_fingerprint:
            unprotected.append({"id": item.id, "name": item.name})

        try:
            _, item_changes = resolve_rates(item, wb_rates)
        except FingerprintMismatch as exc:
            broken.append({"id": item.id, "name": item.name, "message": str(exc)})
            continue
        changes.extend(
            {"id": item.id, "name": item.name, "cell": c.cell,
             "was": str(c.last_seen), "now": str(c.current)}
            for c in item_changes
        )

    return {"checked": len(catalog.items), "price_changes": changes,
            "broken_items": broken, "unprotected_items": unprotected}
