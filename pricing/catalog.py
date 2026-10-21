"""The mapping table.

Every rate is stored as a cell reference plus the value last seen there.
That makes prices self-refreshing, makes price changes detectable, and —
via row fingerprints — makes structural drift loud instead of silent.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

from pricing.money import MoneyParseError, parse_money
from pricing.workbook import CellRef, Workbook

_WHITESPACE = re.compile(r"\s+")


class FingerprintMismatch(Exception):
    def __init__(self, item_id: str, expected_name: str, cell: str, found: str) -> None:
        super().__init__(
            f"'{expected_name}' is no longer at {cell} (found '{found}'). "
            f"The sheet has changed shape — please re-run /map for this region."
        )
        self.item_id = item_id


@dataclass
class PriceChange:
    cell: str
    last_seen: Decimal
    current: Decimal


@dataclass
class CatalogItem:
    """Catalog item with drift detection via dual fingerprints.

    row_fingerprint: Hashes the item's name cell only. Detects if a row is inserted
      at the name cell itself. Empty means unverified.

    structure_fingerprint: Hashes all cells in source_rows EXCEPT rate/modifier cells.
      Detects column insertions, row deletions, and other structural changes while
      allowing legitimate price updates. Empty means unverified.

    Either or both fingerprints can be empty (meaning that verification is skipped);
    empty fingerprints are not an error. Missing both means the item is unprotected
    against structural drift.
    """
    id: str
    name: str
    name_cell: str
    region: str
    currency: str
    unit: str
    pricing: dict
    modifiers: list[dict] = field(default_factory=list)
    source_rows: list[int] = field(default_factory=list)
    row_fingerprint: str = ""
    confirmed_at: str = ""
    min_billable_pax: int | None = None
    structure_fingerprint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CatalogItem":
        return cls(**data)


class Catalog:
    def __init__(self, items: list[CatalogItem] | None = None) -> None:
        self.items: list[CatalogItem] = list(items or [])

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([CatalogItem.from_dict(d) for d in data.get("items", [])])

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "items": [i.to_dict() for i in self.items]}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def upsert(self, item: CatalogItem) -> None:
        for index, existing in enumerate(self.items):
            if existing.id == item.id:
                self.items[index] = item
                return
        self.items.append(item)

    def get(self, item_id: str) -> CatalogItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def by_region(self, region: str) -> list[CatalogItem]:
        return [i for i in self.items if i.region == region]


def fingerprint(text: str) -> str:
    normalised = _WHITESPACE.sub(" ", str(text).strip().lower())
    return "sha1:" + hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:16]


def compute_structure_fingerprint(wb: Workbook, item: CatalogItem) -> str:
    """Hash all cells in source_rows except those referenced by rates/modifiers.

    This fingerprint is stable across legitimate price updates (only rate cells
    change) but sensitive to structural drift (column insertions, row deletions,
    cell moves). Returns empty string if source_rows is empty or not provided.
    """
    if not item.source_rows:
        return ""

    # Collect all rate/modifier cell references (the ones we exclude).
    excluded_cells = set()
    for cell, _ in _rate_cells(item):
        excluded_cells.add(cell.upper())  # Normalize to uppercase for comparison

    # Collect sheet and column info from name_cell to determine the sheet context.
    name_ref = CellRef.parse(item.name_cell)
    sheet_name = name_ref.sheet

    # Read all cells in source_rows, excluding rate/modifier cells.
    all_values = []
    for row_num in item.source_rows:
        row_data = wb.read_row(sheet_name, row_num)
        if row_data:
            for col_idx, cell_value in enumerate(row_data, start=1):
                # Build cell reference for this cell.
                from openpyxl.utils import get_column_letter
                col_letter = get_column_letter(col_idx)
                cell_ref = f"{sheet_name}!{col_letter}{row_num}".upper()

                # Include only if not a rate/modifier cell.
                if cell_ref not in excluded_cells:
                    # Normalize the cell value the same way fingerprint() does.
                    normalised = _WHITESPACE.sub(" ", str(cell_value).strip().lower())
                    if normalised:  # Only include non-empty cells
                        all_values.append(normalised)

    # Hash the concatenated normalized values.
    if not all_values:
        return ""
    combined = "|".join(all_values)
    return "sha1:" + hashlib.sha1(combined.encode("utf-8")).hexdigest()[:16]


def resolve_rates(item: CatalogItem, wb: Workbook) -> tuple[dict[str, Decimal], list[PriceChange]]:
    _verify_fingerprint(item, wb)

    rates: dict[str, Decimal] = {}
    changes: list[PriceChange] = []

    for cell, last_seen in _rate_cells(item):
        raw = wb.read(CellRef.parse(cell))
        try:
            current = parse_money(raw)
        except MoneyParseError:
            continue  # Left unresolved; patterns.evaluate raises NeedsQuote.
        rates[cell] = current
        if last_seen is not None and current != last_seen:
            changes.append(PriceChange(cell, last_seen, current))

    return rates, changes


def _verify_fingerprint(item: CatalogItem, wb: Workbook) -> None:
    # Verify row_fingerprint (name cell).
    if item.row_fingerprint:
        found = wb.read(CellRef.parse(item.name_cell))
        if fingerprint(found or "") != item.row_fingerprint:
            raise FingerprintMismatch(item.id, item.name, item.name_cell, str(found))

    # Verify structure_fingerprint (all non-rate cells in source_rows).
    if item.structure_fingerprint:
        computed = compute_structure_fingerprint(wb, item)
        if computed and computed != item.structure_fingerprint:
            raise FingerprintMismatch(
                item.id,
                item.name,
                f"rows {item.source_rows[0]}-{item.source_rows[-1]}" if item.source_rows else "unknown",
                "structural drift detected"
            )


def _rate_cells(item: CatalogItem) -> list[tuple[str, Decimal | None]]:
    entries: list[tuple[str, Decimal | None]] = []

    pricing = item.pricing
    if pricing.get("pattern") == "flat":
        entries.append((pricing["cell"], _seen(pricing)))
    elif pricing.get("pattern") == "tiered_by_pax":
        for tier in pricing["tiers"]:
            entries.append((tier["cell"], _seen(tier)))

    for mod in item.modifiers:
        if "cell" in mod:
            entries.append((mod["cell"], _seen(mod)))

    return entries


def _seen(node: dict) -> Decimal | None:
    raw = node.get("last_seen")
    return Decimal(str(raw)) if raw is not None else None
