---
name: profile-rate-sheet
description: Use when the operator runs /profile, attaches a costing workbook for the first time, or says her rate sheet has changed shape. Reads the workbook's structure, shows her every plausible header row so she can pick the right one, and gets the pricing model confirmed before any mapping starts.
---

# Profiling a rate sheet

## 1. Locate the workbook

Ask which file is her costing workbook if you don't already know. Then run, from the
project folder:

```
uv run python -m pricing profile --workbook "<path>"
```

This reads every sheet's structure, saves one profile file per sheet, and remembers the
workbook location for every command that follows.

The result never contains any text or number that was actually read from a cell — no
header words, no rates, no names. It's built that way on purpose so it's safe to hand to
whoever supports this tool. It does list one thing that came from her workbook: the
**names of her tabs** (e.g. "Italy", "Greece"). Tell her this plainly:

> Nothing in this file shows your prices or any header text. It does list your sheet
> tab names, though — if a tab name itself is sensitive (say, it has a client's name in
> it), rename the tab before you send this file to anyone.

## 2. Find the real header row — show her every candidate, not just the best guess

The tool proposes a ranked list of rows that could plausibly be the header for each
sheet. It only proposes; it does not decide. **Always show her every candidate it found,
not only the top one** — the true header sometimes ranks last (a category band or title
row can outscore it), and picking only the top guess would hide the right answer from
her.

To let her see the actual words in each candidate row (the profile itself has none),
pull the real content with:

```
uv run python -m pricing rows --sheet "<sheet name>" --from <row> --to <row>
```

Run this once per candidate row (or a small range covering all candidates at once), then
lay out what you found and ask her to confirm:

> On the **Italy** tab, two rows could be the header:
> `1` Row 3: Experience, Min Pax, Max Pax, Net Rate, Unit, PM Supplement
> `2` Row 1: ITALY — NET RATES 2026 (merged across the row — looks like a title, not a
>     header)
>
> Which one is actually your column header row?

One question per sheet. Do this for every sheet before moving on.

## 3. Propose the pricing model, axis by axis

Once the header row is confirmed, use the real column text (from `rows`) together with
the structural hints in the profile — whether a column looks numeric, how many distinct
values it has, whether it looks price-bearing — to name the axes you believe exist.
Ask about each one **separately**, one question per message:

- "The `Unit` column has two values, `per person` and `per group`. Am I right that this
  says whether the rate is charged once or per traveller?"
- "There's a `PM Supplement` column. Is that added per person, or once per booking?"
- "I don't see anything about seasons or blackout dates on this sheet. Are there any I
  should know about, or are rates the same year-round?"

Record her answers — they decide how you'll shape each catalog entry when you map this
region later.

## 4. Profile the itinerary template

Ask her to attach a blank itinerary (or her most recent one). Run:

```
uv run python -m pricing profile-itinerary --file "<path>"
```

This proposes which column holds the experience name, the date, the party size, the
time of day, and — importantly — which empty column is the one that will receive the
price. Read the proposed columns back to her in plain language and confirm each one:

> I think column A is the experience name, column C is the party size, and column E is
> where I should write the price. Does that sound right?

If the command can't find a required column, it will say so directly (it needs at least
an experience-name column and a cost column to work at all) — ask her directly which
column holds each one.

Some itineraries state the party size once for the whole trip instead of in a column
next to each line (look for something like "Party size: 4" near the top). The command
can't find a pax column on a layout like this, and will say so.

There is no way to save a party size here, and that's deliberate: the saved template
describes the *shape* of an itinerary, and it's normal — expected — for the same shape
to be reused across different clients' trips. A party size is data about one specific
client's booking, not about the shape of the sheet, so it can never be remembered
between itineraries. Remembering it would mean a second client's differently-sized trip
could silently be priced using the first client's headcount, with no warning anywhere —
exactly the mistake this tool exists to prevent.

`/cost` will refuse to price this shape of itinerary until she gives you the party size
**for that specific trip**, via `--default-pax` on `cost` itself — see `cost-itinerary/SKILL.md`.
Every itinerary shaped like this gets asked again, every time. That repetition is the
point, not a rough edge.

## 5. Point at the next step

> Next, run `/map Italy` (or whichever region you want to start with). You only need to
> map a region once, and you can stop partway through a sheet — it saves as you go, so
> nothing is lost if you need to come back later.
