# Itinerary Pricing Automation — Design

**Date:** 2026-09-03
**Status:** Approved design, ready for implementation planning

## Problem

A travel agent prices client itineraries by hand. Supplier rates arrive as PDFs, which
are parsed into a single Excel costing workbook — one sheet per city/country/region,
fewer than 100 experiences per sheet. The workbook was built for humans to read, not
for machines to parse: layouts vary between sheets, pricing axes are encoded
inconsistently, and rates change without notice.

For every quote she locates each experience in the workbook, reads off the rate that
applies to that group size, time of day, day of week and season, and copies the number
into the itinerary's cost sheet. It is slow, repetitive, and a transcription error
reaches a paying client.

**Goal:** she attaches an itinerary, and gets back the same itinerary with the cost
sheet filled in correctly.

## Constraints

- **The operator is non-technical.** Every interaction is a slash command in the Claude
  desktop app. She never edits JSON, never uses git, never reads a traceback.
- **She is remote from the developer.** Support happens over the phone. Diagnostics must
  be self-describing.
- **Neither developer nor Claude can see the real data.** Rates and client names are
  proprietary and cannot be transmitted. The design must discover its own input shape
  and must be testable without real data.
- **Her platform is unknown** (Mac or Windows). Everything is platform-agnostic.
- **Output is net cost only.** Markup and commission remain her judgment; the columns
  and rules file are structured so markup could be added later without rework.

## Guiding principle

**Claude does language. Python does money.**

The model reads sheets, interprets structure, and resolves fuzzy names — with the
operator confirming. It never returns a number. It returns a *mapping*
("itinerary line 14 → catalog item `IT-FLR-0032`, 4 pax, Saturday PM") and Python looks
up the rate and computes the total.

A wrong answer is therefore always a wrong *match* — visible, explainable, correctable.
Never a wrong *sum*, which is invisible.

## Architecture

Approach: skills orchestrating a small, self-contained Python engine.

```
itinerary-pricing/
├── .claude/
│   ├── skills/
│   │   ├── profile-rate-sheet/SKILL.md
│   │   ├── map-rate-sheet/SKILL.md
│   │   ├── cost-itinerary/SKILL.md
│   │   └── refresh-rates/SKILL.md
│   └── commands/           # /profile /map /cost /refresh /verify /doctor /update
├── pricing/                # the engine: no LLM, no network, pure functions
│   ├── workbook.py         # all Excel I/O — the only module that touches xlsx
│   ├── profile.py          # Phase 0 structural profiling + redaction
│   ├── catalog.py          # mapping table load/save/validate
│   ├── match.py            # candidate generation + deterministic scoring
│   ├── patterns.py         # pricing patterns and their evaluation
│   ├── cost.py             # itinerary line → priced line
│   └── report.py           # audit trail
├── data/                   # her data — gitignored, never leaves her machine
│   ├── profiles/
│   ├── catalog.json
│   ├── aliases.json
│   └── runs/
├── tests/fixtures/         # synthetic workbooks
├── SETUP.md
└── README.md
```

`pricing/` is a normal Python package with a CLI (`python -m pricing.cost ...`). It has
no knowledge of Claude. Claude invokes it via Bash and reads structured JSON back.

There are seven commands but only four skills: `/verify`, `/doctor` and `/update` are
thin wrappers over deterministic engine calls and need no model reasoning, so they carry
no skill of their own.
Every calculation is therefore testable, replayable, and debuggable with no model in the
loop.

## Phases

Discovery is a permanent part of the pipeline, not a one-off warm-up. A system that
cannot re-derive its input shape breaks the first time a supplier changes a rate sheet.

### Phase 0 — Profile (`/profile`)

Reads the costing workbook and emits a **structural** report per sheet: sheet names and
dimensions, detected header rows, verbatim column headers, per-column fill rate and
cardinality, the distinct values of every low-cardinality column (where `Adult`/`Child`,
`Mon–Thu`, `Peak`/`Shoulder` live), merged-cell ranges, data block boundaries, and which
cells are formulas versus literals.

