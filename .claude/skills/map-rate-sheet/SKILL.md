---
name: map-rate-sheet
description: Use when the operator runs /map, names a region to map, or asks to review or fix existing mappings. Walks a sheet's rows, proposes a catalog entry for each experience, and saves only what she confirms — one save per confirmation, never batched.
---

# Mapping a region sheet

## 1. Read the rows

You need to know where this region's data starts and stops. If you profiled the
workbook already, you have the header row and data-block boundaries; otherwise ask, or
re-run `/profile` first. Then read the actual rows:

```
uv run python -m pricing rows --sheet "<region>" --from <first> --to <last>
```

Work in blocks of about 15 rows at a time so you never hold more than you can reason
about.

## 2. Propose one entry, and get the shape confirmed

Present the first row or group of rows in her language, not as raw data:

> **Rows 4–5 — Uffizi Gallery, Private Guided Tour**
> I read this as **per person, tiered by group size**: €285 for 1–4 people, €240 for
> 5–10. PM departures add €40 per person.
>
> `1` Correct  ·  `2` Not quite  ·  `3` Skip for now  ·  `4` Not a sellable item

## 3. Batch everything that matches that shape

Once she confirms a shape, scan the remaining rows for the same structure and present
them **as a group** rather than one at a time:

> Rows 20–34 all follow that same structure. Here they are — tell me if any are
> different.

A 90-row sheet should cost her something like 8 decisions, not 90.

## 4. Save after every confirmation — never batch saves

For each row (or group) she confirms, write one item to a temporary JSON file and save
it **immediately**, before moving to the next one:

```
uv run python -m pricing catalog-add --file "<path to item json>"
```

Do this right after each confirmation, never in a batch at the end of the sheet. If she
stops mid-sheet, everything confirmed so far is already saved.

`catalog-add` checks every cell reference in the item before writing anything. If one is
malformed it refuses with a plain message naming the field — fix it and try again; it
never half-saves a broken entry.

`catalog-add` also refuses to save an item with no `row_fingerprint` or
`structure_fingerprint` computed — compute both first (step 5, below) before calling
`catalog-add` for real. This is not optional cleanup; skipping it leaves the item
silently unprotected against the sheet changing shape underneath it later. If you have a
genuine reason to save one without them anyway, pass `--unprotected` — but that should be
a deliberate, rare exception, never a reflex to make the refusal go away.

`catalog-add` also refuses if `id` already exists in the catalog with *different*
content — saving under a reused id would silently overwrite a previously confirmed,
fingerprinted entry, and since you choose ids yourself across sessions, a collision is a
real risk, not a theoretical one. Re-saving an item that is identical to what's already
there always succeeds (nothing changed, nothing to warn about). Only pass `--replace`
when you are deliberately re-mapping an item she has already confirmed — never as a
reflex to make a refusal go away; if the refusal surprises you, stop and check whether
you actually meant to reuse that id before overwriting it.

### The item's shape

Each item is a JSON object with these fields:

| Field | What it is |
|---|---|
| `id` | You choose it — region prefix plus a number works well, e.g. `IT-FLR-0001`. Must be unique — reusing one on purpose requires `--replace` (see below). |
| `name` | The experience name, exactly as the `rows` command showed it. |
| `name_cell` | The cell holding that name, e.g. `"Italy!A4"`. |
| `region` | The sheet/tab name, e.g. `"Italy"`. |
| `currency` | e.g. `"EUR"`. |
| `unit` | `"per_person"` or `"per_group"`. |
| `pricing` | See below. |
| `modifiers` | A list — can be empty. See below. |
| `source_rows` | Every row number this entry was built from, e.g. `[4, 5]` for a two-tier entry. |
| `row_fingerprint` | See step 5 — lets the tool notice if this row moves. |
| `structure_fingerprint` | See step 5 — lets the tool notice if the row's shape changes. |
| `confirmed_at` | Today's date, `"YYYY-MM-DD"`. |
| `min_billable_pax` | Only when there's a minimum group charge, e.g. `2` to always bill at least 2 people even for a solo traveller. Omit otherwise. |

`pricing` is one of two shapes:

- A single rate: `{"pattern": "flat", "cell": "Italy!D6", "last_seen": 95}`
- A price that depends on party size:
  `{"pattern": "tiered_by_pax", "tiers": [{"max_pax": 4, "cell": "Italy!D4", "last_seen": 285}, {"max_pax": 10, "cell": "Italy!D5", "last_seen": 240}]}`
  (list every tier from smallest to largest group size)

Each entry in `modifiers` has a `type` and, except for `blackout`, an `op` and either a
`cell` (a live rate, tracked the same way as the base price) or a fixed `factor`:

- `{"type": "day_part", "when": ["PM"], "op": "add_per_unit", "cell": "Italy!F4", "last_seen": 40}`
  — adds a per-person amount when the itinerary line is AM or PM.
- `{"type": "day_of_week", "when": ["SAT", "SUN"], "op": "add_per_booking", "cell": "...", "last_seen": ...}`
  — adds a flat amount on certain days.
- `{"type": "seasonal", "from": "2026-05-01", "to": "2026-09-30", "op": "multiply", "factor": 1.15}`
  — scales the price during a date range.
- `{"type": "blackout", "dates": ["2026-12-25"]}`
  — no `op`, no `cell`: booking on one of these dates means the tool refuses to price
    the line and asks for a manual quote instead of guessing.

`last_seen` on a rate cell is just what the sheet showed when she confirmed it — it's how
`/refresh` later notices the rate has moved.

## 5. Compute the two fingerprints before saving

Do this BEFORE running `catalog-add` for real (step 4 showed the general save command,
but the actual save always happens after this step) — every item must carry both
fingerprints, so the tool can tell a harmless price update apart from someone inserting
or deleting rows above this one:

- `row_fingerprint` — a hash of the name cell's exact text.
- `structure_fingerprint` — a hash of everything else in the item's rows (not the rate
  cells themselves, since those are expected to change).

Write the item file first with `row_fingerprint` and `structure_fingerprint` left out (or
empty strings), then fill them in with:

```
uv run python -c "
import json, sys
from pathlib import Path
from pricing.catalog import fingerprint, compute_structure_fingerprint, CatalogItem
from pricing.workbook import Workbook, CellRef

item_path, workbook_path = Path(sys.argv[1]), Path(sys.argv[2])
data = json.loads(item_path.read_text())
item = CatalogItem.from_dict(data)
wb = Workbook(workbook_path)
try:
    data['row_fingerprint'] = fingerprint(wb.read(CellRef.parse(item.name_cell)) or '')
    item.row_fingerprint = data['row_fingerprint']
    data['structure_fingerprint'] = compute_structure_fingerprint(wb, item)
finally:
    wb.close()
item_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
" "<path to item json>" "<path to her costing workbook>"
```

Then run `catalog-add` on that same file. Without both fingerprints, `catalog-add`
refuses to save the item at all (see step 4) — if someone edits the sheet later, an
unprotected entry gives no warning that it no longer points at what she thinks it does,
so this step is not optional. Always compute both before saving.

## 6. Close the loop

Report how many entries were saved and how many rows were skipped or marked not
sellable, then:

> `/map <next region>` when you're ready, or `/cost` to price an itinerary using what
> you've mapped so far.
