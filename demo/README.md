# Costing — demo web app

A statically-hosted demo of the itinerary pricing engine, built from
[`docs/demo-app-handoff.md`](../docs/demo-app-handoff.md).

No backend, no accounts, no rate sheets. A visitor picks one of three sample
trips, watches it price itself, confirms anything ambiguous, and downloads a
costed copy. Everything runs in the browser; state lives in one `localStorage`
key so **Reset demo** is a single removal.

The trip is shown as a **day-by-day itinerary** — hotel, transfers,
experiences and free time in the order the day happens — rather than as a list
of priced rows. A consultant works in the same view the client receives.

Picking a trip opens it **unpriced first**: the same days, the same hotels, the
same free time, in Shannon's own wording, with the cost column empty. Costing
it is the next click. The two screens share one layout deliberately — the only
thing that changes between them is the money, which is the whole claim.

## Running it

```bash
pnpm --dir demo install
pnpm --dir demo dev
```

```bash
pnpm --dir demo test
```

```bash
pnpm --dir demo build
```

The build is plain static files in `demo/dist/` — no server, no environment
variables, nothing to configure at runtime.

## Deploying to Vercel

The app lives in `demo/` inside a Python repository, so Vercel needs one
setting and then everything else is standard:

> **Project Settings → General → Root Directory: `demo`**

With that set, `demo/vercel.json` supplies the rest — framework `vite`,
`pnpm install --frozen-lockfile`, `pnpm build`, output `dist`, and
immutable caching on the content-hashed files under `/assets`. Vercel picks
up pnpm from `demo/pnpm-lock.yaml` and Node 20+ from `engines`.

```bash
cd demo && vercel --prod
```

Two things worth knowing before changing that config:

- **There is no catch-all rewrite, on purpose.** `vite.config.ts` sets
  `base: "./"` so the same build can also be published as an Artifact, which
  means assets are referenced relatively. A rewrite serving `index.html` at
  a deep path would make `./assets/…` resolve against that path and 404. The
  app keeps all its state in memory and never changes the URL, so it needs no
  rewrite — a stray path should 404 honestly.
- **`pnpm.onlyBuiltDependencies`** in `demo/package.json` is required, not
  cosmetic. pnpm 10 blocks dependency build scripts by default, and esbuild
  needs its postinstall to fetch a platform binary or the build fails.

The demo is public by design — invented rates, no accounts, no data. If it
ever needs to sit behind a password, Vercel's Deployment Protection does it
without touching the code.

## How it is laid out

| Path | What it is |
|---|---|
| `src/engine/` | Ports of the Python, plus the annotation parser. No React, no DOM, no storage. |
| `src/itinerary/` | Arranging a costed trip into days, and writing the costed copy. |
| `src/data/` | The sample catalog (14 cities, 186 experiences) and three trips. |
| `src/store/` | All demo state, in one namespaced `localStorage` key. |
| `src/screens/` | The seven screens. |
| `src/ui/` | Design tokens from the mockups, icons, money formatting. |
| `src/template/` | The blank .xlsx a consultant downloads, and the zip writer under it. |
| `src/shared/` | Date formatting, used by both the engine and the screens. |

`src/itinerary/` is presentation structure, not pricing: it places what the
engine already returned and never computes or alters a price.

## What is a port, and what is not

`src/engine/patterns.ts` is an exact port of `pricing/patterns.py`. Every case
in `tests/test_patterns.py` is ported to `src/engine/patterns.test.ts` with its
hand-verified totals intact. The only structural change is the one the handoff
calls for: rates are literal `amount` strings rather than cell references into
a live workbook, so the `rates` map the Python signature takes has no
counterpart here.

`src/engine/match.ts` ports the *decision* exactly — `normalize()`, the plural
allowlist, the marker punctuation, the alias store, and the ambiguity guard.
It does not reproduce `difflib.SequenceMatcher`; its `score` is a bigram-Dice
blend instead. Nothing branches on that number, so the two only need to agree
on ordering.

### Notes a consultant writes into a line

`src/engine/annotations.ts` reads notes written into an itinerary's wording —
`Game of Thrones Walking Tour (only 4 people)`, `(15% discount)`. It is
deliberately mean, because §9 is a list of five silent mispricings and every
one came from reading free text generously:

- It recognises **a party size or a percentage, and nothing else**. Every
  pattern is anchored end to end, so a number inside a sentence is not a party
  size — `(2 adults + 1 child)` is refused, which is the §9 bug by name.
