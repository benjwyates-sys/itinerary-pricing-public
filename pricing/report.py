"""Producing the deliverable: a costed copy, a summary, and an audit trail.

This is the presentation layer. It never decides a price (pricing/cost.py
does that) and it never mutates the operator's original file — every write
lands on a copy made by copy_for_write. The one house rule that matters
most here: a line that could not be priced must still show visible text in
the cost cell. A blank or a 0 reads as "free" to a human skimming a quote,
so needs_quote/unmatched lines always get "NEEDS QUOTE -- ..." or
"NOT MATCHED -- ..." text instead.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pricing.catalog import PriceChange
from pricing.cost import PricedLine
from pricing.itinerary_profile import ItineraryTemplate
from pricing.workbook import CellRef, Workbook, copy_for_write

# Machine-readable result of the Task 4b round-trip fidelity measurement.
# Read this, never the human-facing prose in docs/fidelity-findings.md --
# that document's wording can drift without breaking anything, and nothing
# should decide user-facing behaviour by grepping prose.
_FIDELITY_PATH = Path(__file__).resolve().parent.parent / "docs" / "fidelity.json"


def output_path(src: Path, today: Date) -> Path:
    """The costed copy's path: marked FINAL, dated, never overwriting.

    FINAL is on every costed sheet because every costed sheet is the client
    deliverable — it is not a "this one is the last" marker. The trailing
    counter is a safety net, not a version number: it appears only when a
    file of that exact name already exists, so re-costing a trip can never
    silently destroy a copy she may already have quoted from.
    """
    src = Path(src)
    base = f"{src.stem}_FINAL_{today.isoformat()}"
    candidate = src.with_name(f"{base}.xlsx")
    counter = 2
    while candidate.exists():
        candidate = src.with_name(f"{base}_{counter}.xlsx")
        counter += 1
    return candidate


def write_costed_workbook(src: Path, template: ItineraryTemplate,
                          priced: list[PricedLine], today: Date) -> Path:
    """Copy src, fill in the cost column on the copy, and return its path.

    src itself is never opened for writing -- copy_for_write byte-copies it
    first, so the operator's original itinerary is untouched no matter what
    happens afterwards.

    The costed copy is built entirely under a hidden temp name next to the
    destination, and only moved into place (os.replace, atomic on the same
    filesystem) once wb.save() has actually succeeded. If anything raises
    -- copy_for_write, a write, or save() itself (e.g. WorkbookLockedError)
    -- the temp file is removed and the exception re-raised unchanged, so a
    disk-full or killed-mid-write failure can never leave a file sitting at
    the destination path that looks like a finished quote but has a blank
    cost column.
    """
    dst = output_path(src, today)
    tmp = dst.with_name(f".{dst.stem}.tmp-{os.getpid()}{dst.suffix}")
    try:
        copy_for_write(src, tmp)

        wb = Workbook(tmp)
        try:
            column = template.roles["cost"]
            for line in priced:
                ref = CellRef(template.sheet, column, line.row)
                wb.write(ref, _cell_value(line))
            wb.save()
        finally:
            wb.close()
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    os.replace(tmp, dst)
    return dst


def _cell_value(line: PricedLine) -> object:
    """What goes in the cost cell -- a real number, or visible text.

    Never an empty string, never 0 for a line that wasn't actually priced
    at zero: either would read as "free" to someone skimming the quote.

    pricing.patterns.evaluate already refuses to produce a non-positive
    total (see NeedsQuote there), so a "priced" line with total <= 0
    should never reach here in practice. This module is the last stop
    before a number is written into a document sent to a paying client,
    so it treats that combination as unpriced anyway, on its own, rather
    than trusting an upstream invariant it has no way to verify.
    """
    if line.status == "priced" and line.total is not None:
        if line.total > 0:
            # Decimal -> float at the openpyxl boundary is fine here:
            # this is the presentation layer, not a pricing calculation.
            # The float never flows back into pricing.cost or
            # pricing.catalog.
            return float(line.total)
        return ("NEEDS QUOTE — priced at "
                f"{line.total} — a zero or negative total needs "
                "confirming before this can be quoted.")
    if line.status == "needs_quote":
        return f"NEEDS QUOTE — {line.reason or 'please confirm and requote.'}"
    return f"NOT MATCHED — {line.reason or 'no candidate chosen.'}"


def summarize(priced: list[PricedLine], changes: list[PriceChange]) -> dict:
    """Counts, per-currency totals, price-drift notes, and warnings.

    totals_by_currency is a mapping, not a single number -- mixed-currency
    itineraries must never be silently summed into one meaningless total.

    A priced line with a missing or empty currency is still money that must
    stay visible: it is bucketed under the sentinel key "UNKNOWN" rather
    than dropped or folded into some other currency's total, and a warning
    names how many lines this happened to. pricing.cost always sets
    currency alongside total today, so this is currently unreachable in
    practice -- but summarize is the safety boundary and should not rely on
    an invariant it has no way to see.
    """
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    missing_currency = 0
    for line in priced:
        if line.status == "priced" and line.total is not None:
            if line.currency:
                totals[line.currency] += line.total
            else:
                totals["UNKNOWN"] += line.total
                missing_currency += 1

    warnings = _warnings()
    if missing_currency:
        noun = "line" if missing_currency == 1 else "lines"
        warnings.append(
            f"{missing_currency} priced {noun} had no currency and "
            'were totalled under "UNKNOWN".'
        )

    return {
        "priced": sum(1 for p in priced if p.status == "priced"),
        "needs_quote": sum(1 for p in priced if p.status == "needs_quote"),
        "unmatched": sum(1 for p in priced if p.status == "unmatched"),
        "totals_by_currency": {k: str(v) for k, v in sorted(totals.items())},
        "price_changes": [
            {"cell": c.cell, "was": str(c.last_seen), "now": str(c.current)}
            for c in changes
        ],
        "warnings": warnings,
    }


def _warnings() -> list[str]:
    """Carry forward what Task 4b measured about round-trip fidelity.

    Reads the machine-readable docs/fidelity.json rather than grepping the
    human-facing findings prose, so that editing that document's wording
    can never silently change what the operator is told. A missing or
    unparseable file means no warning is emitted -- we only warn about a
    measured fact, never guess one.
    """
    if not _FIDELITY_PATH.exists():
        return []
    try:
        measured = json.loads(_FIDELITY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(measured, dict):
        return []
    if measured.get("images_survive_roundtrip") is False:
        return ["Note: your itinerary's logo is not carried into the costed copy."]
    return []


def write_run_log(runs_dir: Path, payload: dict) -> Path:
    """Append-only audit trail: one JSON file per run, never overwritten."""
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)

    stamp = f"{datetime.now():%Y-%m-%dT%H-%M-%S}"
    candidate = runs_dir / f"{stamp}.json"
    counter = 2
    while candidate.exists():
        candidate = runs_dir / f"{stamp}_{counter}.json"
        counter += 1

    candidate.write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return candidate
