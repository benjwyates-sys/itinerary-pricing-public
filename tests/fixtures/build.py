"""Synthetic workbooks standing in for the real, proprietary files.

Nine layouts spanning the shapes rate sheets and itineraries actually take.
Two are deliberately adversarial (multiheader, wide itinerary): the engine is
expected to notice it cannot be sure, not to guess well.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl


# ---------------------------------------------------------------- costing


def build_rate_sheet(path: Path) -> Path:
    """Baseline: one row per price point, tiers expressed as extra rows."""
    wb = openpyxl.Workbook()

    italy = wb.active
    italy.title = "Italy"
    italy["A1"] = "ITALY — NET RATES 2026"
    italy["A2"] = "All rates in EUR, per person unless stated"
    for col, header in zip("ABCDEF", ["Experience", "Min Pax", "Max Pax",
                                      "Net Rate", "Unit", "PM Supplement"]):
        italy[f"{col}3"] = header
    italy["A4"] = "Uffizi Gallery — Private Guided Tour"
    italy["B4"], italy["C4"], italy["D4"], italy["E4"], italy["F4"] = 1, 4, 285, "per person", 40
    italy["A5"] = "Uffizi Gallery — Private Guided Tour"
    italy["B5"], italy["C5"], italy["D5"], italy["E5"], italy["F5"] = 5, 10, 240, "per person", 40
    italy["A6"] = "Vatican Museums — Skip the Line"
    italy["B6"], italy["C6"], italy["D6"], italy["E6"] = 1, 12, 95, "per person"
    italy["A7"] = "Private Transfer — FCO to Rome Centre"
    italy["B7"], italy["C7"], italy["D7"], italy["E7"] = 1, 3, 110, "per group"
    italy.merge_cells("A1:F1")

    greece = wb.create_sheet("Greece")
    greece["A1"] = "GREECE — NET RATES 2026"
    for col, header in zip("ABCDE", ["Experience", "Min Pax", "Max Pax", "Net Rate", "Unit"]):
        greece[f"{col}3"] = header
    greece["A4"] = "Catamaran Cruise — PM (beverages incl.)"
    greece["B4"], greece["C4"], greece["D4"], greece["E4"] = 2, 8, 165, "per person"

    wb.save(path)
    return path


def build_wide_rate_sheet(path: Path) -> Path:
    """Pax bands as columns — the layout that breaks row-per-tier parsing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Japan"
    ws["A1"] = "JAPAN — NET RATES 2026 (EUR)"
    ws.merge_cells("A1:F1")
    for col, header in zip("ABCDEF", ["Experience", "1-4 Pax", "5-10 Pax", "11+ Pax",
                                      "PM Supplement", "Unit"]):
        ws[f"{col}3"] = header
    ws["A4"] = "Tea Ceremony — Gion"
    ws["B4"], ws["C4"], ws["D4"], ws["E4"], ws["F4"] = 120, 95, 80, 15, "per person"
    ws["A5"] = "Tsukiji Market Walking Tour"
    ws["B5"], ws["C5"], ws["D5"], ws["F5"] = 85, 70, 60, "per person"
    ws["A6"] = "Private Transfer — HND to Shinjuku"
    ws["B6"], ws["C6"], ws["D6"], ws["F6"] = 140, 140, 140, "per group"
    wb.save(path)
    return path


def build_stacked_rate_sheet(path: Path) -> Path:
    """Season rows with explicit date ranges, and a second currency."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SouthAfrica"
    ws["A1"] = "SOUTH AFRICA — NET RATES 2026/27"
    for col, header in zip("ABCDEFGH", ["Experience", "Season", "From", "To",
                                        "Min Pax", "Max Pax", "Net Rate", "Currency"]):
        ws[f"{col}3"] = header
    ws["A4"] = "Table Mountain — Private Guide"
    ws["B4"], ws["C4"], ws["D4"] = "Green", "2026-05-01", "2026-09-30"
    ws["E4"], ws["F4"], ws["G4"], ws["H4"] = 1, 6, 180, "USD"
    ws["A5"] = "Table Mountain — Private Guide"
    ws["B5"], ws["C5"], ws["D5"] = "Peak", "2026-10-01", "2027-04-30"
    ws["E5"], ws["F5"], ws["G5"], ws["H5"] = 1, 6, 240, "USD"
    ws["A6"] = "Cape Point — Full Day"
    ws["B6"] = "All Year"
    ws["E6"], ws["F6"], ws["G6"], ws["H6"] = 1, 8, 310, "USD"
    wb.save(path)
    return path


def build_nasty_sheet(path: Path) -> Path:
    """Parsing robustness: text rates, European notation, a gap, a non-price."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Odd"
    ws["A1"] = "MISCELLANEOUS"
    ws["A2"], ws["B2"], ws["C2"] = "Experience", "Pax", "Rate"
    ws["A3"], ws["B3"], ws["C3"] = "Cooking Class — Trastevere", 6, "€285"
    ws["A4"], ws["B4"], ws["C4"] = "Wine Tasting — Chianti", 4, "1.234,50"
    # row 5 intentionally blank — splits the data block
    ws["A6"], ws["B6"], ws["C6"] = "Truffle Hunt — Umbria", 2, "on request"
    wb.save(path)
    return path


