---
name: refresh-rates
description: Use when the operator runs /refresh, asks whether any prices have changed, or says she has updated her costing workbook. Separates informational price changes from items that must be re-mapped before they can price at all.
---

# Refreshing rates

## 1. Sweep the catalog

```
uv run python -m pricing refresh
```

This checks every mapped experience against the live costing workbook.

## 2. Report price changes — these are informational only

The result's `price_changes` list is a set of rates that moved since she mapped them.
Report it as a plain list:

> **2 rates have changed since you mapped them:**
> - Uffizi Gallery private tour: €285 → €310
> - Vatican Museums: €95 → €99

Make clear this needs no action from her: the catalog reads live cells every time it
prices something, so any quote she runs already uses the new numbers. Nothing needs
re-mapping just because a price moved.

**Exception:** if an entry shows a rate that moved to `0` (or negative), do not describe
that as routine. A rate of zero almost always means a placeholder or a cleared cell in
her sheet, not a genuine price drop — flag it to her plainly, and mention that any
itinerary line using that rate will come back asking her to confirm it rather than
pricing at €0.

## 3. Report broken items — these need her to act

The result's `broken_items` list is a **completely different kind of thing**. An item
lands here when the sheet around it has changed shape — rows inserted, deleted, or moved
— badly enough that the tool can no longer trust it's reading the right cell. These
items **cannot be priced at all** until she fixes them:

> **1 item needs re-mapping.** The Uffizi tour is no longer where it was on your Italy
> tab — it looks like rows were inserted or moved. Run `/map Italy` to fix it. Until
> then, any itinerary line that needs that experience won't price.

Never combine this list with the price-change list, and never describe a broken item as
if it were just another price update — it is work she has to do, not something to note
and move on from.

If both lists are empty, tell her plainly that everything checked out and nothing has
changed.

## 4. Report unprotected items — these are a heads-up, not urgent

The result's `unprotected_items` list is a third, separate kind of thing again: items
that were saved without the two fingerprints that let the tool notice if the sheet's
shape changes underneath them later (usually because `/map` computed them without
running the fingerprinting step, or someone deliberately skipped it). They price
normally right now — nothing is broken — but they have no protection if the sheet
changes shape in the future.

> **1 item has no drift protection:** Uffizi Gallery Tour. It's pricing fine, but if
> rows ever get inserted or deleted near it on your Italy tab, I won't be able to warn
> you that it's now reading the wrong cell. Re-run `/map Italy` for it when you have a
> moment to fix that.

This is a lower-priority heads-up, not something she needs to act on immediately the way
a broken item is — but don't fold it into either of the other two lists.

## 5. Suggest a verification

> Once anything above is fixed, run `/verify` on a trip you already priced by hand, to
> confirm everything still lines up.
