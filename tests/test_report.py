import json
from datetime import date
from decimal import Decimal

import pytest

from pricing.catalog import PriceChange
from pricing.cost import PricedLine
from pricing.itinerary_profile import propose_template
from pricing import report
from pricing.report import output_path, summarize, write_costed_workbook, write_run_log
from pricing.workbook import CellRef, Workbook

PRICED = [
    PricedLine(row=8, raw_name="Uffizi", item_id="IT-1", status="priced",
               total=Decimal("1300.00"), currency="EUR"),
    PricedLine(row=9, raw_name="Vatican", item_id="IT-2", status="needs_quote",
               reason="14 pax is above the highest mapped tier (10 pax)."),
    PricedLine(row=10, raw_name="Catamaran", status="unmatched",
               reason="No confident match — please choose."),
]


def test_output_path_is_dated_and_never_overwrites(tmp_path):
    src = tmp_path / "Trip_Smith.xlsx"
    src.write_bytes(b"x")
    first = output_path(src, date(2026, 9, 3))
    assert first.name == "Trip_Smith_FINAL_2026-09-03.xlsx"
    first.write_bytes(b"x")
    assert output_path(src, date(2026, 9, 3)).name == "Trip_Smith_FINAL_2026-09-03_2.xlsx"


def test_writes_totals_and_leaves_the_original_alone(itinerary):
    before = itinerary.read_bytes()
    template = propose_template(Workbook(itinerary), "Itinerary")
    out = write_costed_workbook(itinerary, template, PRICED, date(2026, 9, 3))

    wb = Workbook(out)
    assert wb.read(CellRef("Itinerary", "E", 8)) == 1300.00
    assert itinerary.read_bytes() == before


def test_unpriced_lines_are_never_blank(itinerary):
    template = propose_template(Workbook(itinerary), "Itinerary")
    out = write_costed_workbook(itinerary, template, PRICED, date(2026, 9, 3))
    wb = Workbook(out)
    assert "NEEDS QUOTE" in str(wb.read(CellRef("Itinerary", "E", 9)))
    assert "NOT MATCHED" in str(wb.read(CellRef("Itinerary", "E", 10)))


# --- C1: a non-positive total is never written as a number ---------------
#
# pricing.patterns.evaluate already refuses to produce a "priced" outcome
# with a non-positive total (see tests/test_patterns.py), so this
# shouldn't happen via the normal cost pipeline any more. But report.py is
# the last stop before a number lands in a document sent to a paying
# client, so it must not trust that upstream invariant blindly -- these
# tests construct the anomalous PricedLine directly (bypassing patterns.py
# entirely) to prove this layer holds on its own.

def test_zero_total_priced_line_is_never_written_as_a_number(itinerary):
    lines = [PricedLine(row=8, raw_name="Uffizi", item_id="IT-1", status="priced",
                        total=Decimal("0.00"), currency="EUR")]
    template = propose_template(Workbook(itinerary), "Itinerary")
    out = write_costed_workbook(itinerary, template, lines, date(2026, 9, 3))
    wb = Workbook(out)
    cell = wb.read(CellRef("Itinerary", "E", 8))
    assert not isinstance(cell, (int, float))
    assert "NEEDS QUOTE" in str(cell)


def test_negative_total_priced_line_is_never_written_as_a_number(itinerary):
    lines = [PricedLine(row=8, raw_name="Uffizi", item_id="IT-1", status="priced",
                        total=Decimal("-50.00"), currency="EUR")]
    template = propose_template(Workbook(itinerary), "Itinerary")
    out = write_costed_workbook(itinerary, template, lines, date(2026, 9, 3))
    wb = Workbook(out)
    cell = wb.read(CellRef("Itinerary", "E", 8))
    assert not isinstance(cell, (int, float))
    assert "NEEDS QUOTE" in str(cell)


def test_failed_save_leaves_no_file_at_destination(itinerary, monkeypatch):
    """Finding 1: a save() failure must never leave a costed-looking file
    behind at the destination path -- the temp file it was building must
    be cleaned up, and the original source must be untouched."""
    before = itinerary.read_bytes()
    template = propose_template(Workbook(itinerary), "Itinerary")
    today = date(2026, 9, 3)
    dst = output_path(itinerary, today)

    def boom(self):
        raise OSError("disk full")

    monkeypatch.setattr(Workbook, "save", boom)

    with pytest.raises(OSError):
        write_costed_workbook(itinerary, template, PRICED, today)

    assert itinerary.read_bytes() == before
    assert not dst.exists()
    # No stray temp file left behind either.
    assert list(itinerary.parent.glob(f".{dst.stem}.tmp-*{dst.suffix}")) == []


