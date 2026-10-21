# Itinerary Pricing Automation

Turns a travel agent's Excel costing workbook into a structured price catalog, then
fills in the cost column on client itineraries automatically — without ever guessing a
price it isn't sure of, and without ever touching the operator's original files.

> **Note:** this project was built for a real client. All client data — agency and
> operator names, supplier rates, and real trip details — has been removed. Everything
> in `samples/` and `demo/` is synthetic fixture data, invented to exercise the same
> shapes the real sheets have.

## The core idea: the LLM does language, Python does money

The system is deliberately split across a hard boundary:

- **The LLM reads and writes language.** It interprets a spreadsheet's structure,
  resolves fuzzy phrasing ("Uffizi Gallery private tour" vs. "Uffizi Gallery — Private
  Guided Tour") with the operator confirming, and reports results back in plain
  English. This is the `.claude/skills/*` and `.claude/commands/*` layer.
- **Python does every calculation and every file write.** `pricing/` is a pure engine
  with no LLM dependency and no network access: every price is `Decimal` arithmetic
  against a rate read straight from a cell, every write lands on a copy, and every
  ambiguous case raises an explicit, human-readable failure instead of a guess.

The model never computes a price and never writes to a workbook directly — it only
calls `pricing/cli.py` and relays what comes back. That makes the pricing logic
testable and auditable with no model in the loop.

## Key design decisions

- **Privacy-preserving profiling.** The rate-sheet profiler emits structure only —
  sheet dimensions, header locations, column kinds, fill rates. Price-bearing columns
  are masked, so the profile can be emailed to a developer for troubleshooting without
  exposing a single rate or client name.
- **Cell-reference mapping tables.** The catalog stores rates as cell references plus
  the value last seen there — never copied numbers. Prices can't go stale (costing
  reads the live cell), price changes surface themselves during a run, and structural
  drift is caught by row fingerprints: if rows are inserted and a cell now holds a
  different tour, the fingerprint breaks and the engine *refuses to price that item*.
- **No similarity-score auto-pricing.** A line prices itself only on an exact
  normalised name match or a previously confirmed alias. Near-identical experiences
  with different prices ("Private Guide" vs. "Small Group", reversed transfer
  directions) can never be silently confused.
- **`Decimal` money, always.** Rates are parsed from Excel as strings; rounding happens
  once, half-up, at the end. The engine never extrapolates — anything outside the
  mapped range comes back as an explicit "needs a quote".
- **Per-run audit trails.** Every costing run writes a log of inputs, matches,
  confidence, cells read, and values computed. "Why did this quote say €1,240?" is
  answered by a file, not a recollection.
- **The operator is non-technical.** Every interaction is a slash command in the chat
  app (`/profile`, `/map`, `/cost`, `/verify`, `/refresh`, `/doctor`). She never edits
  JSON, never uses git, never reads a traceback — every engine error has a
  plain-English surface.

## Repository layout

| Path | What it is |
|---|---|
| `pricing/` | The engine: 15 Python modules, no network, JSON CLI (`python -m pricing …`). |
| `.claude/skills/` | Conversational procedures for profiling, mapping, costing, refreshing. |
| `.claude/commands/` | The slash commands the operator types. |
| `tests/` | 350+ pytest tests, built against synthetic workbooks in `tests/fixtures/`. |
| `samples/` | A synthetic Dubrovnik dataset (rate sheet + itineraries) plus the generator
| | script `build_samples.py`. Regenerate with `uv run python samples/build_samples.py`. |
| `demo/` | A standalone TypeScript/React demo web app (Vite) with invented pan-European
| | sample data — a clickable walkthrough of the workflow. |
| `design/` | UI mockups for the demo app. |
| `docs/` | Design spec, implementation plan, known-issues log, fidelity findings. |
| `SETUP.md` | Install and first-run instructions (operator-facing). |
| `START-HERE.md` | Operator onboarding: the order to do things in, how to tell if it's working. |
| `data/` | **Gitignored.** Holds a real deployment's catalog, aliases, profiles, and run
| | logs. Ships empty except a template profile. |

## Try it with the synthetic fixtures

```
# Install uv (https://astral.sh/uv), then:
uv sync --extra dev

# Run the full test suite
uv run pytest

# Regenerate the sample dataset
uv run python samples/build_samples.py

# Build a known-good catalog from the samples and price an itinerary
uv run python samples/build_reference_catalog.py
uv run python -m pricing cost --file samples/Trip_Sample_Dubrovnik.xlsx
```

The samples exercise the awkward shapes real rate sheets have: title blocks above
headers, merged category bands, tiers expressed as rows, per-group vs. per-person
units, time-of-day and seasonal supplements, minimum billable party sizes, blackout
dates, rates typed as text, and genuinely unpriceable lines. See `samples/README.md`
for the expected answers — a disagreement means something is wrong, not that the
sample is approximate.

## Tech stack

- **Python 3.12** (pinned via `uv`), `openpyxl` + `Pillow` for Excel I/O, `pytest`
  for tests, `decimal.Decimal` for all money, stdlib-only matching
- **Claude Code skills** (`.claude/skills/`, `.claude/commands/`) for the operator
  conversation layer
- **TypeScript + React + Vite** for the standalone demo app (`demo/`)

## License

MIT — see [LICENSE](LICENSE).