**Cells in columns classified as price-bearing are masked.** The report says "column H is
numeric with 340 non-empty values" and nothing about the values. The resulting profile
contains no rates and no client names, so it is safe for the operator to send to the
developer.

`/profile` also profiles **the itinerary template**, whose layout is equally unknown to
us: where line items begin, which columns hold the experience name, date, pax count and
time of day, and which columns are the empty cost cells to be filled. She confirms this
once; it is stored as `data/profiles/itinerary_template.json`. This is what lets Phase 2
parse an itinerary deterministically instead of guessing at its structure, and it is the
reason "produce a copy of her itinerary file" is achievable rather than aspirational.

Re-running `/profile` later is how structural drift is detected — a different and more
dangerous failure than a changed price.

### Phase 0.5 — Schema proposal

Claude reads the profile and proposes the pricing model: which variation axes exist
(pax tier, time of day, day of week, season, blackout; per-person vs per-group) and how
each is encoded in her layout. She confirms or corrects axis by axis. The unknown is
resolved by the person who knows the answer.

### Phase 1 — Map (`/map <region>`)

Walks one sheet's rows and proposes a catalog entry for each. Once a shape is confirmed,
Claude proposes structurally identical rows **as a group**, so a 90-row sheet becomes
roughly 8 real decisions plus outliers.

`catalog.json` is written after **every** confirmation. `/map Italy` resumes exactly
where she stopped.

Because the unit of work is one sheet, she gets value after mapping a single region —
no big-bang migration.

### Phase 2 — Cost (`/cost`)

1. Python parses the itinerary into line items using the confirmed itinerary-template
   profile (experience, date, pax, time of day).
2. Alias hit or unambiguous name match → priced silently.
3. Ambiguous → Claude pauses with the top three candidates and its reasoning; she picks;
   the alias is saved so it never asks again.
4. Any `last_seen` mismatch is reported inline during the run.
5. Python writes `<name>_costed_<date>.xlsx` beside the original and prints a summary.

### Phase 3 — Refresh (`/refresh`) and Verify (`/verify`)

`/refresh` re-profiles and diffs against the catalog, reporting what changed.
`/verify` re-costs an itinerary she already priced by hand and diffs the two.

## Data model

Four JSON files in `data/`, all local.

### `catalog.json`

```json
{
  "id": "IT-FLR-0032",
  "name": "Uffizi Gallery — Private Guided Tour",
  "region": "Italy",
  "currency": "EUR",
  "unit": "per_person",
  "pricing": {
    "pattern": "tiered_by_pax",
    "tiers": [
      { "max_pax": 4,  "cell": "Italy!D14", "last_seen": "285.00" },
      { "max_pax": 10, "cell": "Italy!D15", "last_seen": "240.00" }
    ]
  },
  "modifiers": [
    { "type": "day_part", "when": "PM", "op": "add", "cell": "Italy!F14", "last_seen": "40.00" }
  ],
  "source_rows": [14, 15],
  "row_fingerprint": "sha1:9c2f…",
  "confirmed_at": "2026-09-03"
}
```

**Every rate is a cell reference plus the value last seen there — never a copied number.**
This single choice does three jobs:

- **Prices are never stale.** Costing reads the live cell. She updates the workbook and
  the next quote is correct with no re-mapping.
- **Price changes surface themselves.** A live value differing from `last_seen` is
  reported *during the costing run*, so she learns about it while quoting rather than
  months later. Periodic re-mapping stops being a chore she must remember.
- **Structural drift is caught.** `row_fingerprint` hashes the row's label cells. If rows
  are inserted and `Italy!D14` now holds a different tour, the fingerprint breaks and the
  engine **refuses to price that item**. This is the failure the design most needs to
  prevent, because it is silent and wrong by hundreds of euros.

### `aliases.json`

The learning layer. Normalized itinerary phrasing → catalog id, written whenever she
resolves an ambiguous match.

```json
{ "sunset catamaran w open bar": { "id": "GR-SAN-0011", "hits": 4 } }
```

### `profiles/<sheet>.json`

