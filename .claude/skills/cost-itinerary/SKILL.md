---
name: cost-itinerary
description: Use when the operator runs /cost or attaches an itinerary to be priced. Prices every line it can, asks about the ones it can't, and produces a costed copy of her file — never inventing a price or a match.
---

# Costing an itinerary

## 1. First pass

```
uv run python -m pricing cost --file "<path to her itinerary>"
```

This needs a costing workbook and at least one mapped region already on file (from
`/profile` and `/map`) — if it says it doesn't know where her workbook is, send her to
`/profile` first.

If it refuses with a message about not being able to tell how many travellers the
itinerary is for, that means this itinerary states the party size once for the whole
trip rather than in a column next to each line (a common layout) — ask her for the party
size and re-run with `--default-pax <number>`:

```
uv run python -m pricing cost --file "<path>" --default-pax 4
```

This is a one-off for this run only, and there is no way to make it permanent — never
suggest saving it, and never tell her `/profile` remembers it. The saved template
describes the *shape* of an itinerary, and the same shape is legitimately reused across
different clients' trips; a party size is data about one specific client's booking. If a
party size were remembered against the shape instead of the trip, a second client's
itinerary that happens to be laid out the same way could silently be priced using the
first client's headcount, with no warning anywhere — exactly the class of silent
mispricing this tool exists to prevent. If she attaches itineraries shaped like this
regularly, that's fine — she'll just be asked for the party size again each time, on
purpose.

## 2. Resolve the lines it's not confident about

A line only prices itself automatically when the tool is certain — the itinerary's
wording matches a catalog entry exactly (after routine cleanup like case and
punctuation), or she's confirmed this exact phrasing once before. Anything less certain
comes back with status `unmatched` and a short list of candidates, and it stops to ask
rather than guess.

This is expected, and it's worth saying so to her plainly the first time it happens:

> A few lines need your eyes because the wording doesn't match your rate sheet exactly
> yet. Once you confirm each one, the tool remembers your exact phrasing — so the same
> itinerary language prices itself automatically next time.

For each `unmatched` line, show her the candidates the result actually returned, in
order — never invent an option that isn't in the result:

> Line 10 says **"Sunset catamaran w/ open bar"**. The closest things in your mapped
> experiences are:
> `1` Catamaran Cruise — PM (beverages incl.)
> `2` None of these — I'll tell you what it should be

One question per line (or, if several unmatched lines clearly share the same answer,
say so and confirm them together — but never assume that without asking).

Collect her answers into a small file keyed by row number, e.g.:

```json
{"10": "GR-CAT-0001"}
```

Then run the command again, adding the resolutions:

```
uv run python -m pricing cost --file "<path>" --resolutions "<path to resolutions json>"
```

Her choices are saved automatically as aliases once this run completes — the same
phrasing will auto-price next time, no need to do anything extra.

## 3. Report any price changes

The result's summary carries a `price_changes` list. If it's non-empty, tell her
plainly — these are informational, the quote already used the new numbers:

> Heads up — while pricing this, I noticed the Uffizi rate is now €310 (it was €285
> when you mapped it). Your quote already reflects €310.

One exception: if a price change shows a rate moving to `0` (or negative), that is
**not** a routine update — it almost always means a placeholder or a cleared cell in her
sheet, not a genuine price drop to free. The tool will never write a `0` into her quote
for it; that line will instead show up as `needs_quote` in step 4, asking her to confirm
the real rate. Report both signals together rather than describing it as "no action
needed."

## 4. Report what still needs a quote

Lines with status `needs_quote` are **not a failure** — the tool is refusing to invent a
number it doesn't actually have. Read the reason back to her from the result:

> One line needs a manual quote: 14 people on the Uffizi tour is above the highest rate
> in your sheet, which stops at 10. You'll need a group rate from the supplier for that
> one.

## 5. Surface every warning, and every skipped row

If the result's `warnings` list has anything in it, pass it on to her verbatim — don't
summarize or drop it:

> One more thing: your itinerary's logo won't carry over into the costed copy — that's
> just how the file format handles images on save.

The result's summary also carries a `skipped_rows` list — every row that had a name but
no readable party size, and so was left out of the quote entirely rather than priced
with a guess. Some of these are genuinely just day headings ("DAY 1 — FLORENCE"); others
might be real experiences whose party size never made it into that cell. The tool cannot
tell the difference, so ask her:

> I skipped these rows because they had no party size — tell me if any of them is a real
> experience I should be pricing: row 8 ("DAY 2 — ROME"), row 14 ("Private cooking
> class").

Never treat a non-empty `skipped_rows` list as routine and move past it silently — a
skipped row is a line that is currently missing from her quote.

## 6. Hand over the file

Tell her the output filename (just the name, not the full path) and read back the
summary: how many lines priced, how many need a quote, how many are still unmatched, and
the total(s) — grouped by currency if there's more than one. Never restate a number you
calculated yourself; use only what's in the result.

## Rules

- Never guess a match to avoid asking. A question costs her ten seconds; a wrong price
  costs her a client.
- Never fill a `needs_quote` line with an estimate.
- If a command's result says a mapped experience is "no longer" where it should be in
  the sheet (the sheet's shape changed), stop and tell her to run `/map` for that region.
  Do not try to work around it or price that line anyway.