def build_multiheader_sheet(path: Path) -> Path:
    """Adversarial: a merged category band above the real header row.

    Row 3 has three text cells, so a naive 'first row with 3+ text cells'
    heuristic picks it — and is wrong. The real header is row 4.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Portugal"
    ws["A1"] = "PORTUGAL — NET RATES 2026"
    ws["A3"], ws["D3"], ws["E3"] = "Group Size Pricing", "Supplements", "Notes"
    ws.merge_cells("A3:C3")
    for col, header in zip("ABCDE", ["Experience", "1-4", "5-10", "PM", "Notes"]):
        ws[f"{col}4"] = header
    ws["A5"] = "Douro Valley Wine Tour"
    ws["B5"], ws["C5"], ws["D5"] = 210, 175, 25
    ws["A6"] = "Sintra & Cascais Day Trip"
    ws["B6"], ws["C6"] = 195, 160
    wb.save(path)
    return path


def build_formula_sheet(path: Path) -> Path:
    """Sheet with both literal and formula cells, for testing is_formula()."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rates"
    ws["A1"] = "Experience"
    ws["B1"] = "Base Rate"
    ws["C1"] = "Discounted Rate"
    ws["A2"] = "Tour A"
    ws["B2"] = 100
    ws["C2"] = "=B2*0.9"  # Formula: 10% discount
    ws["A3"] = "Tour B"
    ws["B3"] = 200
    ws["C3"] = 180  # Literal value
    wb.save(path)
    return path


# -------------------------------------------------------------- itinerary


def build_itinerary(path: Path) -> Path:
    """Baseline: a title block, then one row per line item."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"] = "SMITH FAMILY — ITALY & GREECE"
    ws["A2"] = "14–24 June 2026"
    ws["A3"] = "Prepared by: Travel Agency"
    for col, header in zip("ABCDE", ["Experience", "Date", "Pax", "Time", "Net Cost"]):
        ws[f"{col}7"] = header
    ws["A8"] = "Uffizi Gallery private tour"
    ws["B8"], ws["C8"], ws["D8"] = "2026-06-15", 4, "PM"
    ws["A9"] = "Vatican Museums skip the line"
    ws["B9"], ws["C9"], ws["D9"] = "2026-06-17", 4, "AM"
    ws["A10"] = "Sunset catamaran w/ open bar"
    ws["B10"], ws["C10"], ws["D10"] = "2026-06-21", 4, "PM"
    wb.save(path)
    return path


def build_day_grouped_itinerary(path: Path) -> Path:
    """Day headings interleaved with line items.

    The headings have a name but no pax — that is how a parser tells them
    apart from real line items.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"] = "JONES PARTY — ITALY"
    for col, header in zip("ABCDE", ["Experience", "Date", "Pax", "Time", "Net Cost"]):
        ws[f"{col}5"] = header
    ws["A6"] = "DAY 1 — FLORENCE"
    ws["A7"] = "Uffizi Gallery private tour"
    ws["B7"], ws["C7"], ws["D7"] = "2026-06-15", 4, "PM"
    ws["A8"] = "DAY 2 — ROME"
    ws["A9"] = "Vatican Museums skip the line"
    ws["B9"], ws["C9"], ws["D9"] = "2026-06-17", 4, "AM"
    wb.save(path)
    return path


def build_minimal_itinerary(path: Path) -> Path:
    """No date column and no time column — time-dependent items cannot price."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"], ws["B1"], ws["C1"] = "Experience", "Pax", "Cost"
    ws["A2"], ws["B2"] = "Uffizi Gallery private tour", 4
    ws["A3"], ws["B3"] = "Vatican Museums skip the line", 4
    wb.save(path)
    return path


def build_wide_itinerary(path: Path) -> Path:
    """Adversarial: pax is stated once for the whole trip, not per row."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"] = "BROWN FAMILY — ITALY"
    ws["A3"], ws["B3"] = "Party size:", 4
    for col, header in zip("ABCD", ["Experience", "Date", "Time", "Net Cost"]):
        ws[f"{col}5"] = header
    ws["A6"] = "Uffizi Gallery private tour"
    ws["B6"], ws["C6"] = "2026-06-15", "PM"
    ws["A7"] = "Vatican Museums skip the line"
    ws["B7"], ws["C7"] = "2026-06-17", "AM"
    wb.save(path)
    return path


def build_branded_itinerary(path: Path) -> Path:
    """An itinerary with a logo and conditional formatting.

    Mirrors what a real agency template carries, so we can measure what a
    save() round trip destroys.
    """
    import base64
    import io

    from openpyxl.drawing.image import Image
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import PatternFill

    build_itinerary(path)
    wb = openpyxl.load_workbook(path)
    ws = wb["Itinerary"]

    # A 1x1 red PNG is enough to detect drop-on-save.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    ws.add_image(Image(io.BytesIO(png)), "G1")

    ws.conditional_formatting.add(
        "E8:E20",
        CellIsRule(operator="lessThan", formula=["0"],
                   fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE")),
    )
    wb.save(path)
    return path