Phase 0 output. Structure and redacted statistics only. The one file safe to send to the
developer.

### `runs/<timestamp>.json`

Every costing run: inputs, each line's matched id, confidence, cells read, values
computed. "Why did this quote say €1,240?" is answered by a file, not a recollection.

### Pricing patterns

A closed set, deliberately not a rules DSL. Only the patterns Phase 0 finds in her sheet
get implemented.

Two orthogonal axes rather than a list of named patterns. `pattern` selects the rate;
`unit` selects the multiplier. Together with an optional `min_billable_pax` they cover
every shape we expect, with half the code paths of four overlapping patterns.

| `pattern` | Selects the rate by |
|---|---|
| `flat` | A single cell |
| `tiered_by_pax` | Bracket matching on group size |

| `unit` | Multiplies by |
|---|---|
| `per_person` | Pax, floored at `min_billable_pax` when present |
| `per_group` | 1 |

So a per-group transfer is `flat` + `per_group`; a class with a six-person minimum is
`flat` + `per_person` + `min_billable_pax: 6`.

Stacking modifiers: `day_part`, `day_of_week`, `seasonal`, `blackout`. Each carries an
`op` of `add_per_unit`, `add_per_booking`, or `multiply`, so the point at which a
supplement applies is explicit rather than inferred.

## Failure handling

- **The original file is never opened for writing.** Copy first, write to the copy. No
  code path can modify her input.
- **Fingerprint mismatch → the item refuses to price**, naming the row and directing her
  to re-run `/map` for that sheet. It does not guess.
- **Out-of-range requests return `needs_quote` with a reason** — 14 pax against a 10-pax
  ceiling, a blackout date, a missing modifier. **The engine never extrapolates a price.**
  A blank cell costs two minutes; an invented rate costs a client.
- **`needs_quote` is visible in the output sheet**, never a blank cell that could pass
  for zero.
- **Money is `Decimal`, never `float`.** Rates are read from Excel as strings and parsed.
- **Mixed currencies never silently sum.** Subtotals are per-currency; a cross-currency
  total requires a rate she supplies explicitly.
- **Every engine error has a plain-English surface and a full traceback in `runs/`.**
  A locked workbook produces "Please close Costing_2026.xlsx and try again", not a
  `PermissionError`.

## Testing

1. **Synthetic fixtures.** Workbooks in `tests/fixtures/` — one per pricing pattern, plus
   deliberately nasty cases: merged header cells, blank rows mid-block, rates stored as
   text (`"€285"`), an inserted row that breaks a fingerprint, a pax count above the top
   tier. The engine is built test-first against these. Requires no real data.
2. **A redaction test.** Asserts profiler output contains no value from any column
   classified as price-bearing. The "safe to send" promise is verified, not assumed.
3. **`/verify` as acceptance.** She re-costs three trips she priced by hand. A
   cent-for-cent match proves the mapping in a way unit tests cannot. Mismatches print a
   line-by-line diff identifying the wrong catalog entry. Re-run after every `/refresh`.

## Setup and support

- **`uv`** pins the interpreter and dependencies with one installer, identically on Mac
  and Windows.
- **`/doctor`** checks Python, dependencies, that the costing workbook is findable and
  openable, and that `data/` is writable — reporting in plain English. Remote support
  becomes "run `/doctor` and read me what it says."
- **`/update`** runs `git pull` behind the scenes. She never types git.
- **Distribution:** private GitHub repo. One screen share to install; fixes ship without
  touching her machine afterward.
- **`data/` is gitignored and `pricing/` makes no network calls.** Her rates never leave
  her computer unless she personally sends a profile.

## Out of scope

- Markup, commission, and client-facing sell prices (columns and rules file are shaped to
  allow it later).
- PDF ingestion. Input is the existing Excel workbook; the PDF→Excel step stays manual.
- Multi-supplier rate sheets. One consolidated workbook today; the catalog carries a
  `region` field and can grow a `supplier` dimension without a rewrite.
- Any integration with the Voyage product. This is a standalone repo.
