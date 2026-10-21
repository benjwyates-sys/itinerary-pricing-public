"""Generate a realistic Dubrovnik sample dataset for trying the tool out.

Run:  uv run python samples/build_samples.py

Produces a costing workbook, an itinerary to price, and a hand-priced
itinerary to check against — plus CSV copies of every sheet so they can be
read without Excel.

The rates here are invented. The SHAPES are the point: a title block above
the headers, a merged category band, tiers as rows, per-group and per-person
units, time-of-day and seasonal supplements, a minimum billable party size,
a blackout date, a rate typed as text, an "on request" line, and two pairs of
near-identically-named experiences. Those are the things that break parsers.
"""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------- rate sheet

DUBROVNIK_HEADERS = [
    "Experience", "Min Pax", "Max Pax", "Net Rate", "Unit",
    "PM Supplement", "Peak Supplement", "Notes",
]

# (experience, min_pax, max_pax, rate, unit, pm_supp, peak_supp, notes)
DUBROVNIK_ROWS = [
    ("Old Town Walking Tour — Private Guide", 1, 6, 180, "per group", None, None,
     "2 hours. Guide fee only, no entries."),
    ("Old Town Walking Tour — Private Guide", 7, 15, 260, "per group", None, None,
     "Same tour, larger group."),
    ("Old Town Walking Tour — Small Group", 1, 18, 45, "per person", None, None,
     "Shared departure, 10:00 daily."),
    ("Game of Thrones Walking Tour", 1, 16, 38, "per person", None, None, None),
    ("Cable Car & Fort Imperial Entry", 1, 30, 27, "per person", None, None,
     "Entry only, no guide."),
    ("Trsteno Arboretum Entry", 1, 40, 12, "per person", None, None, None),
    # blank row 13 splits the block on purpose
    (None, None, None, None, None, None, None, None),
    ("Elafiti Islands Full-Day Cruise", 2, 8, 95, "per person", None, None,
     "Min 2 pax. Lunch included."),
    ("Elafiti Islands Full-Day Cruise", 9, 20, 82, "per person", None, None,
     "Larger group rate."),
    ("Sea Kayaking — Old Town Walls", 2, 12, 48, "per person", 12, None,
     "PM departure is the sunset paddle."),
    ("Konavle Valley Wine Tasting — Half Day", 2, 14, 78, "per person", None, 14,
     "Peak = 15 Jun – 15 Sep."),
    ("Cooking Class — Gruž Market & Lunch", 1, 10, 110, "per person", None, None,
     "Billed for 4 minimum."),
    ("Ston Oysters & Walls Day Trip", 2, 12, "€85", "per person", None, None,
     "Rate typed as text on the supplier's sheet."),
    ("Private Yacht Charter — Full Day", 1, 10, 1850, "per group", None, None,
     "Not available 15 Aug (Assumption)."),
    ("Bespoke Photography Session", 1, 6, "on request", "per person", None, None,
     "Quote per enquiry."),
    ("Private Transfer — Dubrovnik Airport (DBV) to Old Town", 1, 3, 42, "per group",
     None, None, None),
    ("Private Transfer — Dubrovnik Airport (DBV) to Old Town", 4, 8, 68, "per group",
     None, None, None),
    ("Private Transfer — Old Town to Dubrovnik Airport (DBV)", 1, 3, 42, "per group",
     None, None, "Same vehicle, return direction."),
    ("Private Transfer — Old Town to Dubrovnik Airport (DBV)", 4, 8, 68, "per group",
     None, None, None),
]

SPLIT_HEADERS = ["Experience", "Min Pax", "Max Pax", "Net Rate", "Unit", "Notes"]
SPLIT_ROWS = [
    ("Diocletian's Palace — Private Guide", 1, 8, 165, "per group", "90 minutes."),
    ("Blue Cave & Hvar Speedboat Tour", 2, 10, 145, "per person", "Full day."),
    ("Krka Waterfalls Day Trip", 2, 16, 98, "per person", "Entry included."),
]


def build_costing_workbook(path: Path) -> Path:
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "Dubrovnik"
    ws["A1"] = "DUBROVNIK & SOUTHERN DALMATIA — NET RATES 2026"
    ws["A1"].font = Font(bold=True, size=13)
    ws.merge_cells("A1:H1")
    ws["A2"] = "All rates in EUR, net to agent. Valid 01 Apr – 31 Oct 2026."
    ws["A3"] = "Peak season 15 Jun – 15 Sep. Rates exclude city tax."

    # A merged category band sitting ABOVE the real header row. This is the
    # shape that fools a naive "first row with several text cells" guess —
    # the tool should offer both row 5 and row 6 and let you choose.
    ws["A5"] = "Group Size & Rates"
    ws.merge_cells("A5:E5")
    ws["F5"] = "Supplements"
    ws.merge_cells("F5:G5")
    ws["H5"] = "Notes"
    for cell in ("A5", "F5", "H5"):
        ws[cell].font = Font(bold=True, italic=True)
        ws[cell].alignment = Alignment(horizontal="center")

    for col, header in enumerate(DUBROVNIK_HEADERS, start=1):
        c = ws.cell(row=6, column=col, value=header)
        c.font = Font(bold=True)

    for offset, row in enumerate(DUBROVNIK_ROWS):
        for col, value in enumerate(row, start=1):
            if value is not None:
                ws.cell(row=7 + offset, column=col, value=value)

    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["H"].width = 38

    ws2 = wb.create_sheet("Split & Hvar")
    ws2["A1"] = "SPLIT & HVAR — NET RATES 2026"
    ws2["A1"].font = Font(bold=True, size=13)
    ws2.merge_cells("A1:F1")
    ws2["A2"] = "All rates in EUR, net to agent."
    for col, header in enumerate(SPLIT_HEADERS, start=1):
        ws2.cell(row=4, column=col, value=header).font = Font(bold=True)
    for offset, row in enumerate(SPLIT_ROWS):
        for col, value in enumerate(row, start=1):
            if value is not None:
                ws2.cell(row=5 + offset, column=col, value=value)
    ws2.column_dimensions["A"].width = 40

    wb.save(path)
    return path