- If **any** note on a line is not recognised, **nothing** on that line is
  applied and nothing is stripped. Half-understanding a line is worse than not
  understanding it. The unrecognised note stays in the wording, which stops the
  line matching, which sends it to a person by the route that already exists.
- A percentage rides with the engine's **multiply step**, so a discounted line
  is still rounded exactly once and the non-positive guard still governs it.
  A 100% discount cannot produce a zero-priced line; the engine refuses it.

The catalog model in `pricing/catalog.py` is untouched. An adjustment is an
addition to the engine's *input*, never to an item.

### Other things the CLI has no equivalent for

Each is marked in the code where it lives:

- **Matching is scoped to the cities a trip visits**, mirroring the real
  engine's one-region-at-a-time mapping.
- **The confirm modal is offered only candidates that share a word** with the
  consultant's wording — a rule about what to display, never about what to
  accept.
- **A price can be overridden by hand on any line.** An overridden figure
  moves out of the rate sheet's total and into the consultant's own, is
  labelled as hers everywhere it appears, and the rate sheet's figure stays on
  screen beside it. An override you cannot see is an override nobody checks.
- **Accommodation is not priced by the engine at all.** The ported model knows
  `per_person` and `per_group` and has no concept of a night, and §4 says not
  to redesign it — so a stay carries its own rate, and every screen showing a
  stay total says it came from the accommodation booking. A trip's headline
  figure always shows its composition beside it.

## The rules that are not negotiable

These are enforced in code, not by convention, and the tests hold them:

1. A refusal is a **return value**, not an exception — so no screen has a code
   path that can render a price the engine declined to produce.
2. Auto-match happens on an **identical normalised name or a saved alias**.
   There is no similarity threshold anywhere.
3. A total of zero or less is **never** a price.
4. Currencies are **never added together**. There is no exchange rate here.
5. "Needs a quick check" and "needs a supplier quote" are **never merged** into
   one list, on any screen. One is a ten-second pick; the other is an email.
   A day planner is by nature one chronological list, so the separation lives
   in the strip above it: two counts that never combine, each opening its own
   list. In the days below they are different colours and never look alike.
6. The costed copy **never writes a zero** where there is no price. An empty
   cost cell plus a sentence saying why, every time.
7. A note the parser cannot read **never changes a number**, and is never
   stripped out of the wording.

## The blank template

**My quotes** offers a real `itinerary_template.xlsx`, written by hand rather
than with a spreadsheet library. An .xlsx is a zip of XML parts and Excel
accepts stored, uncompressed entries, so `src/template/zip.ts` is a CRC and
some little-endian headers — a small enough surface to own outright for one
fixed file.

"Optimised for this application" is a shape, not a decoration. The sample
workbook in `samples/build_samples.py` deliberately carries a title block and
a merged category band because those are what break parsers; this file is the
opposite of it:

- The five columns `pricing/itinerary_profile.py` looks for, in **row one**,
  with nothing above them, on a single sheet.
- The cost column left empty — that is the column the tool fills, in a copy.
- **Sixty empty rows beneath the header, which are load-bearing.**
  `find_header_candidates` skips any row with nothing under it (`row >=
  max_row`), so a sheet holding only headers is a template the tool cannot
  read. This was found by running the generated file through the real
  profiler, not by reasoning about it.

It is verified against the engine itself rather than against my own idea of
the format. The file the browser hands a consultant is byte-identical (same
SHA-256) to one that `openpyxl` opens without warnings and that
`propose_template` profiles to `name→A, date→B, pax→C, day_part→D, cost→E`.

## Known gaps

- The drop zone does not accept a real `.xlsx`. The three sample trips are the
  demo path, by decision.
- The **costed copy** is a `.csv`, not an `.xlsx` — the handoff allows
  either. The blank template is a real `.xlsx`, since that is the file a
  consultant fills in and drops back.
- The admin screen is read-only, and its usage figures are marked as samples.
- Hotel rates are sample data with no system behind them. In the real product
  they would come from wherever accommodation is actually booked.

## Publishing it as an Artifact

The Artifact host wraps the page in its own document shell, so Vite's
`dist/index.html` cannot be published directly — it carries its own
`<html>`/`<head>`/`<body>`. `scripts/artifact-page.mjs` reads the hashed asset
names out of the built `index.html` and writes a `dist/page.html` that mounts
the same bundle:

```bash
pnpm --dir demo build && node demo/scripts/artifact-page.mjs
```

Then publish `demo/dist/page.html`, passing `demo/dist` as the root and the
two `assets/…` files alongside it. Republishing the same path keeps the URL.