def test_locked_destination_message_survives_failed_save(itinerary, monkeypatch):
    """WorkbookLockedError must still reach the caller with its message
    intact, and still leave nothing at the destination."""
    from pricing.workbook import WorkbookLockedError

    template = propose_template(Workbook(itinerary), "Itinerary")
    today = date(2026, 9, 3)
    dst = output_path(itinerary, today)

    def locked(self):
        raise WorkbookLockedError("Please close it in Excel and try again.")

    monkeypatch.setattr(Workbook, "save", locked)

    with pytest.raises(WorkbookLockedError, match="Please close it in Excel"):
        write_costed_workbook(itinerary, template, PRICED, today)

    assert not dst.exists()


def test_summary_counts_and_totals_by_currency():
    summary = summarize(PRICED, [PriceChange("Italy!D4", Decimal("285"), Decimal("310"))])
    assert summary["priced"] == 1
    assert summary["needs_quote"] == 1
    assert summary["unmatched"] == 1
    assert summary["totals_by_currency"] == {"EUR": "1300.00"}
    assert len(summary["price_changes"]) == 1


def test_mixed_currencies_are_totalled_separately():
    lines = PRICED + [PricedLine(row=11, raw_name="Safari", item_id="ZA-1",
                                 status="priced", total=Decimal("500.00"), currency="USD")]
    assert summarize(lines, [])["totals_by_currency"] == {"EUR": "1300.00", "USD": "500.00"}


def test_priced_lines_missing_currency_land_under_unknown_and_reconcile():
    """Finding 2: priced lines with no currency must not vanish from the
    totals -- they land under the sentinel "UNKNOWN" key, and the sum of
    every bucket (including UNKNOWN) must equal the sum of all priced
    totals. A warning must call out how many lines this happened to."""
    lines = [
        PricedLine(row=8, raw_name="Uffizi", item_id="IT-1", status="priced",
                   total=Decimal("1300.00"), currency="EUR"),
        PricedLine(row=11, raw_name="Mystery A", item_id="ZZ-1", status="priced",
                   total=Decimal("50.00"), currency=None),
        PricedLine(row=12, raw_name="Mystery B", item_id="ZZ-2", status="priced",
                   total=Decimal("35.00"), currency=""),
    ]

    summary = summarize(lines, [])

    assert summary["priced"] == 3
    assert summary["totals_by_currency"]["UNKNOWN"] == "85.00"
    assert summary["totals_by_currency"]["EUR"] == "1300.00"

    reconciled = sum(Decimal(v) for v in summary["totals_by_currency"].values())
    expected = sum((line.total for line in lines), Decimal("0"))
    assert reconciled == expected

    assert any("UNKNOWN" in w and "2" in w for w in summary["warnings"])


def test_run_log_is_written(tmp_path):
    path = write_run_log(tmp_path / "runs", {"summary": {"priced": 1}})
    assert path.exists() and path.suffix == ".json"


def test_no_logo_warning_when_images_survive(tmp_path, monkeypatch):
    fidelity = tmp_path / "fidelity.json"
    fidelity.write_text(json.dumps({"images_survive_roundtrip": True}))
    monkeypatch.setattr(report, "_FIDELITY_PATH", fidelity)
    assert summarize(PRICED, [])["warnings"] == []


def test_logo_warning_when_images_do_not_survive(tmp_path, monkeypatch):
    fidelity = tmp_path / "fidelity.json"
    fidelity.write_text(json.dumps({"images_survive_roundtrip": False}))
    monkeypatch.setattr(report, "_FIDELITY_PATH", fidelity)
    warnings = summarize(PRICED, [])["warnings"]
    assert any("logo" in w for w in warnings)


def test_no_warning_when_fidelity_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "_FIDELITY_PATH", tmp_path / "does-not-exist.json")
    assert summarize(PRICED, [])["warnings"] == []


def test_no_warning_when_fidelity_file_unparseable(tmp_path, monkeypatch):
    fidelity = tmp_path / "fidelity.json"
    fidelity.write_text("not json{{{")
    monkeypatch.setattr(report, "_FIDELITY_PATH", fidelity)
    assert summarize(PRICED, [])["warnings"] == []