# --------------------------------------------------------------- itineraries

ITINERARY_HEADERS = ["Experience", "Date", "Pax", "Time", "Net Cost"]

# Deliberately worded the way an agent types, NOT the way the rate sheet reads.
# Two lines match the catalog EXACTLY so you can watch auto-accept work; the
# rest should stop and ask you.
SAMPLE_LINES = [
    ("Airport transfer on arrival",              "2026-06-08", 5, "AM", None),
    ("Old Town walking tour (private)",          "2026-06-08", 5, "PM", None),
    ("Game of Thrones Walking Tour",             "2026-06-09", 5, "AM", None),
    ("Elafiti islands cruise",                   "2026-06-10", 5, "AM", None),
    ("Sunset sea kayaking",                      "2026-06-10", 5, "PM", None),
    ("Trsteno Arboretum Entry",                  "2026-06-11", 5, "AM", None),
    ("Cooking class at Gruz market",             "2026-06-11", 2, "PM", None),
    ("Konavle wine tasting",                     "2026-07-02", 5, "AM", None),
    ("Private yacht charter",                    "2026-08-15", 5, "AM", None),
    ("Bespoke photography session",              "2026-06-12", 5, "AM", None),
    ("Airport transfer on departure",            "2026-06-12", 5, "PM", None),
]

# Uses the rate sheet's exact wording, and the Net Cost column is already
# filled with the correct hand-calculated answer. This is the /verify test.
#
#   Transfer DBV → Old Town, 4 pax        per group, 4–8 tier          68.00
#   Old Town Walking Tour private, 4 pax  per group, 1–6 tier         180.00
#   Elafiti cruise, 4 pax                 per person 95 × 4           380.00
#   Konavle wine tasting, 4 pax, 14 May   shoulder, 78 × 4            312.00
#   Cooking class, 4 pax                  per person 110 × 4          440.00
#   Cable car, 4 pax                      per person 27 × 4           108.00
#   Sea kayaking PM, 4 pax                (48 + 12) × 4, PM supp      240.00
#                                                          TOTAL    1,728.00
SAMPLE_PRICED_LINES = [
    ("Private Transfer — Dubrovnik Airport (DBV) to Old Town", "2026-05-12", 4, "AM", 68.00),
    ("Old Town Walking Tour — Private Guide",                  "2026-05-12", 4, "PM", 180.00),
    ("Elafiti Islands Full-Day Cruise",                        "2026-05-13", 4, "AM", 380.00),
    ("Konavle Valley Wine Tasting — Half Day",                 "2026-05-14", 4, "AM", 312.00),
    ("Cooking Class — Gruž Market & Lunch",                    "2026-05-15", 4, "PM", 440.00),
    ("Cable Car & Fort Imperial Entry",                        "2026-05-16", 4, "AM", 108.00),
    ("Sea Kayaking — Old Town Walls",                          "2026-05-16", 4, "PM", 240.00),
]


def build_itinerary(path: Path, title: str, subtitle: str, lines) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = subtitle
    ws["A3"] = "Prepared by: Sample Travel"

    for col, header in enumerate(ITINERARY_HEADERS, start=1):
        ws.cell(row=5, column=col, value=header).font = Font(bold=True)

    for offset, (name, date, pax, time, cost) in enumerate(lines):
        r = 6 + offset
        ws.cell(row=r, column=1, value=name)
        ws.cell(row=r, column=2, value=date)
        ws.cell(row=r, column=3, value=pax)
        ws.cell(row=r, column=4, value=time)
        if cost is not None:
            ws.cell(row=r, column=5, value=cost)

    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["E"].width = 14
    wb.save(path)
    return path


# ----------------------------------------------------------------- csv views


def export_csvs(xlsx: Path, out_dir: Path) -> list[Path]:
    """A readable copy of every sheet, for looking at without Excel."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    wb = openpyxl.load_workbook(xlsx)
    for sheet in wb.worksheets:
        safe = sheet.title.replace(" ", "_").replace("&", "and")
        dest = out_dir / f"{xlsx.stem}__{safe}.csv"
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            for row in sheet.iter_rows(values_only=True):
                writer.writerow(["" if v is None else v for v in row])
        written.append(dest)
    wb.close()
    return written


def main() -> None:
    costing = build_costing_workbook(HERE / "Dubrovnik_Costing_2026.xlsx")
    sample = build_itinerary(
        HERE / "Trip_Sample_Dubrovnik.xlsx",
        "SAMPLE PARTY — DUBROVNIK",
        "8–12 June 2026 · 5 travellers",
        SAMPLE_LINES,
    )
    sample_priced = build_itinerary(
        HERE / "Trip_Sample_Dubrovnik_PRICED.xlsx",
        "SAMPLE PARTY — DUBROVNIK",
        "12–16 May 2026 · 4 travellers · priced by hand",
        SAMPLE_PRICED_LINES,
    )

    csv_dir = HERE / "csv-copies"
    for book in (costing, sample, sample_priced):
        export_csvs(book, csv_dir)

    print("Wrote:")
    for p in (costing, sample, sample_priced):
        print(f"  {p.relative_to(HERE.parent)}")
    print(f"  {csv_dir.relative_to(HERE.parent)}/ ({len(list(csv_dir.glob('*.csv')))} csv files)")


if __name__ == "__main__":
    main()
