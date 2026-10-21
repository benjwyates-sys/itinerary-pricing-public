"""Phase 0: describe the shape of a rate sheet without disclosing its rates.

The output of this module (`to_dict`) is the one artefact the operator can
safely send to a developer. It carries STRUCTURE ONLY -- sheet dimensions,
header row location, merged ranges, formula counts, data-block boundaries,
and per-column metadata (letter, fill rate, distinct count, kind, whether a
column looks price-bearing). It never carries a single character or digit
read from a cell.

This replaces an earlier design that tried to classify header text and cell
values as confidential-or-not and mask what it judged unsafe. That
classifier leaked four times in a row, each time while its own test suite
was green: substring word matching let "age" inside "Beverage" through,
hyphen-adjacency rules meant to protect pax bands ("1-4 Pax") also excused
hyphenated price ranges ("150-300"), tightening currency adjacency still
missed "€45"/"$50"/"1,250 flat"/"99.5"/"85 CHF", and a whole-header context
check unlocked unrelated prices sitting elsewhere in the same header
("Adult 45", "Guest $50"). Classifying content derived from a confidential
document is adversarial and unwinnable by vocabulary tweaks -- there is
always another header shape the vocabulary doesn't cover. So the artefact
now simply never contains cell-derived content: nothing to classify means
nothing to get wrong. Do not reintroduce a content classifier here.

`ColumnProfile.header` and `ColumnProfile.sample_values` still exist as
in-memory dataclass fields, populated the same way they always were, for
the operator's own local use during `/profile` and `/map` -- they never
leave the machine because `to_dict` does not serialize them. `price_bearing`
is retained and still serialized: it is structural metadata (does this
column look like it holds money?), not a copy of the money itself, and a
later task uses it.

One field is a deliberate, documented exception to "no cell-derived
content": the sheet `name` itself IS included in the artefact. A sheet
name is workbook organisation, not cell data -- it is how the profile is
structured and how the operator refers to her own regions (tab names in
this domain are things like "Italy", "Greece", "Japan"), and indexing
sheets as `sheet_0`/`sheet_1` would make the artefact unintelligible for
the remote-support job it exists to do. This is a considered decision,
not an oversight: an operator whose tab name happens to be sensitive
(e.g. it embeds a price, as in "Acme Tours 2026 Net 4500") should rename
the tab, or ask for sheets to be indexed instead, before sharing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl.utils import get_column_letter

from pricing.money import MoneyParseError, parse_money
from pricing.workbook import CellRef, Workbook

MONEY_WORDS = ("rate", "price", "cost", "net", "supplement", "fee",
               "charge", "eur", "usd", "gbp", "$", "€", "£")
COUNT_WORDS = ("pax", "qty", "quantity", "min", "max", "count", "number",
               "days", "nights", "hours", "duration", "year", "age")

MAX_SAMPLES = 12


@dataclass
class ColumnProfile:
    letter: str
    header: str | None
    fill_rate: float
    distinct_count: int
    kind: str
    price_bearing: bool
    # repr=False: this can hold real rates (see module docstring on
    # sample_values no longer being gated by price_bearing). It must never
    # be dumped by a default repr/logging/exception rendering of a profile.
    sample_values: list[str] = field(default_factory=list, repr=False)


@dataclass
class SheetProfile:
    name: str
    max_row: int
    max_column: int
    header_row: int | None
    merged_ranges: list[str]
    formula_cells: int
    data_blocks: list[list[int]]
    columns: list[ColumnProfile]
    header_row_candidates: list[int] = field(default_factory=list)


def profile_workbook(wb: Workbook) -> list[SheetProfile]:
    return [profile_sheet(wb, name) for name in wb.sheet_names()]


def profile_sheet(wb: Workbook, sheet: str) -> SheetProfile:
    max_row, max_col = wb.dimensions(sheet)
    candidates = find_header_candidates(wb, sheet, max_row, max_col)
    header_row = candidates[0] if candidates else None
    first_data = (header_row + 1) if header_row else 1

    columns = [
        _profile_column(wb, sheet, col, header_row, first_data, max_row)
        for col in range(1, max_col + 1)
    ]

    return SheetProfile(
        name=sheet,
        max_row=max_row,
        max_column=max_col,
        header_row=header_row,
        merged_ranges=wb.merged_ranges(sheet),
        formula_cells=_count_formulas(wb, sheet, max_row, max_col),
        data_blocks=_data_blocks(wb, sheet, first_data, max_row),
        columns=columns,
        header_row_candidates=candidates,
    )


def _row_has_numeric(values: list[object]) -> bool:
    return any(isinstance(v, (int, float)) for v in values)


def _row_text_count(values: list[object]) -> int:
    return len([v for v in values if isinstance(v, str) and v.strip()])


def _leads_to_data_through_more_headers(wb: Workbook, sheet: str, start_row: int,
                                        max_row: int, limit: int = 20) -> bool:
    """Walk down from `start_row`, treating each further text-heavy,
    numberless row as another header layer, until numeric data is found.

    This is the non-merge signal for a stacked category band: a band does
    not sit directly above data, it sits above ANOTHER header-like row
    (which may itself sit above yet another, before data finally appears).
    A row that merely has numbers directly beneath it is not a band --
    that is the ordinary, single-header case and is scored separately.
    """
    row = start_row
    steps = 0
    while row <= max_row and steps < limit:
        values = wb.read_row(sheet, row)
        if _row_has_numeric(values):
            return True
        if _row_text_count(values) < 3:
            return False
        row += 1
        steps += 1
    return False


def find_header_candidates(wb: Workbook, sheet: str, max_row: int, max_col: int) -> list[int]:
    """Every row that could plausibly be the header, best first.

    Category bands above the real header ('Group Size Pricing') look like
    headers too -- whether or not the cells are merged. Rather than pick
    one and be silently wrong, we return all of them and let the operator
    confirm.
    """
    scored: list[tuple[int, int]] = []
    merged_rows: set[int] = set()
    for rng in wb.merged_ranges(sheet):
        start = str(rng).split(":")[0]
        match = re.match(r"^[A-Za-z]+(\d+)$", start)
        if match:
            merged_rows.add(int(match.group(1)))

    for row in range(1, min(max_row, 20) + 1):
        values = wb.read_row(sheet, row)
        texts = [v for v in values if isinstance(v, str) and v.strip()]
        if len(texts) < 3 or row >= max_row:
            continue
        score = len(texts)
        if row in merged_rows:
            score -= 2          # a merged band is more likely a category label
        below = wb.read_row(sheet, row + 1)
        if _row_has_numeric(below):
            score += 2          # real headers sit directly above data
        elif _leads_to_data_through_more_headers(wb, sheet, row + 1, max_row):
            # The row beneath is itself text-heavy and numberless, and
            # data only appears further down, through one or more such
            # rows -- this row is stacked above the real header, not
            # sitting on top of the data itself. No merge required.
            score -= 3
        scored.append((score, row))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [row for _, row in scored]


def find_header_row(wb: Workbook, sheet: str, max_row: int, max_col: int) -> int | None:
    """The single best header-row guess. Prefer find_header_candidates when
    the caller can act on more than one plausible row."""
    candidates = find_header_candidates(wb, sheet, max_row, max_col)
    return candidates[0] if candidates else None


def _profile_column(wb: Workbook, sheet: str, col: int, header_row: int | None,
                    first_data: int, max_row: int) -> ColumnProfile:
    letter = get_column_letter(col)
    header = None
    if header_row:
        raw = wb.read(CellRef(sheet, letter, header_row))
        header = str(raw).strip() if raw is not None else None

    values = [
        wb.read(CellRef(sheet, letter, row))
        for row in range(first_data, max_row + 1)
    ]
    present = [v for v in values if v is not None and str(v).strip() != ""]
    fill_rate = round(len(present) / len(values), 3) if values else 0.0
    distinct = {str(v) for v in present}
    kind = _classify(present)
    price = _is_price_bearing(header, kind, present)

    # sample_values is in-memory-only (see module docstring); the serialized
    # form never carries it, so there is no confidentiality reason to gate
    # it on price_bearing any more -- any column with few enough distinct
    # values gets its samples populated for local use.
    samples: list[str] = []
    if 0 < len(distinct) <= MAX_SAMPLES:
        samples = sorted(distinct)

    return ColumnProfile(
        letter=letter,
        header=header,
        fill_rate=fill_rate,
        distinct_count=len(distinct),
        kind=kind,
        price_bearing=price,
        sample_values=samples,
    )


def _classify(values: list[object]) -> str:
    if not values:
        return "empty"
    kinds = set()
    for value in values:
        if isinstance(value, (date, datetime)):
            kinds.add("date")
        elif isinstance(value, (int, float)):
            kinds.add("numeric")
        else:
            try:
                parse_money(value)
                kinds.add("numeric")
            except MoneyParseError:
                kinds.add("text")
    if len(kinds) == 1:
        return kinds.pop()
    return "mixed"


def _tokenize_header(header: str | None) -> list[str]:
    """Split header into tokens on non-alphanumeric characters."""
    if not header:
        return []
    # Replace non-alphanumeric with spaces and split
    normalized = re.sub(r'[^a-z0-9]+', ' ', header.lower())
    return [token for token in normalized.split() if token]


def _has_money_word_substring(header: str | None) -> bool:
    """Check if header contains any money word as a substring (loose matching)."""
    lowered = (header or "").lower()
    return any(word in lowered for word in MONEY_WORDS)


def _has_count_word_token(header: str | None) -> bool:
    """Check if header contains any count word as a complete token."""
    tokens = _tokenize_header(header)
    return any(word in tokens for word in COUNT_WORDS)


def _are_plausible_counts(values: list[object]) -> bool:
    """Check if all non-empty values are non-negative integers 0-999."""
    for value in values:
        if value is None:
            continue
        str_val = str(value).strip()
        if not str_val:
            continue
        # Try to parse as integer
        try:
            num = int(str_val)
            if num < 0 or num > 999:
                return False
        except ValueError:
            # Non-integer value
            return False
    return True


def _looks_like_a_band(header: str) -> bool:
    """'1-4 Pax', '5-10 Pax', '11+ Pax': a numeric range in the header names
    a group-size *band*, not a count. Its column holds the price for that
    band, so money words must win over count words for these headers."""
    return bool(re.search(r"\d\s*[-–+]\s*\d|\d\s*\+", header))


def _is_price_bearing(header: str | None, kind: str, values: list[object]) -> bool:
    lowered = (header or "").lower()

    # Money words (substring match): always price-bearing
    if _has_money_word_substring(header):
        return True

    # A pax *band* ('1-4 Pax', '5-10 Pax') is a price column whose header
    # happens to name a count. A range in the header means money.
    if _looks_like_a_band(lowered) and kind in ("numeric", "mixed"):
        return True

    # Count words (token match): only non-price if values are plausible counts
    if _has_count_word_token(header):
        return not _are_plausible_counts(values)

    # Unlabelled or ambiguous numeric data is assumed to be money.
    return kind in ("numeric", "mixed") and bool(values)


def _count_formulas(wb: Workbook, sheet: str, max_row: int, max_col: int) -> int:
    total = 0
    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            if wb.is_formula(CellRef(sheet, get_column_letter(col), row)):
                total += 1
    return total


def _data_blocks(wb: Workbook, sheet: str, first_data: int, max_row: int) -> list[list[int]]:
    """Contiguous runs of rows whose first column (A) is populated.

    Anchors on column A, so sheets whose first column is not the row-identity
    column may produce empty or misleading block lists.
    """
    blocks: list[list[int]] = []
    start: int | None = None
    for row in range(first_data, max_row + 1):
        value = wb.read(CellRef(sheet, "A", row))
        populated = value is not None and str(value).strip() != ""
        if populated and start is None:
            start = row
        elif not populated and start is not None:
            blocks.append([start, row - 1])
            start = None
    if start is not None:
        blocks.append([start, max_row])
    return blocks


def _column_to_dict(column: ColumnProfile) -> dict:
    """Structure-only view of a column: no header text, no cell values."""
    return {
        "letter": column.letter,
        "fill_rate": column.fill_rate,
        "distinct_count": column.distinct_count,
        "kind": column.kind,
        "price_bearing": column.price_bearing,
    }


def _sheet_to_dict(sheet: SheetProfile) -> dict:
    """Structure-only view of a sheet: no cell-derived content anywhere."""
    return {
        "name": sheet.name,
        "max_row": sheet.max_row,
        "max_column": sheet.max_column,
        "header_row": sheet.header_row,
        "header_row_candidates": sheet.header_row_candidates,
        "merged_ranges": sheet.merged_ranges,
        "formula_cells": sheet.formula_cells,
        "data_blocks": sheet.data_blocks,
        "columns": [_column_to_dict(c) for c in sheet.columns],
    }


def to_dict(profiles: list[SheetProfile]) -> dict:
    """Serialize to the shareable artefact: structure only, no cell content.

    Nothing derived from a cell's text or value -- not a header, not a
    sample, not a masked fragment of either -- appears anywhere in this
    output. See the module docstring for why.
    """
    return {"sheets": [_sheet_to_dict(p) for p in profiles]}
