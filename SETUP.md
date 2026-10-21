# Setting up your pricing assistant

> **New here? Read `START-HERE.md` first.** It explains what the tool does, what
> order to do things in, and how to check it's working. This document is just the
> one-time install and a reference for each command.

This tool reads your supplier rates once, then fills in the cost column on any client
itinerary automatically — no more hunting through spreadsheets and copying numbers by
hand. You stay in control the whole time: it only ever asks you to confirm what it
found, and it never changes your original files.

## One-time setup

You only need to do this once, on the computer you'll be working from.

### 1. Install the Claude desktop app

If you don't already have it, install the Claude desktop app from Anthropic and sign
in. This is the program you'll be chatting with to run the tool.

### 2. Install a small helper program

The pricing tool needs one small helper program installed alongside Claude to be able
to run. Open your computer's command window and paste in the line below for your
system, then press Enter.

**On a Mac** — open **Terminal** (search for it with Spotlight) and run:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**On Windows** — open **PowerShell** (search for it in the Start menu) and run:

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Either command will print some progress messages and finish on its own. You can close
the window afterward — you won't need to open it again.

### 3. Get the project folder
I have sent you link to download the project folder, called
`itinerary-pricing`. Save it somewhere easy to find — your Desktop or Documents folder
both work well — and make sure it ends up as one whole folder, not scattered loose
files.

## Opening the folder in Claude

Open the Claude desktop app and add `itinerary-pricing` as a project folder (look for
an option like "Open Folder" or "Add Project"). Once it's open, you're ready to start —
everything from here on happens by typing a command starting with `/` into the chat,
the same way you'd send any other message to Claude.

## Run `/doctor` first

Before doing anything else, type:

```
/doctor
```

This checks that everything is set up correctly and reports back in plain language,
one line per check, each marked with a tick or a cross. It checks five things: your
settings, the tool itself, Excel support, your costing workbook, and your saved data
folder.

The very first time you run it, one of those five is expected to show a cross — the
check for your costing workbook, since you haven't pointed it at one yet. That's normal,
not a problem: its own message tells you exactly what to do next ("Run /profile and
point me at it"), which is exactly the next step below. Only treat a cross as something
to worry about if its message doesn't explain what to do, or if it's still there after
you've followed its instructions — in that case, skip ahead to "If something goes wrong"
below.

## `/profile` — teach it your costing workbook

Once `/doctor` looks good, attach your costing workbook (the spreadsheet with all your
supplier rates in it) and type `/profile`. Claude will read through it and tell you, in
plain language, what it found — how many regions, how each one seems to be laid out,
and how it thinks pricing works for each. It will never repeat a rate or a client name
back to you at this stage; it's only checking that it understands the shape of your
sheet, not reading the numbers out loud. Correct anything it got wrong before moving on.

## `/map` — confirm your rates, one region at a time

Type `/map` followed by a region name (or just `/map` to be shown a list of regions to
choose from). Claude will walk through that region's rows a handful at a time,
describing each experience and how it's priced in your own words, and ask you to
confirm, correct, skip, or mark it as not something you sell. Every confirmation is
saved immediately, so if you need to stop partway through, nothing you've already
confirmed is lost. Repeat this for each region you want to be able to price
automatically — you don't have to do them all in one sitting.

## `/cost` — price a client itinerary

Attach a client itinerary and type `/cost`. Claude fills in the cost for every
experience it recognises, working out group size, time of day, and any seasonal or
day-of-week rules along the way. It always produces a brand-new copy of the file,
marked FINAL and dated — `Trip_Sample_FINAL_2026-09-11.xlsx` — so your original itinerary
is never touched or overwritten and you can run this as many times as you like with no
risk. Anything it isn't confident about is left clearly marked instead of guessed at, so
you always know what still needs a second look.

## `/verify` — check its work against a trip you already priced by hand

This is worth doing once, right after you finish mapping a region, before you trust the
tool with a real client quote. Pick two or three trips you've already priced by hand in
the past, attach one, and type `/verify`. Claude re-prices it from scratch using what
you've mapped, and compares its numbers against the costs already sitting in that file.

If the numbers match to the cent, your mapping is right — that's the whole point of the
check, and the strongest confidence you can have before sending a tool-priced quote to a
client. If anything doesn't match, Claude will tell you exactly which line and by how
much, so you can go back and fix the mapping before it matters. Run it again on the
other trips you picked out, and any time you've made a big change to your mappings and
want that same confidence back.

## `/refresh` — check whether any of your rates have changed

Whenever you've updated your costing workbook — new season, new supplier prices — type
`/refresh`. Claude checks every experience you've mapped against the live workbook and
tells you plainly what it found: which prices have moved (informational only — your
next quote already uses the new numbers, nothing to redo), which experiences can no
longer be priced at all because the sheet around them changed shape and need
re-mapping with `/map`, and which experiences are still priceable right now but were
mapped without the extra protection that would catch that kind of change automatically
next time — worth a look when you have a moment, but not urgent. It always keeps those
three kinds of news separate, so you can tell at a glance whether something needs your
attention or not.

## If something goes wrong

Type `/doctor` again. Then copy everything it prints and send it to whoever supports
this tool for you — the more of it you send, the faster they can help, so don't
summarise or trim it down.
