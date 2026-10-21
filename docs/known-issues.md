# Known issues and follow-ups

Everything here was found by review during the initial build, judged non-blocking, and
deliberately shipped. Each entry says what the consequence actually is, because "minor"
in a tool that quotes money to clients needs justifying rather than asserting.

The safety properties these are judged against, in priority order:

1. The engine never modifies an input file.
2. The engine never invents a price — anything unpriceable raises `NeedsQuote`.
3. No similarity score gates auto-pricing: only an exact normalised name match or a
   saved alias auto-accepts.
4. The written profile carries no cell content, so it is safe to email. Sheet/tab names
   are a documented exception and do travel.
5. Structural drift in the workbook refuses to price rather than pricing the wrong cell.
6. All money is `Decimal`, rounded once, `ROUND_HALF_UP`, 2dp.
7. The CLI always prints exactly one JSON object, with plain-English errors.

## Worth fixing next

**Equal `max_pax` tiers resolve by list order.** `pricing/patterns.py`
Two tiers with the same `max_pax` price differently depending purely on JSON array order
(reproduced: EUR1,140 vs EUR960 for the same 4-pax request). Relatedly, a tiered item whose
lowest mapped tier does not start at 1 has no lower bound — mapping only the 5-10 tier
prices a party of 2 at the 5-10 rate without complaint. The rate sheets have a "Min Pax"
column that the catalog model currently discards.
*Fix:* reject duplicate `max_pax` in `catalog-add`; consider an optional `min_pax`.

**Header-candidate confirmation is rate-sheet only.** `pricing/itinerary_profile.py`
`/profile` shows every candidate header row for a rate sheet and lets the operator pick,
because the true header can rank last. `propose_template` takes `candidates[0]` for the
itinerary side with no equivalent confirmation. It usually fails loudly via
`MissingRoleError`; when it does not, the consequence is a silently skipped line.

**A leading minus is erased in matching.** `pricing/match.py`
`Deposit -50` and `Deposit 50` normalise identically and can auto-accept. Needs exactly
one of the pair mapped to bite. A sign inversion is a 20% swing.
*Fix:* preserve `-` when it immediately precedes a digit. Do NOT add `-` to the marker
set — `Skip-the-Line` matching `Skip the Line` is load-bearing.

**Non-xlsx input gets the generic error.** `pricing/cli.py`
Attaching a `.xls`, `.csv` or Numbers file yields "Something went wrong that I don't have
a friendly explanation for." This is a realistic step-one failure for the operator.

## Accepted, with reasoning

**`seat`/`room` in the plural allowlist.** Unlike `guide` (where "Private Guides" names a
genuinely different product), plurality of `seat`/`room`/`night`/`adult` in an experience
name is grammatical rather than quantitative — the count lives in the number, which
normalisation preserves.

**An alias hit short-circuits the ambiguity guard.** An alias is the operator's own prior
confirmation, the strongest signal in the system; deferring to it over an unresolved
duplicate-name tie is correct.

**An uncached formula in a rate cell.** Reads as `None`, which produces `NeedsQuote`.
Fails safe. The message is a shade technical for the audience.

**An `os.replace` failure leaks a temp file.** Leaves a hidden dotfile beside the output.
The destination stays clean, which is the part that matters.

**`compute_structure_fingerprint` hashes a blank cell as the string `"none"`,** so a cell
containing the text "None" is indistinguishable from a blank. Over-refuses, which is the
safe direction.

## Housekeeping

- Duplicated normalisation: `pricing/catalog.py` inlines whitespace/case folding under a
  comment saying it works "the same way `fingerprint()` does" instead of calling it.
  Guaranteed to drift. `profile._tokenize_header` is imported as a private symbol across
  a module boundary and is ASCII-only, while `match.normalize` is Unicode-aware — they
  disagree on accented headers.
- Dead or test-only code: `Catalog.by_region`, `ItineraryTemplate.alternatives`,
  `CellRef.__str__`. `ColumnProfile.header` and `.sample_values` additionally cost a full
  extra read pass over every cell during `/profile`.
- `verify_itinerary` opens a `Workbook` it never closes.
- `_prefer_empty_cost_column` uses `max()` on column letters, so `max("Z", "AA") == "Z"` —
  wrong for itineraries wider than 26 columns.
- A modifier carrying both `factor` and `cell` silently ignores the `cell`, so a mapped
  rate cell that has since vanished goes undetected.

## A note on the test suite

Two guards were found to survive deletion with the whole suite green: `patterns.py`'s
"no rate available" refusal and `catalog.py`'s skip of an unparseable rate cell. Both are
now pinned by `test_invalid_modifier_rate_cell_never_silently_drops_the_modifier`, and
both mutations were re-verified to fail after every subsequent change.

The pattern worth remembering: the guards that were *argued about* during the build are
superbly tested; the guards that were merely *written* were not tested at all. When adding
a safety check here, break it deliberately and confirm something fails.
