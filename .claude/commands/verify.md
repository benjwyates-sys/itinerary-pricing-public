---
description: Check my pricing against a trip I already priced by hand
---

Run, on the itinerary named in $ARGUMENTS (ask for it if not given):

```
uv run python -m pricing verify --file "<path>"
```

Report the result plainly, using only the `diffs` and `summary` the command returned —
never a number you calculated yourself.

Every line with status `match` is the good outcome — say so clearly: "All 12 lines
match to the cent." For a line with status `mismatch`, show the row, the experience
name, what she had (`expected`), what the tool computed (`computed`), and the
difference (`delta`).

Before you say anything about *why* a mismatch happened, check that line's
`match_confidence`:

- `auto_accept` — the match itself is certain (identical name, or a phrasing she's
  confirmed before). A mismatch here means the **rate** is wrong: tell her a mismatch
  usually means that experience's mapped rate has drifted or was mapped incorrectly, and
  offer to run `/map` for its region.
- `top_guess` — the tool could not confirm which catalog entry this line even refers to,
  and picked its best guess just so it could show her a number. **Never present this as
  a wrong price.** Say the match itself is unconfirmed first: "I'm not certain 'Sunset
  catamaran w/ open bar' matches 'Catamaran Cruise — PM' — the totals don't agree, but
  that could mean it's the wrong match, not a wrong rate. Want to run `/cost` so you can
  confirm which experience this actually is?"
- `none` — nothing in her mapped experiences was even a candidate for this line; it
  wasn't priced at all. Tell her the line needs mapping, not that its price is wrong.

Lines with status `no_expected` had nothing in the cost column to compare against —
that's not a mismatch, just nothing to check. Lines with status `not_priced` couldn't be
priced this run at all — say so, but the tool's output carries no `reason` field for
this case, so never invent one; just report that it wasn't priced.
