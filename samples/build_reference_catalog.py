"""Build a reference catalog for the Dubrovnik sample, skipping /map.

Run:  uv run python samples/build_reference_catalog.py

Use this ONLY to jump straight to /cost and /verify. Doing /map by hand is
the more valuable test, because that is the step your operator actually
performs. This also doubles as a worked example of correct catalog entries:
note that every rate is a CELL REFERENCE plus the value last seen there,
never a copied number, and that both fingerprints are computed from the
live workbook rather than left blank.
"""

import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from pricing.catalog import Catalog, CatalogItem, fingerprint, compute_structure_fingerprint
from pricing.workbook import Workbook

BOOK = Path("samples/Dubrovnik_Costing_2026.xlsx")
wb = Workbook(BOOK)

def item(iid, name, name_cell, rows, unit, pricing, modifiers=None, min_bill=None):
    it = CatalogItem(
        id=iid, name=name, name_cell=name_cell, region="Dubrovnik", currency="EUR",
        unit=unit, pricing=pricing, modifiers=modifiers or [], source_rows=rows,
        row_fingerprint=fingerprint(name), confirmed_at="2026-09-11",
        min_billable_pax=min_bill,
    )
    it.structure_fingerprint = compute_structure_fingerprint(wb, it)
    return it

items = [
    item("HR-DBV-0001", "Old Town Walking Tour — Private Guide", "Dubrovnik!A7", [7, 8],
         "per_group", {"pattern": "tiered_by_pax", "tiers": [
             {"max_pax": 6, "cell": "Dubrovnik!D7", "last_seen": "180"},
             {"max_pax": 15, "cell": "Dubrovnik!D8", "last_seen": "260"}]}),
    item("HR-DBV-0002", "Elafiti Islands Full-Day Cruise", "Dubrovnik!A14", [14, 15],
         "per_person", {"pattern": "tiered_by_pax", "tiers": [
             {"max_pax": 8, "cell": "Dubrovnik!D14", "last_seen": "95"},
             {"max_pax": 20, "cell": "Dubrovnik!D15", "last_seen": "82"}]}),
    item("HR-DBV-0003", "Sea Kayaking — Old Town Walls", "Dubrovnik!A16", [16],
         "per_person", {"pattern": "flat", "cell": "Dubrovnik!D16", "last_seen": "48"},
         [{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
           "cell": "Dubrovnik!F16", "last_seen": "12"}]),
    item("HR-DBV-0004", "Konavle Valley Wine Tasting — Half Day", "Dubrovnik!A17", [17],
         "per_person", {"pattern": "flat", "cell": "Dubrovnik!D17", "last_seen": "78"},
         [{"type": "seasonal", "from": "2026-06-15", "to": "2026-09-15",
           "op": "add_per_unit", "cell": "Dubrovnik!G17", "last_seen": "14"}]),
    item("HR-DBV-0005", "Cooking Class — Gruž Market & Lunch", "Dubrovnik!A18", [18],
         "per_person", {"pattern": "flat", "cell": "Dubrovnik!D18", "last_seen": "110"},
         None, 4),
    item("HR-DBV-0006", "Cable Car & Fort Imperial Entry", "Dubrovnik!A11", [11],
         "per_person", {"pattern": "flat", "cell": "Dubrovnik!D11", "last_seen": "27"}),
    item("HR-DBV-0007", "Private Transfer — Dubrovnik Airport (DBV) to Old Town",
         "Dubrovnik!A22", [22, 23], "per_group",
         {"pattern": "tiered_by_pax", "tiers": [
             {"max_pax": 3, "cell": "Dubrovnik!D22", "last_seen": "42"},
             {"max_pax": 8, "cell": "Dubrovnik!D23", "last_seen": "68"}]}),
]

cat = Catalog()
for i in items:
    cat.upsert(i)

flat = lambda c, v: {"pattern": "flat", "cell": c, "last_seen": v}
for args in [
    ("HR-DBV-0008", "Old Town Walking Tour — Small Group", "Dubrovnik!A9", [9], "per_person", flat("Dubrovnik!D9","45")),
    ("HR-DBV-0009", "Game of Thrones Walking Tour", "Dubrovnik!A10", [10], "per_person", flat("Dubrovnik!D10","38")),
    ("HR-DBV-0010", "Trsteno Arboretum Entry", "Dubrovnik!A12", [12], "per_person", flat("Dubrovnik!D12","12")),
    ("HR-DBV-0011", "Ston Oysters & Walls Day Trip", "Dubrovnik!A19", [19], "per_person", flat("Dubrovnik!D19","85")),
    ("HR-DBV-0012", "Bespoke Photography Session", "Dubrovnik!A21", [21], "per_person", flat("Dubrovnik!D21", None)),
]:
    cat.upsert(item(*args))

cat.upsert(item("HR-DBV-0013", "Private Yacht Charter — Full Day", "Dubrovnik!A20", [20],
                "per_group", flat("Dubrovnik!D20","1850"),
                [{"type": "blackout", "dates": ["2026-08-15"]}]))
cat.upsert(item("HR-DBV-0014", "Private Transfer — Old Town to Dubrovnik Airport (DBV)",
                "Dubrovnik!A24", [24, 25], "per_group",
                {"pattern": "tiered_by_pax", "tiers": [
                    {"max_pax": 3, "cell": "Dubrovnik!D24", "last_seen": "42"},
                    {"max_pax": 8, "cell": "Dubrovnik!D25", "last_seen": "68"}]}))
cat.save(Path("data/catalog.json"))
print(f"catalog now {len(cat.items)} items")

out = Path("data/catalog.json")
cat.save(out)
print(f"built reference catalog: {len(cat.items)} items -> {out}")
print("Also write data/config.json pointing at samples/Dubrovnik_Costing_2026.xlsx,")
print("or just run:  uv run python -m pricing profile --workbook samples/Dubrovnik_Costing_2026.xlsx")
