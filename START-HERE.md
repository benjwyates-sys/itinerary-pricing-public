# Start here

## What this is

You've already done the hard part: someone turned your suppliers' PDFs into a costing
workbook. This tool learns that workbook once, and from then on it fills in the cost
column on client itineraries for you.

You teach it your rates a region at a time, confirming what it's understood as you go.
After that, you attach an itinerary and get back a copy with the costs filled in.

It asks rather than guesses. Every time it isn't certain, it stops and asks you, and
remembers your answer so it doesn't ask again.

## Read this before your first session

**This has never been used on your actual spreadsheets.** It's been tested extensively,
but only against made-up practice files, because your real rates couldn't leave your
computer while it was being built.

So the first session isn't about pricing a client. It's about finding out whether the
tool understands *your* files. That's a genuinely different job, and it's the one that
matters — everything after it is easy.

**Please don't send a client a quote from this tool until you've done the check in
"How to tell if it's working" below.** That check takes about fifteen minutes and it's
the only real proof that exists.

Set aside an hour or so. Plan to get through one region, not all of them.

## The order to do things in

You'll need help with the first two steps — they're a one-time install, and it's much
easier on a screen share than alone.

| | Step | What it's for | How long |
|---|---|---|---|
| 1 | Install | One-time setup. See `SETUP.md`. | 20 min, with help |
| 2 | `/doctor` | Confirms everything's working | 1 min |
| 3 | `/profile` | It reads your costing workbook and works out how it's laid out | 10 min |
| 4 | `/map` | You confirm your rates, one region at a time | 20–40 min per region |
| 5 | `/verify` | **The real test.** Checks it against trips you priced by hand | 15 min |
| 6 | `/cost` | Price a client itinerary | 2 min per trip |

Steps 3 and 4 happen once per workbook. Step 5 is how you decide whether to trust it.
Step 6 is the everyday use — the thing you're actually here for.

A note on step 2: the very first time you run `/doctor`, one of its five checks will
show a cross, because you haven't shown it your costing workbook yet. That's expected.
Its message tells you what to do next.

## What it will ask you, and how to answer

Most of your time is in `/map`, and it's a conversation. Here's the shape of it.

**It describes an experience back to you in your own words:**

> **Rows 14–15 — Uffizi Gallery, Private Guided Tour**
> I read this as **per person, tiered by group size**: €285 for 1–4, €240 for 5–10.
> PM departures add €40 per person.

You say whether that's right. If it isn't, say what's wrong in plain language —
"the €40 is per booking, not per person" — and it'll correct itself.

**Then it groups the rest:** once you've confirmed one shape, it finds every other row
that looks the same and shows them together, so a ninety-row sheet is usually about
eight decisions rather than ninety. Skim the group; if one of them is different, say so.

**Answer honestly, including "I don't know."** If a row is something you'd have to check
with the supplier, mark it as skip and move on. A skipped row is safe — it just means
the tool will ask you about it later instead of guessing. Confirming something you're
unsure about is the one thing that can lead to a wrong price.

**You can stop any time.** Every confirmation is saved the moment you give it. Close the
laptop mid-region and pick up exactly where you left off.

## How to tell if it's working

This is the part that matters. Don't skip it.

Find **two or three trips you've already priced by hand** — real ones, already sent to
clients, ideally in the region you just mapped, and ideally not all the same shape (one
simple, one with a bigger group or an odd date if you have it).

Attach one and type `/verify`. It re-prices the trip from scratch using what you mapped,
then compares its numbers against the ones already in the file.

**If every line matches to the cent** — that's it. That's the proof. The mapping is
right and you can start using `/cost` for real work in that region.

**If a line doesn't match**, it tells you exactly which experience and by how much. Three
things it's usually telling you:

- *It's off by a supplement or a percentage* — the pricing rule got confirmed slightly
  wrong during `/map`. Re-run `/map` for that region and correct that experience.
- *It picked a different experience than you did* — two things in your sheet have similar
  names. Tell it which one is right; it'll remember.
- *It's right and your old quote was wrong.* This does happen. Check before assuming the
  tool is at fault — catching an old transcription slip is a point in its favour.

**If it can't price a line at all** and says it needs a manual quote, that isn't a
failure. That's the tool refusing to invent a number, which is exactly what you want it
to do. Price that line by hand as usual.

Run `/verify` again on your other trips. When they all come back clean, you're done
evaluating and the tool is yours to use.

## What to send back

Whether it goes well or badly, these are worth passing on:

- **Anything it got confidently wrong.** A wrong answer it was *sure* about is far more
  important than a question it asked. Say which experience and what it should have been.
- **Any question that felt nonsensical**, or that you couldn't answer from looking at
  your own sheet.
- **Anything it skipped** that was actually a real experience. It reports skipped rows at
  the end of a costing run — glance at that list.
- **Whatever `/doctor` prints**, if something breaks. Send all of it, not a summary.

You can safely send the file `/profile` creates. It describes the *shape* of your
workbook — how many columns, where the data starts — and deliberately contains none of
your rates and no client names. The one thing it does include is your tab names, so if a
tab is named something you'd rather not share, rename it first.

## Once it's working

Your everyday routine is one command:

- **`/cost`** — attach an itinerary, get a costed copy back. Your original is never
  touched; it always writes a new file marked FINAL and dated, e.g.
  `Trip_Sample_Dubrovnik_FINAL_2026-09-11.xlsx`.
- **`/refresh`** — run it after you update your workbook. It tells you which prices moved
  (nothing to do — your next quote already uses the new numbers) and which experiences
  need re-mapping because the sheet changed shape around them.
- **`/map`** — when you want to add a new region, or fix one.
- **`/verify`** — worth re-running after any big change to your mappings, to get that
  same confidence back.

## Things it will never do

Worth knowing, so you can relax about the rest:

- **It never changes your files.** Not your costing workbook, not your itineraries. It
  always writes a new copy with a date in the name. A bad run costs you nothing.
- **It never invents a price.** If it can't work something out, it says so in the cost
  cell in plain words. It will never quietly leave a blank that looks like "free", and
  it will never guess.
- **It never quietly matches the wrong experience.** It only fills in a price
  automatically when the name matches exactly, or when you've confirmed that exact
  wording before. Everything else it asks about.
- **Your rates never leave your computer** unless you personally send something.

## If something goes wrong

Type `/doctor`, copy everything it prints, and send the lot to whoever supports this for
you. Don't trim it — the parts that look like noise are usually the useful parts.
