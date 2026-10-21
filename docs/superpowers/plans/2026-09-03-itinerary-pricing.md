# Itinerary Pricing Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude-skills workflow that maps a travel agent's Excel costing workbook into a structured catalog, then auto-fills the cost columns of her itinerary files.

**Architecture:** A pure-Python engine (`pricing/`) does every file read, every file write, and every calculation, exposed as a JSON-in/JSON-out CLI. A thin skills layer (`.claude/`) drives it conversationally: Claude interprets structure and resolves fuzzy names with the operator confirming, then hands structured decisions to the engine. The engine has no LLM dependency and no network access, so it is testable and debuggable with no model in the loop.

**Tech Stack:** Python 3.12 (pinned by `uv`), `openpyxl` + `Pillow` for Excel I/O, `pytest` for tests, `Decimal` for all money, standard library only for matching (`difflib`). No other runtime dependencies.

## Global Constraints

These apply to every task. Every task's requirements implicitly include this section.

- **Python 3.12**, pinned in `pyproject.toml` via `requires-python = ">=3.12"` and `uv`.
- **Runtime dependencies are exactly `openpyxl` and `Pillow`.** Nothing else. Dev
  dependencies are exactly `pytest`. Pillow is not optional decoration: without it
  openpyxl's reader silently discards embedded images, which strips the agency logo
  out of the client-facing costed itinerary (measured in Task 4).
- **All money is `decimal.Decimal`.** No `float` may appear in any pricing code path. Rates are read from Excel and parsed through `pricing.money.parse_money`.
- **Rounding happens once, at the end of a calculation**, using `ROUND_HALF_UP` to 2 decimal places. Intermediate values keep full precision.
- **`pricing/` makes no network calls.** No `requests`, no `httpx`, no `urllib` outside of tests.
- **The engine never modifies an input file.** Writes go to a copy, always.
- **The engine never extrapolates a price.** Anything outside the mapped range raises `NeedsQuote` with a human-readable reason.
- **Every CLI entry point prints a single JSON object to stdout** and nothing else. Diagnostics go to stderr.
- **User-facing error text is plain English with no tracebacks.** Full tracebacks go to `data/runs/`.
- **Cross-platform:** no shell-outs, no hardcoded path separators. Use `pathlib` everywhere.
- **Commit after every task** using the message given in that task's final step.

## File Structure

| File | Responsibility |
|---|---|
| `pricing/money.py` | Parse Excel cell values into `Decimal`. The only place money parsing lives. |
| `pricing/workbook.py` | All Excel I/O. The only module importing `openpyxl`. |
| `pricing/profile.py` | Phase 0 structural profiling and redaction of rate sheets. |
| `pricing/itinerary_profile.py` | Phase 0 profiling of the itinerary template. |
| `pricing/patterns.py` | Pricing patterns and their evaluation. Pure functions, no I/O. |
| `pricing/catalog.py` | Catalog load/save/validate, row fingerprints, live rate resolution, drift detection. |
| `pricing/match.py` | Deterministic candidate scoring and the alias store. |
| `pricing/cost.py` | Orchestration: itinerary lines → priced lines. |
| `pricing/report.py` | Writing the costed workbook copy, run logs, and summaries. |
| `pricing/verify.py` | Diffing a re-costed itinerary against a hand-priced one. |
| `pricing/doctor.py` | Environment and configuration health check. |
| `pricing/config.py` | Locating `data/`, the costing workbook, and profiles. |
| `pricing/cli.py` | Argument parsing and JSON output for every entry point. |
| `tests/fixtures/build.py` | Constructs synthetic workbooks used by the whole test suite. |
| `.claude/skills/*/SKILL.md` | Conversational procedures for profile, map, cost, refresh. |
| `.claude/commands/*.md` | The seven commands the operator types. |
| `SETUP.md` | Install instructions written for a non-technical user, Mac and Windows. |

Files that change together live together: `patterns.py` owns the pricing semantics and nothing else touches them; `workbook.py` owns Excel and nothing else imports `openpyxl`.

---

### Task 1: Project scaffold and money parsing

Scaffolding is folded into this task because the first real unit needs a working toolchain to be tested at all.

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `pricing/__init__.py`
- Create: `pricing/money.py`
- Test: `tests/test_money.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `pricing.money.parse_money(value: object) -> Decimal`, `pricing.money.MoneyParseError(ValueError)`, `pricing.money.round_money(value: Decimal) -> Decimal`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "itinerary-pricing"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["openpyxl>=3.1"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["pricing"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
data/
__pycache__/
*.pyc
.pytest_cache/
.venv/
~$*.xlsx
```

`data/` is gitignored because it holds proprietary rates. `~$*.xlsx` is Excel's lock file on Windows.

- [ ] **Step 3: Create the package marker**

```bash
mkdir -p pricing tests/fixtures
touch pricing/__init__.py tests/__init__.py
```

- [ ] **Step 4: Write the failing test**

Create `tests/test_money.py`:

```python
from decimal import Decimal

import pytest

from pricing.money import MoneyParseError, parse_money, round_money


@pytest.mark.parametrize(
    "raw,expected",
    [
        (285, Decimal("285")),
        (285.5, Decimal("285.5")),
        ("285.00", Decimal("285.00")),
        ("€285", Decimal("285")),
        ("$1,234.50", Decimal("1234.50")),
        ("  240 ", Decimal("240")),
        ("1.234,50", Decimal("1234.50")),
    ],
)
def test_parses_money_shapes(raw, expected):
    assert parse_money(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "on request", "N/A", "TBC"])
def test_rejects_non_money(raw):
    with pytest.raises(MoneyParseError):
        parse_money(raw)


def test_float_input_does_not_leak_binary_error():
    # Excel hands back floats; 0.1 + 0.2 must not become 0.30000000000000004
    assert parse_money(0.1) + parse_money(0.2) == Decimal("0.3")


def test_round_money_uses_half_up():
    assert round_money(Decimal("2.345")) == Decimal("2.35")
    assert round_money(Decimal("2.344")) == Decimal("2.34")
```

The `1.234,50` case is European decimal notation. Her rate sheet covers European suppliers, so this will occur.

- [ ] **Step 5: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_money.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.money'`

- [ ] **Step 6: Write the implementation**

Create `pricing/money.py`:

```python
"""Parsing Excel cell values into Decimal money.

Every rate in the system passes through here. Floats from openpyxl are
converted via str() so that binary representation error never enters a
calculation.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENTS = Decimal("0.01")

# Currency symbols and codes we strip before parsing.
_STRIP = re.compile(r"[^\d,.\-]")


class MoneyParseError(ValueError):
    """The value is not a price."""


def parse_money(value: object) -> Decimal:
    if value is None:
        raise MoneyParseError("empty cell")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise MoneyParseError(f"not a price: {value!r}")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if not isinstance(value, str):
        raise MoneyParseError(f"not a price: {value!r}")

    cleaned = _STRIP.sub("", value).strip()
    if not cleaned:
        raise MoneyParseError(f"not a price: {value!r}")

    cleaned = _normalise_separators(cleaned)
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise MoneyParseError(f"not a price: {value!r}") from exc


def _normalise_separators(text: str) -> str:
    """Resolve ',' and '.' into a single decimal point.

    '1,234.50' -> '1234.50'   (comma is a thousands separator)
    '1.234,50' -> '1234.50'   (European: dot is thousands, comma is decimal)
    '240,50'   -> '240.50'    (lone comma with 2 trailing digits is decimal)
    """
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            return text.replace(".", "").replace(",", ".")
        return text.replace(",", "")
    if "," in text:
        head, _, tail = text.rpartition(",")
        if len(tail) == 2 and head.count(",") == 0:
            return f"{head}.{tail}"
        return text.replace(",", "")
    return text


def round_money(value: Decimal) -> Decimal:
    """Round to cents. Called once, at the end of a calculation."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_money.py -v`
Expected: PASS, 14 passed

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore pricing/ tests/
git commit -m "feat: project scaffold and Decimal money parsing"
```

---

### Task 2: The fixture matrix

Every later task tests against these. Building them first means no task ever needs real data.

**We do not know what her sheets look like.** A single fixture would encode a guess and
quietly bake it into the engine. So this task builds **five costing layouts and four
itinerary layouts**, chosen to span the shapes real rate sheets actually take. Two of them
are deliberately adversarial: they are expected to defeat naive heuristics, and later
tasks must handle them by *asking the operator*, not by guessing harder.

| Costing fixture | Sheet | Shape | Why |
|---|---|---|---|
| `build_rate_sheet` | Italy, Greece | One row per price point, tiers as rows | The baseline |
| `build_wide_rate_sheet` | Japan | Pax bands as **columns** (`1-4 Pax`, `5-10 Pax`, `11+ Pax`) | Extremely common; breaks any row-per-tier assumption |
| `build_stacked_rate_sheet` | SouthAfrica | Season rows with From/To date ranges, **USD** | Seasonal pricing + a second currency |
| `build_nasty_sheet` | Odd | Text rates, European notation, blank row, "on request" | Parsing robustness |
| `build_multiheader_sheet` | Portugal | **Two-row header** with merged category band | Adversarial: defeats `find_header_row` |

| Itinerary fixture | Shape | Why |
|---|---|---|
| `build_itinerary` | Headers row 7, name/date/pax/time/cost | The baseline |
| `build_day_grouped_itinerary` | `DAY 1 — FLORENCE` heading rows between line items | Very common; naive parsing prices the headings |
| `build_minimal_itinerary` | Headers row 1, name/pax/cost only — no date, no time | Forces `needs_quote` on time-dependent items |
| `build_wide_itinerary` | Pax stated **once** in a header cell, not per row | Adversarial: there is no pax column to find |

**Files:**
- Create: `tests/fixtures/build.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Consumes: nothing.
- Produces: the nine builder functions above, each `(path: Path) -> Path`. Pytest fixtures
  with the same names minus the `build_` prefix (`rate_sheet`, `wide_rate_sheet`,
  `stacked_rate_sheet`, `nasty_sheet`, `multiheader_sheet`, `itinerary`,
  `day_grouped_itinerary`, `minimal_itinerary`, `wide_itinerary`), each yielding a `Path`
  to a temporary `.xlsx`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_fixtures.py`:

```python
import openpyxl


def _ws(path, name):
    return openpyxl.load_workbook(path)[name]


def test_rate_sheet_has_expected_regions(rate_sheet):
    assert openpyxl.load_workbook(rate_sheet).sheetnames == ["Italy", "Greece"]


def test_rate_sheet_italy_has_tiered_rows(rate_sheet):
    ws = _ws(rate_sheet, "Italy")
    assert ws["A4"].value == "Uffizi Gallery — Private Guided Tour"
    assert ws["D4"].value == 285
    assert ws["D5"].value == 240


def test_wide_sheet_puts_pax_bands_in_columns(wide_rate_sheet):
    ws = _ws(wide_rate_sheet, "Japan")
    assert ws["B3"].value == "1-4 Pax"
    assert ws["C3"].value == "5-10 Pax"
    assert ws["A4"].value == "Tea Ceremony — Gion"
    assert ws["B4"].value == 120 and ws["C4"].value == 95


def test_stacked_sheet_has_season_rows_and_usd(stacked_rate_sheet):
    ws = _ws(stacked_rate_sheet, "SouthAfrica")
    assert ws["B3"].value == "Season"
    assert ws["A4"].value == ws["A5"].value  # same experience, two seasons
    assert ws["B4"].value == "Green" and ws["B5"].value == "Peak"
    assert ws["H4"].value == "USD"


def test_multiheader_sheet_has_a_merged_category_band(multiheader_sheet):
    ws = _ws(multiheader_sheet, "Portugal")
    assert "A3:C3" in [str(r) for r in ws.merged_cells.ranges]
    assert ws["A3"].value == "Group Size Pricing"
    assert ws["A4"].value == "Experience"      # the real header row
    assert ws["A5"].value == "Douro Valley Wine Tour"


def test_nasty_sheet_has_text_rate_and_blank_row(nasty_sheet):
    ws = _ws(nasty_sheet, "Odd")
    assert ws["C3"].value == "€285"
    assert ws["A5"].value is None


def test_itinerary_has_empty_cost_column(itinerary):
    ws = _ws(itinerary, "Itinerary")
    assert ws["A7"].value == "Experience"
    assert ws["E8"].value is None


def test_day_grouped_itinerary_interleaves_headings(day_grouped_itinerary):
    ws = _ws(day_grouped_itinerary, "Itinerary")
    assert ws["A6"].value == "DAY 1 — FLORENCE"
    assert ws["C6"].value is None            # headings carry no pax
    assert ws["A7"].value == "Uffizi Gallery private tour"
    assert ws["C7"].value == 4


def test_minimal_itinerary_has_no_date_or_time_column(minimal_itinerary):
    ws = _ws(minimal_itinerary, "Itinerary")
    headers = [ws.cell(row=1, column=c).value for c in range(1, 4)]
    assert headers == ["Experience", "Pax", "Cost"]


def test_wide_itinerary_states_pax_once_in_a_header_cell(wide_itinerary):
    ws = _ws(wide_itinerary, "Itinerary")
    assert ws["B3"].value == 4
    assert ws["A5"].value == "Experience"
    headers = [ws.cell(row=5, column=c).value for c in range(1, 5)]
    assert "Pax" not in headers
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_fixtures.py -v`
Expected: FAIL with `fixture 'rate_sheet' not found`

- [ ] **Step 3: Write the builders**

Create `tests/fixtures/build.py`:

```python
"""Synthetic workbooks standing in for the real, proprietary files.

Nine layouts spanning the shapes rate sheets and itineraries actually take.
Two are deliberately adversarial (multiheader, wide itinerary): the engine is
expected to notice it cannot be sure, not to guess well.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl


# ---------------------------------------------------------------- costing


def build_rate_sheet(path: Path) -> Path:
    """Baseline: one row per price point, tiers expressed as extra rows."""
    wb = openpyxl.Workbook()

    italy = wb.active
    italy.title = "Italy"
    italy["A1"] = "ITALY — NET RATES 2026"
    italy["A2"] = "All rates in EUR, per person unless stated"
    for col, header in zip("ABCDEF", ["Experience", "Min Pax", "Max Pax",
                                      "Net Rate", "Unit", "PM Supplement"]):
        italy[f"{col}3"] = header
    italy["A4"] = "Uffizi Gallery — Private Guided Tour"
    italy["B4"], italy["C4"], italy["D4"], italy["E4"], italy["F4"] = 1, 4, 285, "per person", 40
    italy["A5"] = "Uffizi Gallery — Private Guided Tour"
    italy["B5"], italy["C5"], italy["D5"], italy["E5"], italy["F5"] = 5, 10, 240, "per person", 40
    italy["A6"] = "Vatican Museums — Skip the Line"
    italy["B6"], italy["C6"], italy["D6"], italy["E6"] = 1, 12, 95, "per person"
    italy["A7"] = "Private Transfer — FCO to Rome Centre"
    italy["B7"], italy["C7"], italy["D7"], italy["E7"] = 1, 3, 110, "per group"
    italy.merge_cells("A1:F1")

    greece = wb.create_sheet("Greece")
    greece["A1"] = "GREECE — NET RATES 2026"
    for col, header in zip("ABCDE", ["Experience", "Min Pax", "Max Pax", "Net Rate", "Unit"]):
        greece[f"{col}3"] = header
    greece["A4"] = "Catamaran Cruise — PM (beverages incl.)"
    greece["B4"], greece["C4"], greece["D4"], greece["E4"] = 2, 8, 165, "per person"

    wb.save(path)
    return path


def build_wide_rate_sheet(path: Path) -> Path:
    """Pax bands as columns — the layout that breaks row-per-tier parsing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Japan"
    ws["A1"] = "JAPAN — NET RATES 2026 (EUR)"
    ws.merge_cells("A1:F1")
    for col, header in zip("ABCDEF", ["Experience", "1-4 Pax", "5-10 Pax", "11+ Pax",
                                      "PM Supplement", "Unit"]):
        ws[f"{col}3"] = header
    ws["A4"] = "Tea Ceremony — Gion"
    ws["B4"], ws["C4"], ws["D4"], ws["E4"], ws["F4"] = 120, 95, 80, 15, "per person"
    ws["A5"] = "Tsukiji Market Walking Tour"
    ws["B5"], ws["C5"], ws["D5"], ws["F5"] = 85, 70, 60, "per person"
    ws["A6"] = "Private Transfer — HND to Shinjuku"
    ws["B6"], ws["C6"], ws["D6"], ws["F6"] = 140, 140, 140, "per group"
    wb.save(path)
    return path


def build_stacked_rate_sheet(path: Path) -> Path:
    """Season rows with explicit date ranges, and a second currency."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SouthAfrica"
    ws["A1"] = "SOUTH AFRICA — NET RATES 2026/27"
    for col, header in zip("ABCDEFGH", ["Experience", "Season", "From", "To",
                                        "Min Pax", "Max Pax", "Net Rate", "Currency"]):
        ws[f"{col}3"] = header
    ws["A4"] = "Table Mountain — Private Guide"
    ws["B4"], ws["C4"], ws["D4"] = "Green", "2026-05-01", "2026-09-30"
    ws["E4"], ws["F4"], ws["G4"], ws["H4"] = 1, 6, 180, "USD"
    ws["A5"] = "Table Mountain — Private Guide"
    ws["B5"], ws["C5"], ws["D5"] = "Peak", "2026-10-01", "2027-04-30"
    ws["E5"], ws["F5"], ws["G5"], ws["H5"] = 1, 6, 240, "USD"
    ws["A6"] = "Cape Point — Full Day"
    ws["B6"] = "All Year"
    ws["E6"], ws["F6"], ws["G6"], ws["H6"] = 1, 8, 310, "USD"
    wb.save(path)
    return path


def build_nasty_sheet(path: Path) -> Path:
    """Parsing robustness: text rates, European notation, a gap, a non-price."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Odd"
    ws["A1"] = "MISCELLANEOUS"
    ws["A2"], ws["B2"], ws["C2"] = "Experience", "Pax", "Rate"
    ws["A3"], ws["B3"], ws["C3"] = "Cooking Class — Trastevere", 6, "€285"
    ws["A4"], ws["B4"], ws["C4"] = "Wine Tasting — Chianti", 4, "1.234,50"
    # row 5 intentionally blank — splits the data block
    ws["A6"], ws["B6"], ws["C6"] = "Truffle Hunt — Umbria", 2, "on request"
    wb.save(path)
    return path


def build_multiheader_sheet(path: Path) -> Path:
    """Adversarial: a merged category band above the real header row.

    Row 3 has three text cells, so a naive 'first row with 3+ text cells'
    heuristic picks it — and is wrong. The real header is row 4.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Portugal"
    ws["A1"] = "PORTUGAL — NET RATES 2026"
    ws["A3"], ws["D3"], ws["E3"] = "Group Size Pricing", "Supplements", "Notes"
    ws.merge_cells("A3:C3")
    for col, header in zip("ABCDE", ["Experience", "1-4", "5-10", "PM", "Notes"]):
        ws[f"{col}4"] = header
    ws["A5"] = "Douro Valley Wine Tour"
    ws["B5"], ws["C5"], ws["D5"] = 210, 175, 25
    ws["A6"] = "Sintra & Cascais Day Trip"
    ws["B6"], ws["C6"] = 195, 160
    wb.save(path)
    return path


# -------------------------------------------------------------- itinerary


def build_itinerary(path: Path) -> Path:
    """Baseline: a title block, then one row per line item."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"] = "SMITH FAMILY — ITALY & GREECE"
    ws["A2"] = "14–24 June 2026"
    ws["A3"] = "Prepared by: Travel Agency"
    for col, header in zip("ABCDE", ["Experience", "Date", "Pax", "Time", "Net Cost"]):
        ws[f"{col}7"] = header
    ws["A8"] = "Uffizi Gallery private tour"
    ws["B8"], ws["C8"], ws["D8"] = "2026-06-15", 4, "PM"
    ws["A9"] = "Vatican Museums skip the line"
    ws["B9"], ws["C9"], ws["D9"] = "2026-06-17", 4, "AM"
    ws["A10"] = "Sunset catamaran w/ open bar"
    ws["B10"], ws["C10"], ws["D10"] = "2026-06-21", 4, "PM"
    wb.save(path)
    return path


def build_day_grouped_itinerary(path: Path) -> Path:
    """Day headings interleaved with line items.

    The headings have a name but no pax — that is how a parser tells them
    apart from real line items.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"] = "JONES PARTY — ITALY"
    for col, header in zip("ABCDE", ["Experience", "Date", "Pax", "Time", "Net Cost"]):
        ws[f"{col}5"] = header
    ws["A6"] = "DAY 1 — FLORENCE"
    ws["A7"] = "Uffizi Gallery private tour"
    ws["B7"], ws["C7"], ws["D7"] = "2026-06-15", 4, "PM"
    ws["A8"] = "DAY 2 — ROME"
    ws["A9"] = "Vatican Museums skip the line"
    ws["B9"], ws["C9"], ws["D9"] = "2026-06-17", 4, "AM"
    wb.save(path)
    return path


def build_minimal_itinerary(path: Path) -> Path:
    """No date column and no time column — time-dependent items cannot price."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"], ws["B1"], ws["C1"] = "Experience", "Pax", "Cost"
    ws["A2"], ws["B2"] = "Uffizi Gallery private tour", 4
    ws["A3"], ws["B3"] = "Vatican Museums skip the line", 4
    wb.save(path)
    return path


def build_wide_itinerary(path: Path) -> Path:
    """Adversarial: pax is stated once for the whole trip, not per row."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Itinerary"
    ws["A1"] = "BROWN FAMILY — ITALY"
    ws["A3"], ws["B3"] = "Party size:", 4
    for col, header in zip("ABCD", ["Experience", "Date", "Time", "Net Cost"]):
        ws[f"{col}5"] = header
    ws["A6"] = "Uffizi Gallery private tour"
    ws["B6"], ws["C6"] = "2026-06-15", "PM"
    ws["A7"] = "Vatican Museums skip the line"
    ws["B7"], ws["C7"] = "2026-06-17", "AM"
    wb.save(path)
    return path
```

- [ ] **Step 4: Wire the pytest fixtures**

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest

from tests.fixtures import build


@pytest.fixture
def rate_sheet(tmp_path: Path) -> Path:
    return build.build_rate_sheet(tmp_path / "Costing_2026.xlsx")


@pytest.fixture
def wide_rate_sheet(tmp_path: Path) -> Path:
    return build.build_wide_rate_sheet(tmp_path / "Costing_Wide.xlsx")


@pytest.fixture
def stacked_rate_sheet(tmp_path: Path) -> Path:
    return build.build_stacked_rate_sheet(tmp_path / "Costing_Stacked.xlsx")


@pytest.fixture
def nasty_sheet(tmp_path: Path) -> Path:
    return build.build_nasty_sheet(tmp_path / "Nasty.xlsx")


@pytest.fixture
def multiheader_sheet(tmp_path: Path) -> Path:
    return build.build_multiheader_sheet(tmp_path / "Costing_Multiheader.xlsx")


@pytest.fixture
def itinerary(tmp_path: Path) -> Path:
    return build.build_itinerary(tmp_path / "Trip_Smith.xlsx")


@pytest.fixture
def day_grouped_itinerary(tmp_path: Path) -> Path:
    return build.build_day_grouped_itinerary(tmp_path / "Trip_Jones.xlsx")


@pytest.fixture
def minimal_itinerary(tmp_path: Path) -> Path:
    return build.build_minimal_itinerary(tmp_path / "Trip_Minimal.xlsx")


@pytest.fixture
def wide_itinerary(tmp_path: Path) -> Path:
    return build.build_wide_itinerary(tmp_path / "Trip_Brown.xlsx")
```

- [ ] **Step 5: Add the fixtures package marker**

```bash
touch tests/__init__.py tests/fixtures/__init__.py
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_fixtures.py -v`
Expected: PASS, 10 passed

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "test: nine synthetic workbook layouts spanning real rate sheet and itinerary shapes"
```

---

### Task 3: Workbook I/O and safe copy-then-write

**Files:**
- Create: `pricing/workbook.py`
- Test: `tests/test_workbook.py`

**Interfaces:**
- Consumes: `pricing.money.parse_money`.
- Produces:
  - `pricing.workbook.CellRef` — frozen dataclass with `sheet: str`, `column: str`, `row: int`; `CellRef.parse(ref: str) -> CellRef`; `str(ref)` returns `"Italy!D14"`.
  - `pricing.workbook.Workbook(path: Path)` with methods `sheet_names() -> list[str]`, `read(ref: CellRef) -> object`, `read_row(sheet: str, row: int) -> list[object]`, `dimensions(sheet: str) -> tuple[int, int]`, `merged_ranges(sheet: str) -> list[str]`, `is_formula(ref: CellRef) -> bool`, `write(ref: CellRef, value: object) -> None`, `save() -> None`, `close() -> None`.
  - `pricing.workbook.copy_for_write(src: Path, dst: Path) -> Path`
  - `pricing.workbook.WorkbookLockedError(RuntimeError)`

- [ ] **Step 1: Write the failing test**

Create `tests/test_workbook.py`:

```python
import shutil

import pytest

from pricing.workbook import CellRef, Workbook, WorkbookLockedError, copy_for_write


def test_cellref_roundtrips():
    ref = CellRef.parse("Italy!D14")
    assert (ref.sheet, ref.column, ref.row) == ("Italy", "D", 14)
    assert str(ref) == "Italy!D14"


def test_cellref_handles_quoted_sheet_names():
    ref = CellRef.parse("'South Africa'!AB7")
    assert (ref.sheet, ref.column, ref.row) == ("South Africa", "AB", 7)


def test_cellref_rejects_garbage():
    with pytest.raises(ValueError):
        CellRef.parse("D14")


def test_reads_values(rate_sheet):
    wb = Workbook(rate_sheet)
    assert wb.sheet_names() == ["Italy", "Greece"]
    assert wb.read(CellRef.parse("Italy!D4")) == 285
    assert wb.read_row("Italy", 4)[0] == "Uffizi Gallery — Private Guided Tour"
    wb.close()


def test_reports_merged_ranges(rate_sheet):
    wb = Workbook(rate_sheet)
    assert "A1:F1" in wb.merged_ranges("Italy")
    wb.close()


def test_copy_for_write_leaves_original_untouched(rate_sheet, tmp_path):
    before = rate_sheet.read_bytes()
    dst = copy_for_write(rate_sheet, tmp_path / "out.xlsx")

    wb = Workbook(dst)
    wb.write(CellRef.parse("Italy!D4"), 999)
    wb.save()
    wb.close()

    assert rate_sheet.read_bytes() == before
    assert Workbook(dst).read(CellRef.parse("Italy!D4")) == 999


def test_locked_file_raises_friendly_error(rate_sheet, tmp_path, monkeypatch):
    def deny(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(shutil, "copy2", deny)
    with pytest.raises(WorkbookLockedError) as exc:
        copy_for_write(rate_sheet, tmp_path / "out.xlsx")
    assert "close" in str(exc.value).lower()
    assert rate_sheet.name in str(exc.value)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_workbook.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.workbook'`

- [ ] **Step 3: Write the implementation**

Create `pricing/workbook.py`:

```python
"""All Excel I/O. The only module in the package that imports openpyxl.

openpyxl is loaded twice per workbook: once with data_only=True to get the
cached values of formula cells (rates are often formulas), and once with
data_only=False so we can tell a formula from a literal. Reading returns
values; is_formula() answers the structural question.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import openpyxl

_REF = re.compile(r"^'?(?P<sheet>[^'!]+)'?!(?P<col>[A-Z]{1,3})(?P<row>\d+)$")


class WorkbookLockedError(RuntimeError):
    """The file is open in Excel, or otherwise not writable."""


@dataclass(frozen=True)
class CellRef:
    sheet: str
    column: str
    row: int

    @classmethod
    def parse(cls, ref: str) -> "CellRef":
        match = _REF.match(ref.strip())
        if not match:
            raise ValueError(f"not a cell reference: {ref!r}")
        return cls(match["sheet"], match["col"].upper(), int(match["row"]))

    def __str__(self) -> str:
        sheet = f"'{self.sheet}'" if "!" in self.sheet or " " in self.sheet else self.sheet
        return f"{sheet}!{self.column}{self.row}"

    @property
    def coordinate(self) -> str:
        return f"{self.column}{self.row}"


class Workbook:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._values = openpyxl.load_workbook(self.path, data_only=True)
        self._formulas = openpyxl.load_workbook(self.path, data_only=False)

    def sheet_names(self) -> list[str]:
        return list(self._values.sheetnames)

    def read(self, ref: CellRef) -> object:
        return self._values[ref.sheet][ref.coordinate].value

    def read_row(self, sheet: str, row: int) -> list[object]:
        ws = self._values[sheet]
        return [cell.value for cell in ws[row]]

    def dimensions(self, sheet: str) -> tuple[int, int]:
        ws = self._values[sheet]
        return (ws.max_row or 0, ws.max_column or 0)

    def merged_ranges(self, sheet: str) -> list[str]:
        return [str(rng) for rng in self._formulas[sheet].merged_cells.ranges]

    def is_formula(self, ref: CellRef) -> bool:
        value = self._formulas[ref.sheet][ref.coordinate].value
        return isinstance(value, str) and value.startswith("=")

    def write(self, ref: CellRef, value: object) -> None:
        self._formulas[ref.sheet][ref.coordinate] = value

    def save(self) -> None:
        try:
            self._formulas.save(self.path)
        except PermissionError as exc:
            raise WorkbookLockedError(_locked_message(self.path)) from exc

    def close(self) -> None:
        self._values.close()
        self._formulas.close()


def copy_for_write(src: Path, dst: Path) -> Path:
    """Copy src to dst so writes never touch the original.

    shutil.copy2 preserves the file byte-for-byte, including everything
    openpyxl would drop on a load/save round trip. Only cells we
    explicitly write are changed afterwards.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dst)
    except PermissionError as exc:
        raise WorkbookLockedError(_locked_message(src)) from exc
    return dst


def _locked_message(path: Path) -> str:
    return (
        f"Please close {path.name} in Excel and try again — "
        "the file is currently locked."
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_workbook.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add pricing/workbook.py tests/test_workbook.py
git commit -m "feat: workbook I/O with safe copy-then-write"
```

---

### Task 4: Round-trip fidelity check

**This task exists to answer a question that could change the design.** `copy_for_write` preserves the file, but `Workbook.save()` re-serialises through openpyxl, which is known to drop embedded images, charts, and some conditional formatting. Her itinerary template very likely carries a logo. We need to know exactly what survives before building the output path on top of it.

**Files:**
- Modify: `tests/fixtures/build.py` (add `build_branded_itinerary`)
- Modify: `tests/conftest.py` (add `branded_itinerary` fixture)
- Test: `tests/test_roundtrip_fidelity.py`
- Create: `docs/fidelity-findings.md`

**Interfaces:**
- Consumes: `pricing.workbook.Workbook`, `copy_for_write`.
- Produces: `tests.fixtures.build.build_branded_itinerary(path: Path) -> Path` — an itinerary containing an embedded PNG and a conditional-format rule. `docs/fidelity-findings.md` recording what survives.

- [ ] **Step 1: Add a branded fixture**

Append to `tests/fixtures/build.py`:

```python
def build_branded_itinerary(path: Path) -> Path:
    """An itinerary with a logo and conditional formatting.

    Mirrors what a real agency template carries, so we can measure what a
    save() round trip destroys.
    """
    import base64
    import io

    from openpyxl.drawing.image import Image
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import PatternFill

    build_itinerary(path)
    wb = openpyxl.load_workbook(path)
    ws = wb["Itinerary"]

    # A 1x1 red PNG is enough to detect drop-on-save.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    ws.add_image(Image(io.BytesIO(png)), "G1")

    ws.conditional_formatting.add(
        "E8:E20",
        CellIsRule(operator="lessThan", formula=["0"],
                   fill=PatternFill(start_color="FFC7CE", end_color="FFC7CE")),
    )
    wb.save(path)
    return path
```

- [ ] **Step 2: Add the fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def branded_itinerary(tmp_path: Path) -> Path:
    return build.build_branded_itinerary(tmp_path / "Trip_Branded.xlsx")
```

- [ ] **Step 3: Write the characterisation test**

Create `tests/test_roundtrip_fidelity.py`:

```python
"""Characterisation tests: what does an openpyxl save() actually destroy?

These assertions encode the *current measured* behaviour. If a future
openpyxl changes it, these fail loudly and docs/fidelity-findings.md needs
updating — which is the point.
"""

import openpyxl

from pricing.workbook import CellRef, Workbook, copy_for_write


def _images(path):
    return len(openpyxl.load_workbook(path)["Itinerary"]._images)


def _cf_ranges(path):
    return len(list(openpyxl.load_workbook(path)["Itinerary"].conditional_formatting))


def test_copy_alone_preserves_everything(branded_itinerary, tmp_path):
    dst = copy_for_write(branded_itinerary, tmp_path / "copy.xlsx")
    assert _images(dst) == _images(branded_itinerary)
    assert _cf_ranges(dst) == _cf_ranges(branded_itinerary)


def test_save_roundtrip_preserves_conditional_formatting(branded_itinerary, tmp_path):
    dst = copy_for_write(branded_itinerary, tmp_path / "out.xlsx")
    wb = Workbook(dst)
    wb.write(CellRef.parse("Itinerary!E8"), 1140)
    wb.save()
    wb.close()
    assert _cf_ranges(dst) == _cf_ranges(branded_itinerary)


def test_save_roundtrip_records_image_behaviour(branded_itinerary, tmp_path):
    """Whatever happens to images, record it explicitly rather than assume."""
    dst = copy_for_write(branded_itinerary, tmp_path / "out.xlsx")
    before = _images(branded_itinerary)
    wb = Workbook(dst)
    wb.write(CellRef.parse("Itinerary!E8"), 1140)
    wb.save()
    wb.close()
    after = _images(dst)
    assert before == 1
    # Assert the measured behaviour. Adjust to `after == 0` and document it
    # if openpyxl drops the image on this version.
    assert after == before, (
        f"openpyxl dropped {before - after} image(s) on save; "
        "update docs/fidelity-findings.md and see Step 5"
    )
```

- [ ] **Step 4: Run the tests and record what actually happens**

Run: `uv run --extra dev pytest tests/test_roundtrip_fidelity.py -v`

Two possible outcomes, both acceptable — do not "fix" the test to make it green:
- **All pass:** images survive. Proceed, and record that in Step 5.
- **`test_save_roundtrip_records_image_behaviour` fails:** images are dropped. Change that assertion to `assert after == 0` with a comment explaining it is the measured behaviour, and record the consequence in Step 5.

- [ ] **Step 5: Write the finding**

Create `docs/fidelity-findings.md` recording, in plain language: the openpyxl version tested, whether images survived, whether conditional formatting survived, and the resulting rule for `/cost`.

If images are dropped, the rule is: **`/cost` must warn in its summary** — "Note: your itinerary's logo is not carried into the costed copy" — and Phase 0 must ask the operator to confirm the costed output looks acceptable before she relies on it. Add that sentence verbatim to the document, because Task 11 will implement it.

- [ ] **Step 6: Commit**

```bash
git add tests/ docs/fidelity-findings.md
git commit -m "test: characterise openpyxl round-trip fidelity"
```

---

### Task 5: Pricing patterns

The spec listed four patterns. Implementation collapses them into **two orthogonal axes**, which covers all four cases with half the code paths and is easier for Claude to emit correctly:

| Spec pattern | Expressed as |
|---|---|
| flat (per person) | `pattern: flat` + `unit: per_person` |
| per_group | `pattern: flat` + `unit: per_group` |
| tiered_by_pax | `pattern: tiered_by_pax` + `unit: per_person` |
| per_group_with_minimum | `pattern: flat` + `unit: per_person` + `min_billable_pax: N` |

**Files:**
- Create: `pricing/patterns.py`
- Test: `tests/test_patterns.py`

**Interfaces:**
- Consumes: `pricing.money.round_money`.
- Produces:
  - `pricing.patterns.PricingRequest` — frozen dataclass `pax: int`, `date: datetime.date | None = None`, `day_part: str | None = None`.
  - `pricing.patterns.PricingResult` — frozen dataclass `total: Decimal`, `currency: str`, `breakdown: list[str]`.
  - `pricing.patterns.NeedsQuote(Exception)` with attribute `reason: str`.
  - `pricing.patterns.evaluate(item: dict, rates: Mapping[str, Decimal], request: PricingRequest) -> PricingResult`

`item` is a catalog entry dict. `rates` maps cell-reference strings to already-resolved `Decimal` values — this module never touches Excel.

**Evaluation order (fixed, and asserted by tests):**
1. Blackout check → `NeedsQuote`.
2. Select the base unit rate from the pattern.
3. Apply `add_per_unit` modifiers to the unit rate.
4. Compute units: `per_group` → 1; `per_person` → `max(pax, min_billable_pax or 0)`.
5. `subtotal = unit_rate * units`.
6. Apply `add_per_booking` modifiers.
7. Apply `multiply` modifiers.
8. Round once, `ROUND_HALF_UP`, 2dp.

- [ ] **Step 1: Write the failing test**

Create `tests/test_patterns.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from pricing.patterns import NeedsQuote, PricingRequest, evaluate

UFFIZI = {
    "id": "IT-FLR-0032",
    "currency": "EUR",
    "unit": "per_person",
    "pricing": {
        "pattern": "tiered_by_pax",
        "tiers": [
            {"max_pax": 4, "cell": "Italy!D4"},
            {"max_pax": 10, "cell": "Italy!D5"},
        ],
    },
    "modifiers": [
        {"type": "day_part", "when": ["PM"], "op": "add_per_unit", "cell": "Italy!F4"}
    ],
}

RATES = {"Italy!D4": Decimal("285"), "Italy!D5": Decimal("240"), "Italy!F4": Decimal("40")}


def test_tiered_picks_the_right_bracket():
    result = evaluate(UFFIZI, RATES, PricingRequest(pax=4, day_part="AM"))
    assert result.total == Decimal("1140.00")
    assert result.currency == "EUR"


def test_higher_pax_uses_the_cheaper_tier():
    result = evaluate(UFFIZI, RATES, PricingRequest(pax=6, day_part="AM"))
    assert result.total == Decimal("1440.00")


def test_day_part_supplement_is_per_person():
    result = evaluate(UFFIZI, RATES, PricingRequest(pax=4, day_part="PM"))
    assert result.total == Decimal("1300.00")  # (285 + 40) * 4


def test_pax_above_top_tier_needs_a_quote():
    with pytest.raises(NeedsQuote) as exc:
        evaluate(UFFIZI, RATES, PricingRequest(pax=14, day_part="AM"))
    assert "14" in exc.value.reason and "10" in exc.value.reason


def test_missing_day_part_needs_a_quote_when_a_supplement_exists():
    with pytest.raises(NeedsQuote) as exc:
        evaluate(UFFIZI, RATES, PricingRequest(pax=4, day_part=None))
    assert "time of day" in exc.value.reason.lower()


def test_per_group_does_not_multiply_by_pax():
    transfer = {
        "currency": "EUR",
        "unit": "per_group",
        "pricing": {"pattern": "flat", "cell": "Italy!D7"},
        "modifiers": [],
    }
    result = evaluate(transfer, {"Italy!D7": Decimal("110")}, PricingRequest(pax=3))
    assert result.total == Decimal("110.00")


def test_minimum_billable_pax_raises_the_floor():
    class_ = {
        "currency": "EUR",
        "unit": "per_person",
        "min_billable_pax": 6,
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [],
    }
    result = evaluate(class_, {"X!A1": Decimal("50")}, PricingRequest(pax=2))
    assert result.total == Decimal("300.00")  # billed for 6, not 2


def test_blackout_date_needs_a_quote():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [{"type": "blackout", "dates": ["2026-12-25"]}],
    }
    with pytest.raises(NeedsQuote) as exc:
        evaluate(item, {"X!A1": Decimal("50")},
                 PricingRequest(pax=2, date=date(2026, 12, 25)))
    assert "blackout" in exc.value.reason.lower()


def test_weekend_multiplier_applies_to_subtotal():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [
            {"type": "day_of_week", "when": ["SAT", "SUN"], "op": "multiply", "factor": "1.15"}
        ],
    }
    saturday = date(2026, 6, 20)
    result = evaluate(item, {"X!A1": Decimal("100")}, PricingRequest(pax=2, date=saturday))
    assert result.total == Decimal("230.00")


def test_seasonal_modifier_needs_a_date():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [
            {"type": "seasonal", "from": "2026-06-01", "to": "2026-08-31",
             "op": "add_per_unit", "cell": "X!B1"}
        ],
    }
    with pytest.raises(NeedsQuote) as exc:
        evaluate(item, {"X!A1": Decimal("100"), "X!B1": Decimal("20")},
                 PricingRequest(pax=2, date=None))
    assert "date" in exc.value.reason.lower()


def test_breakdown_explains_the_arithmetic():
    result = evaluate(UFFIZI, RATES, PricingRequest(pax=4, day_part="PM"))
    joined = " ".join(result.breakdown)
    assert "285" in joined and "40" in joined and "4" in joined


def test_rounding_happens_once_at_the_end():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [
            {"type": "day_of_week", "when": ["MON"], "op": "multiply", "factor": "1.005"}
        ],
    }
    monday = date(2026, 6, 15)
    # 33.33 * 3 = 99.99 -> * 1.005 = 100.48995 -> 100.49
    result = evaluate(item, {"X!A1": Decimal("33.33")}, PricingRequest(pax=3, date=monday))
    assert result.total == Decimal("100.49")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_patterns.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.patterns'`

- [ ] **Step 3: Write the implementation**

Create `pricing/patterns.py`:

```python
"""Pricing semantics. Pure functions — no Excel, no filesystem, no network.

Rates arrive already resolved as Decimals keyed by cell reference, so this
module can be tested exhaustively with no fixtures.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from pricing.money import round_money

DAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class NeedsQuote(Exception):
    """This booking cannot be priced from what is mapped. Never guess."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PricingRequest:
    pax: int
    date: Date | None = None
    day_part: str | None = None


@dataclass(frozen=True)
class PricingResult:
    total: Decimal
    currency: str
    breakdown: list[str] = field(default_factory=list)


def evaluate(item: dict, rates: Mapping[str, Decimal], request: PricingRequest) -> PricingResult:
    modifiers = item.get("modifiers") or []
    _check_blackout(modifiers, request)

    unit_rate, lines = _base_rate(item, rates, request)
    applicable = [m for m in modifiers if _applies(m, request)]

    for mod in _with_op(applicable, "add_per_unit"):
        amount = _amount(mod, rates)
        unit_rate += amount
        lines.append(f"+ {amount} per person ({mod['type']})")

    units = _units(item, request)
    subtotal = unit_rate * units
    lines.append(f"= {unit_rate} x {units} = {subtotal}")

    for mod in _with_op(applicable, "add_per_booking"):
        amount = _amount(mod, rates)
        subtotal += amount
        lines.append(f"+ {amount} per booking ({mod['type']})")

    for mod in _with_op(applicable, "multiply"):
        factor = _amount(mod, rates)
        subtotal *= factor
        lines.append(f"x {factor} ({mod['type']})")

    return PricingResult(round_money(subtotal), item["currency"], lines)


def _base_rate(item: dict, rates: Mapping[str, Decimal],
               request: PricingRequest) -> tuple[Decimal, list[str]]:
    pricing = item["pricing"]
    pattern = pricing["pattern"]

    if pattern == "flat":
        rate = _lookup(rates, pricing["cell"])
        return rate, [f"base {rate} ({pricing['cell']})"]

    if pattern == "tiered_by_pax":
        tiers = sorted(pricing["tiers"], key=lambda t: t["max_pax"])
        for tier in tiers:
            if request.pax <= tier["max_pax"]:
                rate = _lookup(rates, tier["cell"])
                return rate, [f"base {rate} (tier <= {tier['max_pax']} pax, {tier['cell']})"]
        ceiling = tiers[-1]["max_pax"]
        raise NeedsQuote(
            f"{request.pax} pax is above the highest mapped tier ({ceiling} pax). "
            "Ask the supplier for a group rate."
        )

    raise NeedsQuote(f"unknown pricing pattern {pattern!r}")


def _units(item: dict, request: PricingRequest) -> int:
    if item["unit"] == "per_group":
        return 1
    return max(request.pax, item.get("min_billable_pax") or 0)


def _check_blackout(modifiers: list[dict], request: PricingRequest) -> None:
    blackouts = [m for m in modifiers if m["type"] == "blackout"]
    if not blackouts:
        return
    if request.date is None:
        raise NeedsQuote("This experience has blackout dates but no date was given.")
    for mod in blackouts:
        if request.date.isoformat() in mod.get("dates", []):
            raise NeedsQuote(
                f"{request.date.isoformat()} is a blackout date for this experience."
            )


def _applies(mod: dict, request: PricingRequest) -> bool:
    kind = mod["type"]

    if kind == "blackout":
        return False

    if kind == "day_part":
        if request.day_part is None:
            raise NeedsQuote(
                "This experience is priced by time of day, but the itinerary "
                "does not say whether it is AM or PM."
            )
        return request.day_part.upper() in [w.upper() for w in mod["when"]]

    if kind == "day_of_week":
        if request.date is None:
            raise NeedsQuote(
                "This experience is priced by day of week, but the itinerary "
                "line has no date."
            )
        return DAY_NAMES[request.date.weekday()] in [w.upper() for w in mod["when"]]

    if kind == "seasonal":
        if request.date is None:
            raise NeedsQuote(
                "This experience has seasonal rates, but the itinerary line has no date."
            )
        start = datetime.fromisoformat(mod["from"]).date()
        end = datetime.fromisoformat(mod["to"]).date()
        return start <= request.date <= end

    raise NeedsQuote(f"unknown modifier type {kind!r}")


def _with_op(modifiers: list[dict], op: str) -> list[dict]:
    return [m for m in modifiers if m.get("op") == op]


def _amount(mod: dict, rates: Mapping[str, Decimal]) -> Decimal:
    if "factor" in mod:
        return Decimal(str(mod["factor"]))
    return _lookup(rates, mod["cell"])


def _lookup(rates: Mapping[str, Decimal], cell: str) -> Decimal:
    try:
        return rates[cell]
    except KeyError:
        raise NeedsQuote(f"no rate available for {cell}") from None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_patterns.py -v`
Expected: PASS, 12 passed

- [ ] **Step 5: Commit**

```bash
git add pricing/patterns.py tests/test_patterns.py
git commit -m "feat: pricing pattern evaluation with never-extrapolate semantics"
```

---

### Task 6: Rate sheet profiling and redaction

**Files:**
- Create: `pricing/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: `pricing.workbook.Workbook`, `pricing.money.parse_money`.
- Produces:
  - `pricing.profile.ColumnProfile` — dataclass `letter: str`, `header: str | None`, `fill_rate: float`, `distinct_count: int`, `kind: str`, `price_bearing: bool`, `sample_values: list[str]`.
  - `pricing.profile.SheetProfile` — dataclass `name: str`, `max_row: int`, `max_column: int`, `header_row: int | None`, `merged_ranges: list[str]`, `formula_cells: int`, `data_blocks: list[list[int]]`, `columns: list[ColumnProfile]`.
  - `pricing.profile.profile_sheet(wb: Workbook, sheet: str) -> SheetProfile`
  - `pricing.profile.profile_workbook(wb: Workbook) -> list[SheetProfile]`
  - `pricing.profile.to_dict(profiles: list[SheetProfile]) -> dict`

**Redaction rule — REVISED after four failed fix rounds. The reasoning IS the requirement.**

The original rule classified header text and cell values as confidential-or-not. That is
adversarial classification over content derived from a confidential document, and it failed
four consecutive rounds while passing a green suite each time: count-word substrings
(`Beverage` contains `age`), hyphenated price ranges, currency spellings nobody enumerated,
headers pairing a counting word with an unrelated price (`Adult 45`), and finally
`sample_values` itself — a `1-4 Pax` column holding `250, 480` published the real
per-person rates, because the header named a count and the values were integers under 1000.

**The serialized profile now carries nothing derived from cell contents.** `to_dict()` emits
structure only — per sheet `name`, `max_row`, `max_column`, `header_row`,
`header_row_candidates`, `merged_ranges`, `formula_cells`, `data_blocks`; per column
`letter`, `fill_rate`, `distinct_count`, `kind`, `price_bearing`. No header text, no sample
values, and the masking machinery is deleted rather than disabled — dead code here is an
invitation to re-enable the leak.

`ColumnProfile.header` and `ColumnProfile.sample_values` REMAIN as in-memory fields, read
locally during `/profile` and `/map`. Only the written artifact is stripped, because only
the written artifact travels.

The guarantee is now structural, not heuristic: there is no classifier to fool, because no
cell content reaches the file. The operator may still choose to paste a specific header to
whoever supports her — her decision, case by case, rather than a default.

**The test that enforces it** — not a list of known secrets, but every cell of every fixture:

```python
def test_serialized_profile_contains_no_cell_content(rate_sheet, wide_rate_sheet,
                                                     stacked_rate_sheet, nasty_sheet,
                                                     multiheader_sheet):
    import json, openpyxl
    for path in [rate_sheet, wide_rate_sheet, stacked_rate_sheet,
                 nasty_sheet, multiheader_sheet]:
        blob = json.dumps(to_dict(profile_workbook(Workbook(path))))
        raw = openpyxl.load_workbook(path)
        for sheet in raw.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    text = str(cell.value).strip() if cell.value is not None else ""
                    if len(text) >= 2:
                        assert text not in blob, (
                            f"{path.name}!{sheet.title}!{cell.coordinate} "
                            f"leaked {text!r} into the shareable profile")
```

- [ ] **Step 1: Write the failing test**

Create `tests/test_profile.py`:

```python
import json

from pricing.profile import profile_sheet, profile_workbook, to_dict
from pricing.workbook import Workbook


def test_finds_the_header_row_below_a_title_block(rate_sheet):
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    assert profile.header_row == 3


def test_captures_headers_verbatim(rate_sheet):
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    headers = [c.header for c in profile.columns]
    assert "Experience" in headers
    assert "Net Rate" in headers
    assert "PM Supplement" in headers


def test_low_cardinality_columns_expose_their_values(rate_sheet):
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    unit_col = next(c for c in profile.columns if c.header == "Unit")
    assert sorted(unit_col.sample_values) == ["per group", "per person"]


def test_rate_columns_are_marked_price_bearing(rate_sheet):
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    by_header = {c.header: c for c in profile.columns}
    assert by_header["Net Rate"].price_bearing is True
    assert by_header["PM Supplement"].price_bearing is True
    assert by_header["Min Pax"].price_bearing is False
    assert by_header["Experience"].price_bearing is False


def test_profile_json_contains_no_rate_values(rate_sheet):
    """The promise that she can safely send this file to a developer."""
    wb = Workbook(rate_sheet)
    blob = json.dumps(to_dict(profile_workbook(wb)))
    for secret in ["285", "240", "110", "95", "165", "40"]:
        assert secret not in blob, f"leaked rate {secret}"


def test_pax_counts_are_not_redacted(rate_sheet):
    """Over-redaction would make the profile useless. Counts must survive."""
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    min_pax = next(c for c in profile.columns if c.header == "Min Pax")
    assert min_pax.sample_values  # non-empty


def test_reports_merged_ranges_and_dimensions(rate_sheet):
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    assert "A1:F1" in profile.merged_ranges
    assert profile.max_row == 7


def test_blank_row_splits_data_blocks(nasty_sheet):
    wb = Workbook(nasty_sheet)
    profile = profile_sheet(wb, "Odd")
    assert profile.data_blocks == [[3, 4], [6, 6]]


def test_profiles_every_sheet(rate_sheet):
    wb = Workbook(rate_sheet)
    assert [p.name for p in profile_workbook(wb)] == ["Italy", "Greece"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.profile'`

- [ ] **Step 3: Write the implementation**

Create `pricing/profile.py`:

```python
"""Phase 0: describe the shape of a rate sheet without disclosing its rates.

The output of this module is the one artefact the operator can safely send
to a developer, so redaction is conservative: anything numeric that is not
demonstrably a count is treated as a price and masked.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl.utils import get_column_letter

from pricing.money import MoneyParseError, parse_money
from pricing.workbook import CellRef, Workbook

MONEY_WORDS = ("rate", "price", "cost", "net", "supplement", "fee",
               "charge", "eur", "usd", "gbp", "$", "€", "£")
COUNT_WORDS = ("pax", "qty", "quantity", "min", "max", "count", "number",
               "days", "nights", "hours", "duration", "year", "age")

MAX_SAMPLES = 12


@dataclass
class ColumnProfile:
    letter: str
    header: str | None
    fill_rate: float
    distinct_count: int
    kind: str
    price_bearing: bool
    sample_values: list[str] = field(default_factory=list)


@dataclass
class SheetProfile:
    name: str
    max_row: int
    max_column: int
    header_row: int | None
    merged_ranges: list[str]
    formula_cells: int
    data_blocks: list[list[int]]
    columns: list[ColumnProfile]


def profile_workbook(wb: Workbook) -> list[SheetProfile]:
    return [profile_sheet(wb, name) for name in wb.sheet_names()]


def profile_sheet(wb: Workbook, sheet: str) -> SheetProfile:
    max_row, max_col = wb.dimensions(sheet)
    header_row = _find_header_row(wb, sheet, max_row, max_col)
    first_data = (header_row + 1) if header_row else 1

    columns = [
        _profile_column(wb, sheet, col, header_row, first_data, max_row)
        for col in range(1, max_col + 1)
    ]

    return SheetProfile(
        name=sheet,
        max_row=max_row,
        max_column=max_col,
        header_row=header_row,
        merged_ranges=wb.merged_ranges(sheet),
        formula_cells=_count_formulas(wb, sheet, max_row, max_col),
        data_blocks=_data_blocks(wb, sheet, first_data, max_row),
        columns=columns,
    )


def _find_header_row(wb: Workbook, sheet: str, max_row: int, max_col: int) -> int | None:
    """The first row with 3+ non-empty text cells that has data beneath it."""
    for row in range(1, min(max_row, 20) + 1):
        values = wb.read_row(sheet, row)
        texts = [v for v in values if isinstance(v, str) and v.strip()]
        if len(texts) >= 3 and row < max_row:
            return row
    return None


def _profile_column(wb: Workbook, sheet: str, col: int, header_row: int | None,
                    first_data: int, max_row: int) -> ColumnProfile:
    letter = get_column_letter(col)
    header = None
    if header_row:
        raw = wb.read(CellRef(sheet, letter, header_row))
        header = str(raw).strip() if raw is not None else None

    values = [
        wb.read(CellRef(sheet, letter, row))
        for row in range(first_data, max_row + 1)
    ]
    present = [v for v in values if v is not None and str(v).strip() != ""]
    fill_rate = round(len(present) / len(values), 3) if values else 0.0
    distinct = {str(v) for v in present}
    kind = _classify(present)
    price = _is_price_bearing(header, kind, present)

    samples: list[str] = []
    if not price and 0 < len(distinct) <= MAX_SAMPLES:
        samples = sorted(distinct)

    return ColumnProfile(
        letter=letter,
        header=header,
        fill_rate=fill_rate,
        distinct_count=len(distinct),
        kind=kind,
        price_bearing=price,
        sample_values=samples,
    )


def _classify(values: list[object]) -> str:
    if not values:
        return "empty"
    kinds = set()
    for value in values:
        if isinstance(value, (date, datetime)):
            kinds.add("date")
        elif isinstance(value, (int, float)):
            kinds.add("numeric")
        else:
            try:
                parse_money(value)
                kinds.add("numeric")
            except MoneyParseError:
                kinds.add("text")
    if len(kinds) == 1:
        return kinds.pop()
    return "mixed"


def _is_price_bearing(header: str | None, kind: str, values: list[object]) -> bool:
    lowered = (header or "").lower()
    if any(word in lowered for word in MONEY_WORDS):
        return True
    if any(word in lowered for word in COUNT_WORDS):
        return False
    # Unlabelled or ambiguous numeric data is assumed to be money.
    return kind in ("numeric", "mixed") and bool(values)


def _count_formulas(wb: Workbook, sheet: str, max_row: int, max_col: int) -> int:
    total = 0
    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            if wb.is_formula(CellRef(sheet, get_column_letter(col), row)):
                total += 1
    return total


def _data_blocks(wb: Workbook, sheet: str, first_data: int, max_row: int) -> list[list[int]]:
    """Contiguous runs of rows whose first column is populated."""
    blocks: list[list[int]] = []
    start: int | None = None
    for row in range(first_data, max_row + 1):
        value = wb.read(CellRef(sheet, "A", row))
        populated = value is not None and str(value).strip() != ""
        if populated and start is None:
            start = row
        elif not populated and start is not None:
            blocks.append([start, row - 1])
            start = None
    if start is not None:
        blocks.append([start, max_row])
    return blocks


def to_dict(profiles: list[SheetProfile]) -> dict:
    return {"sheets": [dataclasses.asdict(p) for p in profiles]}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_profile.py -v`
Expected: PASS, 9 passed

If `test_profile_json_contains_no_rate_values` fails, **do not relax the test.** Tighten
`_is_price_bearing` until it passes. That test is the entire basis for telling the
operator her profile is safe to share.

- [ ] **Step 5: Commit**

```bash
git add pricing/profile.py tests/test_profile.py
git commit -m "feat: rate sheet structural profiling with conservative redaction"
```

---

### Task 7: Itinerary template profiling

**Files:**
- Create: `pricing/itinerary_profile.py`
- Test: `tests/test_itinerary_profile.py`

**Interfaces:**
- Consumes: `pricing.workbook.Workbook`, `pricing.profile._find_header_row` (re-exported as `pricing.profile.find_header_row` — rename it in `profile.py` and update its internal call sites).
- Produces:
  - `pricing.itinerary_profile.ItineraryTemplate` — dataclass `sheet: str`, `header_row: int`, `first_data_row: int`, `roles: dict[str, str]` mapping role name to column letter. Roles: `name`, `date`, `pax`, `day_part`, `cost`.
  - `pricing.itinerary_profile.propose_template(wb: Workbook, sheet: str) -> ItineraryTemplate`
  - `pricing.itinerary_profile.save_template(t: ItineraryTemplate, path: Path) -> None`
  - `pricing.itinerary_profile.load_template(path: Path) -> ItineraryTemplate`
  - `pricing.itinerary_profile.MissingRoleError(Exception)` with attribute `missing: list[str]`

`propose_template` guesses; the operator confirms in Phase 0.5. `name` and `cost` are
required — if either cannot be found, raise `MissingRoleError` so the skill asks her
directly rather than guessing wrong.

- [ ] **Step 1: Rename the header finder for reuse**

In `pricing/profile.py`, rename `_find_header_row` to `find_header_row` and update the one
call site inside `profile_sheet`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_itinerary_profile.py`:

```python
import pytest

from pricing.itinerary_profile import (
    MissingRoleError,
    load_template,
    propose_template,
    save_template,
)
from pricing.workbook import Workbook


def test_finds_the_line_item_header_below_the_title_block(itinerary):
    wb = Workbook(itinerary)
    template = propose_template(wb, "Itinerary")
    assert template.header_row == 7
    assert template.first_data_row == 8


def test_maps_every_role_to_a_column(itinerary):
    wb = Workbook(itinerary)
    template = propose_template(wb, "Itinerary")
    assert template.roles == {
        "name": "A",
        "date": "B",
        "pax": "C",
        "day_part": "D",
        "cost": "E",
    }


def test_missing_cost_column_is_an_error_not_a_guess(itinerary, tmp_path):
    import openpyxl

    wb_raw = openpyxl.load_workbook(itinerary)
    wb_raw["Itinerary"]["E7"] = "Notes"
    stripped = tmp_path / "no_cost.xlsx"
    wb_raw.save(stripped)

    with pytest.raises(MissingRoleError) as exc:
        propose_template(Workbook(stripped), "Itinerary")
    assert "cost" in exc.value.missing


def test_template_roundtrips_through_json(itinerary, tmp_path):
    wb = Workbook(itinerary)
    template = propose_template(wb, "Itinerary")
    path = tmp_path / "template.json"
    save_template(template, path)
    assert load_template(path) == template
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_itinerary_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.itinerary_profile'`

- [ ] **Step 4: Write the implementation**

Create `pricing/itinerary_profile.py`:

```python
"""Phase 0 for the itinerary side: where do line items live, and which
column is the empty one we fill in?

Guesses are proposals only. The operator confirms them once, and the
confirmed template is what makes Phase 2 deterministic.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from openpyxl.utils import get_column_letter

from pricing.profile import find_header_row
from pricing.workbook import CellRef, Workbook

ROLE_WORDS: dict[str, tuple[str, ...]] = {
    "name": ("experience", "service", "item", "activity", "description", "tour"),
    "date": ("date", "day"),
    "pax": ("pax", "guests", "people", "persons", "qty", "quantity", "adults"),
    "day_part": ("time", "am/pm", "when", "departure", "slot"),
    "cost": ("cost", "net", "price", "rate", "amount", "total"),
}

REQUIRED_ROLES = ("name", "cost")


class MissingRoleError(Exception):
    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            "Could not find these columns in the itinerary: " + ", ".join(missing)
        )
        self.missing = missing


@dataclass
class ItineraryTemplate:
    sheet: str
    header_row: int
    first_data_row: int
    roles: dict[str, str]


def propose_template(wb: Workbook, sheet: str) -> ItineraryTemplate:
    max_row, max_col = wb.dimensions(sheet)
    header_row = find_header_row(wb, sheet, max_row, max_col)
    if header_row is None:
        raise MissingRoleError(list(REQUIRED_ROLES))

    headers = {
        get_column_letter(col): str(wb.read(CellRef(sheet, get_column_letter(col), header_row)) or "")
        for col in range(1, max_col + 1)
    }

    roles: dict[str, str] = {}
    for role, words in ROLE_WORDS.items():
        for letter, header in headers.items():
            lowered = header.strip().lower()
            if lowered and any(word in lowered for word in words) and letter not in roles.values():
                roles[role] = letter
                break

    missing = [r for r in REQUIRED_ROLES if r not in roles]
    if missing:
        raise MissingRoleError(missing)

    return ItineraryTemplate(sheet, header_row, header_row + 1, roles)


def save_template(template: ItineraryTemplate, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(template), indent=2), encoding="utf-8")


def load_template(path: Path) -> ItineraryTemplate:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return ItineraryTemplate(**data)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_itinerary_profile.py tests/test_profile.py -v`
Expected: PASS, 13 passed

- [ ] **Step 6: Commit**

```bash
git add pricing/ tests/
git commit -m "feat: itinerary template profiling with required-role validation"
```

---

### Task 7b: Layout variant coverage

Task 2 built five costing layouts and four itinerary layouts. Tasks 6 and 7 were written
against the baseline. This task runs them against **every** variant and fixes what breaks.

**The multiheader sheet and the wide itinerary are expected to defeat the heuristics.**
That is not a bug to code around — it is the case the design already answers by having the
operator confirm. So the fix is to make both proposers **report their uncertainty** instead
of silently returning one guess.

**Files:**
- Modify: `pricing/profile.py` (add `header_row_candidates` to `SheetProfile`; add `find_header_candidates`)
- Modify: `pricing/itinerary_profile.py` (add `confidence`, `alternatives`, `default_pax` to `ItineraryTemplate`)
- Test: `tests/test_profile_variants.py`
- Test: `tests/test_itinerary_variants.py`

**Interfaces:**
- Consumes: everything from Tasks 6 and 7.
- Produces:
  - `pricing.profile.find_header_candidates(wb, sheet, max_row, max_col) -> list[int]` — every plausible header row, best first. `find_header_row` returns `candidates[0]` or `None`.
  - `SheetProfile.header_row_candidates: list[int]` — new field, populated by `profile_sheet`.
  - NOTE: pax-band detection and any other header-text reasoning must read headers LIVE
    from the `Workbook`, or from `ColumnProfile.header` in memory — never from the
    serialized profile, which no longer carries header text by design.
  - `ItineraryTemplate.confidence: str` — `"high"` when every role was found by header match, `"low"` when a required role was inferred or a role is missing.
  - `ItineraryTemplate.alternatives: dict[str, list[str]]` — other columns that plausibly fill each role, for the skill to offer.
  - `ItineraryTemplate.default_pax: int | None` — used when there is no pax column; set by the operator in Phase 0.5.

`ItineraryTemplate` gains fields with defaults, so `load_template` keeps working on
templates written before this task.

- [ ] **Step 1: Write the failing profile-variant test**

Create `tests/test_profile_variants.py`:

```python
import json

from pricing.profile import find_header_candidates, profile_sheet, profile_workbook, to_dict
from pricing.workbook import Workbook


def test_wide_sheet_headers_are_captured_verbatim(wide_rate_sheet):
    profile = profile_sheet(Workbook(wide_rate_sheet), "Japan")
    headers = [c.header for c in profile.columns]
    assert "1-4 Pax" in headers and "5-10 Pax" in headers and "11+ Pax" in headers


def test_wide_sheet_pax_band_columns_are_price_bearing(wide_rate_sheet):
    """'1-4 Pax' holds money despite the word 'Pax' in its header."""
    profile = profile_sheet(Workbook(wide_rate_sheet), "Japan")
    band = next(c for c in profile.columns if c.header == "1-4 Pax")
    assert band.price_bearing is True


def test_stacked_sheet_exposes_season_and_currency_values(stacked_rate_sheet):
    profile = profile_sheet(Workbook(stacked_rate_sheet), "SouthAfrica")
    by_header = {c.header: c for c in profile.columns}
    assert sorted(by_header["Season"].sample_values) == ["All Year", "Green", "Peak"]
    assert by_header["Currency"].sample_values == ["USD"]


def test_multiheader_offers_both_candidate_rows(multiheader_sheet):
    """Adversarial: row 3 is a category band, row 4 is the real header."""
    wb = Workbook(multiheader_sheet)
    max_row, max_col = wb.dimensions("Portugal")
    candidates = find_header_candidates(wb, "Portugal", max_row, max_col)
    assert 3 in candidates and 4 in candidates


def test_multiheader_profile_records_the_candidates(multiheader_sheet):
    profile = profile_sheet(Workbook(multiheader_sheet), "Portugal")
    assert len(profile.header_row_candidates) >= 2


def test_no_variant_leaks_a_rate(rate_sheet, wide_rate_sheet, stacked_rate_sheet,
                                 multiheader_sheet, nasty_sheet):
    """The safe-to-share promise must hold for every layout, not just one."""
    secrets = {
        rate_sheet: ["285", "240", "110", "95", "165", "40"],
        wide_rate_sheet: ["120", "95", "80", "140", "85", "70", "60", "15"],
        stacked_rate_sheet: ["180", "240", "310"],
        multiheader_sheet: ["210", "175", "195", "160", "25"],
        nasty_sheet: ["285", "1234", "1.234,50"],
    }
    for path, values in secrets.items():
        blob = json.dumps(to_dict(profile_workbook(Workbook(path))))
        for secret in values:
            assert secret not in blob, f"{path.name} leaked {secret}"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run --extra dev pytest tests/test_profile_variants.py -v`
Expected: FAIL — `find_header_candidates` does not exist.

Two of these will likely still fail after the import is satisfied:
`test_wide_sheet_pax_band_columns_are_price_bearing` (because `Pax` is in `COUNT_WORDS`)
and `test_no_variant_leaks_a_rate`. **Both are real leaks.** Fix the classifier, not the test.

- [ ] **Step 3: Fix the profiler**

In `pricing/profile.py`:

Add `header_row_candidates: list[int]` to `SheetProfile` (default `field(default_factory=list)`),
and populate it in `profile_sheet` from the new function.

Replace `find_header_row` with a candidates-based pair:

```python
def find_header_candidates(wb: Workbook, sheet: str, max_row: int, max_col: int) -> list[int]:
    """Every row that could plausibly be the header, best first.

    Merged category bands above the real header ('Group Size Pricing')
    look like headers too. Rather than pick one and be silently wrong, we
    return all of them and let the operator confirm.
    """
    scored: list[tuple[int, int]] = []
    merged_rows = {int(str(rng).split(":")[0][1:]) for rng in wb.merged_ranges(sheet)}

    for row in range(1, min(max_row, 20) + 1):
        values = wb.read_row(sheet, row)
        texts = [v for v in values if isinstance(v, str) and v.strip()]
        if len(texts) < 3 or row >= max_row:
            continue
        score = len(texts)
        if row in merged_rows:
            score -= 2          # a merged band is more likely a category label
        below = wb.read_row(sheet, row + 1)
        if any(isinstance(v, (int, float)) for v in below):
            score += 2          # real headers sit directly above data
        scored.append((score, row))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [row for _, row in scored]


def find_header_row(wb: Workbook, sheet: str, max_row: int, max_col: int) -> int | None:
    candidates = find_header_candidates(wb, sheet, max_row, max_col)
    return candidates[0] if candidates else None
```

Then fix the redaction classifier. `COUNT_WORDS` currently matches `1-4 Pax`, which holds
money. Money words must win over count words:

```python
def _is_price_bearing(header: str | None, kind: str, values: list[object]) -> bool:
    lowered = (header or "").lower()
    if any(word in lowered for word in MONEY_WORDS):
        return True
    # A pax *band* ('1-4 Pax', '5-10 Pax') is a price column whose header
    # happens to name a count. A range in the header means money.
    if _looks_like_a_band(lowered) and kind in ("numeric", "mixed"):
        return True
    if any(word in lowered for word in COUNT_WORDS):
        return False
    return kind in ("numeric", "mixed") and bool(values)


def _looks_like_a_band(header: str) -> bool:
    return bool(re.search(r"\d\s*[-–+]\s*\d|\d\s*\+", header))
```

- [ ] **Step 4: Run the profile-variant tests**

Run: `uv run --extra dev pytest tests/test_profile_variants.py tests/test_profile.py -v`
Expected: PASS, all tests. `test_pax_counts_are_not_redacted` from Task 6 must still pass —
plain `Min Pax` stays visible, only *bands* are treated as money.

- [ ] **Step 5: Write the failing itinerary-variant test**

Create `tests/test_itinerary_variants.py`:

```python
import pytest

from pricing.itinerary_profile import MissingRoleError, propose_template
from pricing.workbook import Workbook


def test_baseline_is_high_confidence(itinerary):
    template = propose_template(Workbook(itinerary), "Itinerary")
    assert template.confidence == "high"
    assert template.roles["cost"] == "E"


def test_day_grouped_itinerary_finds_the_same_roles(day_grouped_itinerary):
    template = propose_template(Workbook(day_grouped_itinerary), "Itinerary")
    assert template.header_row == 5
    assert template.first_data_row == 6
    assert template.roles["pax"] == "C"


def test_minimal_itinerary_has_no_date_or_time_role(minimal_itinerary):
    template = propose_template(Workbook(minimal_itinerary), "Itinerary")
    assert template.roles["name"] == "A"
    assert template.roles["cost"] == "C"
    assert "date" not in template.roles
    assert "day_part" not in template.roles


def test_wide_itinerary_has_no_pax_column_and_says_so(wide_itinerary):
    """Adversarial: pax is stated once in a header cell, not per row."""
    template = propose_template(Workbook(wide_itinerary), "Itinerary")
    assert "pax" not in template.roles
    assert template.confidence == "low"
    assert template.default_pax is None       # the operator supplies it


def test_alternatives_are_offered_for_ambiguous_roles(itinerary):
    template = propose_template(Workbook(itinerary), "Itinerary")
    assert isinstance(template.alternatives, dict)


def test_missing_cost_column_is_still_an_error(itinerary, tmp_path):
    import openpyxl

    raw = openpyxl.load_workbook(itinerary)
    raw["Itinerary"]["E7"] = "Notes"
    stripped = tmp_path / "no_cost.xlsx"
    raw.save(stripped)

    with pytest.raises(MissingRoleError) as exc:
        propose_template(Workbook(stripped), "Itinerary")
    assert "cost" in exc.value.missing
```

- [ ] **Step 6: Extend `ItineraryTemplate`**

In `pricing/itinerary_profile.py`, add three fields with defaults so existing saved
templates still load:

```python
@dataclass
class ItineraryTemplate:
    sheet: str
    header_row: int
    first_data_row: int
    roles: dict[str, str]
    confidence: str = "high"
    alternatives: dict[str, list[str]] = field(default_factory=dict)
    default_pax: int | None = None
```

In `propose_template`, after building `roles`:

```python
    alternatives = {
        role: [letter for letter, header in headers.items()
               if header.strip().lower()
               and any(word in header.strip().lower() for word in words)
               and roles.get(role) != letter]
        for role, words in ROLE_WORDS.items()
    }

    missing = [r for r in REQUIRED_ROLES if r not in roles]
    if missing:
        raise MissingRoleError(missing)

    # 'pax' is not required to find the template, but without it we cannot
    # price anything until the operator tells us the party size.
    confidence = "high" if "pax" in roles else "low"

    return ItineraryTemplate(sheet, header_row, header_row + 1, roles,
                             confidence, alternatives)
```

`load_template` needs no change — the new fields have defaults.

- [ ] **Step 7: Run everything**

Run: `uv run --extra dev pytest -v`
Expected: PASS, all tests.

- [ ] **Step 8: Commit**

```bash
git add pricing/profile.py pricing/itinerary_profile.py tests/
git commit -m "feat: report header-row candidates and template confidence across layout variants"
```

---

### Task 8: Catalog with fingerprints and live rate resolution

This task implements the spec's central decision: rates are stored as **cell references plus the value last seen**, never as copied numbers.

**Files:**
- Create: `pricing/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `pricing.workbook.Workbook`/`CellRef`, `pricing.money.parse_money`.
- Produces:
  - `pricing.catalog.CatalogItem` — dataclass with `id: str`, `name: str`, `name_cell: str`, `region: str`, `currency: str`, `unit: str`, `pricing: dict`, `modifiers: list[dict]`, `source_rows: list[int]`, `row_fingerprint: str`, `confirmed_at: str`, `min_billable_pax: int | None = None`. Method `to_dict() -> dict`, classmethod `from_dict(d) -> CatalogItem`.
  - `pricing.catalog.Catalog` — `Catalog.load(path) -> Catalog`, `.save(path)`, `.upsert(item)`, `.get(item_id) -> CatalogItem`, `.by_region(region) -> list[CatalogItem]`, `.items -> list[CatalogItem]`.
  - `pricing.catalog.fingerprint(text: str) -> str`
  - `pricing.catalog.PriceChange` — dataclass `cell: str`, `last_seen: Decimal`, `current: Decimal`.
  - `pricing.catalog.resolve_rates(item: CatalogItem, wb: Workbook) -> tuple[dict[str, Decimal], list[PriceChange]]`
  - `pricing.catalog.FingerprintMismatch(Exception)` with attribute `item_id: str`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_catalog.py`:

```python
from decimal import Decimal

import openpyxl
import pytest

from pricing.catalog import (
    Catalog,
    CatalogItem,
    FingerprintMismatch,
    fingerprint,
    resolve_rates,
)
from pricing.workbook import Workbook

UFFIZI = CatalogItem(
    id="IT-FLR-0032",
    name="Uffizi Gallery — Private Guided Tour",
    name_cell="Italy!A4",
    region="Italy",
    currency="EUR",
    unit="per_person",
    pricing={
        "pattern": "tiered_by_pax",
        "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"},
        ],
    },
    modifiers=[
        {"type": "day_part", "when": ["PM"], "op": "add_per_unit",
         "cell": "Italy!F4", "last_seen": "40"}
    ],
    source_rows=[4, 5],
    row_fingerprint=fingerprint("Uffizi Gallery — Private Guided Tour"),
    confirmed_at="2026-09-03",
)


def test_catalog_roundtrips(tmp_path):
    catalog = Catalog()
    catalog.upsert(UFFIZI)
    path = tmp_path / "catalog.json"
    catalog.save(path)
    assert Catalog.load(path).get("IT-FLR-0032").name == UFFIZI.name


def test_upsert_replaces_rather_than_duplicates(tmp_path):
    catalog = Catalog()
    catalog.upsert(UFFIZI)
    catalog.upsert(UFFIZI)
    assert len(catalog.items) == 1


def test_load_missing_file_gives_empty_catalog(tmp_path):
    assert Catalog.load(tmp_path / "nope.json").items == []


def test_resolves_live_rates(rate_sheet):
    rates, changes = resolve_rates(UFFIZI, Workbook(rate_sheet))
    assert rates["Italy!D4"] == Decimal("285")
    assert rates["Italy!F4"] == Decimal("40")
    assert changes == []


def test_detects_a_price_change(rate_sheet, tmp_path):
    raw = openpyxl.load_workbook(rate_sheet)
    raw["Italy"]["D4"] = 310
    changed = tmp_path / "changed.xlsx"
    raw.save(changed)

    rates, changes = resolve_rates(UFFIZI, Workbook(changed))
    assert rates["Italy!D4"] == Decimal("310")
    assert len(changes) == 1
    assert changes[0].last_seen == Decimal("285")
    assert changes[0].current == Decimal("310")


def test_shifted_rows_refuse_to_price(rate_sheet, tmp_path):
    """The silent-and-expensive failure this design exists to prevent."""
    raw = openpyxl.load_workbook(rate_sheet)
    raw["Italy"].insert_rows(4)
    raw["Italy"]["A4"] = "Colosseum — Underground Tour"
    shifted = tmp_path / "shifted.xlsx"
    raw.save(shifted)

    with pytest.raises(FingerprintMismatch) as exc:
        resolve_rates(UFFIZI, Workbook(shifted))
    assert exc.value.item_id == "IT-FLR-0032"
    assert "map" in str(exc.value).lower()


def test_fingerprint_ignores_whitespace_and_case():
    assert fingerprint("  Uffizi  Gallery ") == fingerprint("uffizi gallery")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.catalog'`

- [ ] **Step 3: Write the implementation**

Create `pricing/catalog.py`:

```python
"""The mapping table.

Every rate is stored as a cell reference plus the value last seen there.
That makes prices self-refreshing, makes price changes detectable, and —
via row fingerprints — makes structural drift loud instead of silent.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path

from pricing.money import MoneyParseError, parse_money
from pricing.workbook import CellRef, Workbook

_WHITESPACE = re.compile(r"\s+")


class FingerprintMismatch(Exception):
    def __init__(self, item_id: str, expected_name: str, cell: str, found: str) -> None:
        super().__init__(
            f"'{expected_name}' is no longer at {cell} (found '{found}'). "
            f"The sheet has changed shape — please re-run /map for this region."
        )
        self.item_id = item_id


@dataclass
class PriceChange:
    cell: str
    last_seen: Decimal
    current: Decimal


@dataclass
class CatalogItem:
    id: str
    name: str
    name_cell: str
    region: str
    currency: str
    unit: str
    pricing: dict
    modifiers: list[dict] = field(default_factory=list)
    source_rows: list[int] = field(default_factory=list)
    row_fingerprint: str = ""
    confirmed_at: str = ""
    min_billable_pax: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CatalogItem":
        return cls(**data)


class Catalog:
    def __init__(self, items: list[CatalogItem] | None = None) -> None:
        self.items: list[CatalogItem] = list(items or [])

    @classmethod
    def load(cls, path: Path) -> "Catalog":
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([CatalogItem.from_dict(d) for d in data.get("items", [])])

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "items": [i.to_dict() for i in self.items]}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def upsert(self, item: CatalogItem) -> None:
        for index, existing in enumerate(self.items):
            if existing.id == item.id:
                self.items[index] = item
                return
        self.items.append(item)

    def get(self, item_id: str) -> CatalogItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)

    def by_region(self, region: str) -> list[CatalogItem]:
        return [i for i in self.items if i.region == region]


def fingerprint(text: str) -> str:
    normalised = _WHITESPACE.sub(" ", str(text).strip().lower())
    return "sha1:" + hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:16]


def resolve_rates(item: CatalogItem, wb: Workbook) -> tuple[dict[str, Decimal], list[PriceChange]]:
    _verify_fingerprint(item, wb)

    rates: dict[str, Decimal] = {}
    changes: list[PriceChange] = []

    for cell, last_seen in _rate_cells(item):
        raw = wb.read(CellRef.parse(cell))
        try:
            current = parse_money(raw)
        except MoneyParseError:
            continue  # Left unresolved; patterns.evaluate raises NeedsQuote.
        rates[cell] = current
        if last_seen is not None and current != last_seen:
            changes.append(PriceChange(cell, last_seen, current))

    return rates, changes


def _verify_fingerprint(item: CatalogItem, wb: Workbook) -> None:
    if not item.row_fingerprint:
        return
    found = wb.read(CellRef.parse(item.name_cell))
    if fingerprint(found or "") != item.row_fingerprint:
        raise FingerprintMismatch(item.id, item.name, item.name_cell, str(found))


def _rate_cells(item: CatalogItem) -> list[tuple[str, Decimal | None]]:
    entries: list[tuple[str, Decimal | None]] = []

    pricing = item.pricing
    if pricing.get("pattern") == "flat":
        entries.append((pricing["cell"], _seen(pricing)))
    elif pricing.get("pattern") == "tiered_by_pax":
        for tier in pricing["tiers"]:
            entries.append((tier["cell"], _seen(tier)))

    for mod in item.modifiers:
        if "cell" in mod:
            entries.append((mod["cell"], _seen(mod)))

    return entries


def _seen(node: dict) -> Decimal | None:
    raw = node.get("last_seen")
    return Decimal(str(raw)) if raw is not None else None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_catalog.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add pricing/catalog.py tests/test_catalog.py
git commit -m "feat: catalog with live rate resolution, drift detection, price-change reporting"
```

---

### Task 9: Matching and the alias store

**Files:**
- Create: `pricing/match.py`
- Test: `tests/test_match.py`

**Interfaces:**
- Consumes: `pricing.catalog.CatalogItem`.
- Produces:
  - `pricing.match.normalize(text: str) -> str`
  - `pricing.match.Candidate` — dataclass `item_id: str`, `name: str`, `score: float`, `reason: str`.
  - `pricing.match.Aliases` — `Aliases.load(path)`, `.save(path)`, `.add(phrase: str, item_id: str)`, `.lookup(phrase: str) -> str | None`, `.entries -> dict`.
  - `pricing.match.candidates(query: str, items: list[CatalogItem], aliases: Aliases, limit: int = 3) -> list[Candidate]`

**REVISED after three failed fix rounds.** `Candidate` carries an `auto_accept: bool`.
It is `True` in exactly two cases: the query and the item name are IDENTICAL after
normalisation, or the query hits a saved alias. In every other case it is `False` and the
operator confirms, with the top candidate pre-selected as a single keystroke.

`score` is for ORDERING candidates only and must never gate a pricing decision. The history:
a 50/50 similarity blend auto-accepted a reversed-direction transfer at 0.900; switching to
a hard MINIMUM dropped obvious matches to 2-in-20; adding fuzzy token matching then
auto-accepted a reversed transfer at 1.000, matched `Unguided Visit` to `Guided Visit`, and
matched adjacent SKU codes. Each round fixed one side and broke the other, which is the
signature of a wrong approach rather than wrong tuning.

Normalisation folds: case, all punctuation to spaces (so `Skip-the-Line` equals
`Skip the Line`), en/em dashes, `&` to `and`, collapsed whitespace, and simple plurals
(strip a trailing `s` from tokens of 4+ characters not ending in `ss`, so `rides` equals
`ride` and `museums` equals `museum`, while `class` and `bus` are left alone).

- [ ] **Step 1: Write the failing test**

Create `tests/test_match.py`:

```python
from pricing.catalog import CatalogItem
from pricing.match import Aliases, candidates, normalize


def _item(item_id, name):
    return CatalogItem(id=item_id, name=name, name_cell="X!A1", region="R",
                       currency="EUR", unit="per_person",
                       pricing={"pattern": "flat", "cell": "X!B1"})


ITEMS = [
    _item("IT-1", "Uffizi Gallery — Private Guided Tour"),
    _item("IT-2", "Vatican Museums — Skip the Line"),
    _item("GR-1", "Catamaran Cruise — PM (beverages incl.)"),
]


def test_normalize_strips_punctuation_and_case():
    assert normalize("Sunset catamaran w/ open bar!") == "sunset catamaran w open bar"


def test_close_phrasing_ranks_first():
    result = candidates("Uffizi Gallery private tour", ITEMS, Aliases())
    assert result[0].item_id == "IT-1"
    assert result[0].score > 0.6


def test_returns_at_most_the_limit():
    assert len(candidates("tour", ITEMS, Aliases(), limit=2)) == 2


def test_distant_phrasing_scores_low_rather_than_matching_confidently():
    result = candidates("Sunset catamaran w/ open bar", ITEMS, Aliases())
    assert result[0].item_id == "GR-1"
    assert result[0].score < 0.6  # low enough that cost.py will ask


def test_alias_hit_wins_outright():
    aliases = Aliases()
    aliases.add("Sunset catamaran w/ open bar", "GR-1")
    result = candidates("sunset  catamaran W/ Open Bar", ITEMS, aliases)
    assert result[0].item_id == "GR-1"
    assert result[0].score == 1.0
    assert result[0].reason == "saved alias"


def test_aliases_roundtrip_and_count_hits(tmp_path):
    aliases = Aliases()
    aliases.add("sunset catamaran", "GR-1")
    aliases.add("sunset catamaran", "GR-1")
    path = tmp_path / "aliases.json"
    aliases.save(path)
    reloaded = Aliases.load(path)
    assert reloaded.lookup("Sunset Catamaran") == "GR-1"
    assert reloaded.entries["sunset catamaran"]["hits"] == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_match.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.match'`

- [ ] **Step 3: Write the implementation**

Create `pricing/match.py`:

```python
"""Resolving an itinerary's phrasing to a catalog item.

Scoring is deterministic so the same itinerary always produces the same
candidate ranking. Claude chooses among candidates and asks the operator
when confidence is low; it never invents an item.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from pricing.catalog import CatalogItem

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    lowered = str(text).lower()
    return _SPACE.sub(" ", _PUNCT.sub("", lowered)).strip()


@dataclass
class Candidate:
    item_id: str
    name: str
    score: float
    reason: str


class Aliases:
    def __init__(self, entries: dict | None = None) -> None:
        self.entries: dict = dict(entries or {})

    @classmethod
    def load(cls, path: Path) -> "Aliases":
        path = Path(path)
        if not path.exists():
            return cls()
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.entries, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, phrase: str, item_id: str) -> None:
        key = normalize(phrase)
        entry = self.entries.get(key)
        if entry and entry["id"] == item_id:
            entry["hits"] += 1
        else:
            self.entries[key] = {"id": item_id, "hits": 1}

    def lookup(self, phrase: str) -> str | None:
        entry = self.entries.get(normalize(phrase))
        return entry["id"] if entry else None


def candidates(query: str, items: list[CatalogItem], aliases: Aliases,
               limit: int = 3) -> list[Candidate]:
    alias_id = aliases.lookup(query)
    if alias_id:
        for item in items:
            if item.id == alias_id:
                return [Candidate(item.id, item.name, 1.0, "saved alias")]

    normalised_query = normalize(query)
    scored = [
        Candidate(
            item.id,
            item.name,
            round(_score(normalised_query, normalize(item.name)), 3),
            "name similarity",
        )
        for item in items
    ]
    scored.sort(key=lambda c: (-c.score, c.item_id))
    return scored[:limit]


def _score(a: str, b: str) -> float:
    """Blend sequence similarity with token overlap.

    Sequence similarity alone punishes reordering ('Uffizi private tour' vs
    'Uffizi — Private Guided Tour'); token overlap alone ignores word order
    entirely. Together they rank sensibly.
    """
    sequence = SequenceMatcher(None, a, b).ratio()
    tokens_a, tokens_b = set(a.split()), set(b.split())
    overlap = len(tokens_a & tokens_b) / len(tokens_a | tokens_b) if tokens_a | tokens_b else 0.0
    return (sequence + overlap) / 2
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_match.py -v`
Expected: PASS, 6 passed

If `test_distant_phrasing_scores_low_rather_than_matching_confidently` fails because the
score is too high, **do not lower the assertion.** A confidently-wrong match is worse than
a question. Adjust the blend weights until distant phrasings land below 0.6.

- [ ] **Step 5: Commit**

```bash
git add pricing/match.py tests/test_match.py
git commit -m "feat: deterministic candidate matching with a learning alias store"
```

---

### Task 10: Costing orchestration

**Files:**
- Create: `pricing/cost.py`
- Test: `tests/test_cost.py`

**Interfaces:**
- Consumes: `pricing.workbook`, `pricing.itinerary_profile.ItineraryTemplate`, `pricing.catalog`, `pricing.patterns`, `pricing.match`.
- Produces:
  - `pricing.cost.ItineraryLine` — dataclass `row: int`, `raw_name: str`, `date: datetime.date | None`, `pax: int`, `day_part: str | None`.
  - `pricing.cost.PricedLine` — dataclass `row: int`, `raw_name: str`, `item_id: str | None`, `status: str`, `total: Decimal | None`, `currency: str | None`, `reason: str | None`, `breakdown: list[str]`, `candidates: list[dict]`.
  - `pricing.cost.parse_itinerary(wb: Workbook, template: ItineraryTemplate) -> list[ItineraryLine]`
  - `pricing.cost.price_lines(lines, catalog, aliases, wb_rates, resolutions: dict[int, str] | None = None) -> tuple[list[PricedLine], list[PriceChange]]`

`status` is one of `priced`, `needs_quote`, `unmatched`. `resolutions` maps an itinerary
row number to an item id the operator has chosen; Claude supplies it on a second pass
after asking.

**Auto-accept is NOT a score threshold — REVISED after three failed fix rounds.** A line is
taken without asking ONLY when `candidates()` returns a top candidate whose `auto_accept`
flag is `True`, which happens in exactly two cases: the names are identical after
normalisation, or the operator has confirmed that exact phrasing before (an alias hit).
Never compare `score` against a threshold — `score` exists to ORDER candidates for display,
nothing more. Three rounds of tuning a similarity threshold produced, in order, a reversed
transfer auto-accepting at 0.900, then only 2 of 20 obvious matches accepting at all, then
a reversed transfer auto-accepting at 1.000 along with `Unguided Visit` matching
`Guided Visit` and adjacent SKU codes matching each other. Lexical similarity cannot be
trusted with a pricing decision.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cost.py`:

```python
from datetime import date
from decimal import Decimal

from pricing.catalog import Catalog, CatalogItem, fingerprint
from pricing.cost import parse_itinerary, price_lines
from pricing.itinerary_profile import propose_template
from pricing.match import Aliases
from pricing.workbook import Workbook


def _catalog():
    catalog = Catalog()
    catalog.upsert(CatalogItem(
        id="IT-FLR-0032", name="Uffizi Gallery — Private Guided Tour",
        name_cell="Italy!A4", region="Italy", currency="EUR", unit="per_person",
        pricing={"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"}]},
        modifiers=[{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                    "cell": "Italy!F4", "last_seen": "40"}],
        source_rows=[4, 5],
        row_fingerprint=fingerprint("Uffizi Gallery — Private Guided Tour")))
    catalog.upsert(CatalogItem(
        id="IT-ROM-0001", name="Vatican Museums — Skip the Line",
        name_cell="Italy!A6", region="Italy", currency="EUR", unit="per_person",
        pricing={"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
        source_rows=[6], row_fingerprint=fingerprint("Vatican Museums — Skip the Line")))
    return catalog


def test_parses_lines_from_the_template(itinerary):
    wb = Workbook(itinerary)
    lines = parse_itinerary(wb, propose_template(wb, "Itinerary"))
    assert [l.row for l in lines] == [8, 9, 10]
    assert lines[0].raw_name == "Uffizi Gallery private tour"
    assert lines[0].pax == 4
    assert lines[0].date == date(2026, 6, 15)
    assert lines[0].day_part == "PM"


def test_prices_confident_matches(itinerary, rate_sheet):
    wb = Workbook(itinerary)
    lines = parse_itinerary(wb, propose_template(wb, "Itinerary"))
    priced, changes = price_lines(lines, _catalog(), Aliases(), Workbook(rate_sheet))

    uffizi = next(p for p in priced if p.row == 8)
    assert uffizi.status == "priced"
    assert uffizi.total == Decimal("1300.00")   # (285 + 40 PM) * 4
    assert changes == []


def test_unrecognised_line_is_unmatched_with_candidates(itinerary, rate_sheet):
    wb = Workbook(itinerary)
    lines = parse_itinerary(wb, propose_template(wb, "Itinerary"))
    priced, _ = price_lines(lines, _catalog(), Aliases(), Workbook(rate_sheet))

    catamaran = next(p for p in priced if p.row == 10)
    assert catamaran.status == "unmatched"
    assert catamaran.total is None
    assert len(catamaran.candidates) <= 3


def test_operator_resolution_prices_the_line_and_is_honoured(itinerary, rate_sheet):
    wb = Workbook(itinerary)
    lines = parse_itinerary(wb, propose_template(wb, "Itinerary"))
    priced, _ = price_lines(lines, _catalog(), Aliases(), Workbook(rate_sheet),
                            resolutions={10: "IT-ROM-0001"})
    catamaran = next(p for p in priced if p.row == 10)
    assert catamaran.status == "priced"
    assert catamaran.item_id == "IT-ROM-0001"


def test_needs_quote_is_reported_not_guessed(itinerary, rate_sheet, tmp_path):
    import openpyxl
    raw = openpyxl.load_workbook(itinerary)
    raw["Itinerary"]["C8"] = 14          # above the top tier
    big = tmp_path / "big.xlsx"
    raw.save(big)

    wb = Workbook(big)
    lines = parse_itinerary(wb, propose_template(wb, "Itinerary"))
    priced, _ = price_lines(lines, _catalog(), Aliases(), Workbook(rate_sheet))
    line = next(p for p in priced if p.row == 8)
    assert line.status == "needs_quote"
    assert line.total is None
    assert "14" in line.reason


def test_day_headings_are_not_priced(day_grouped_itinerary, rate_sheet):
    """'DAY 1 - FLORENCE' has a name but no pax. It is not a line item."""
    wb = Workbook(day_grouped_itinerary)
    lines = parse_itinerary(wb, propose_template(wb, "Itinerary"))
    assert [l.row for l in lines] == [7, 9]
    assert all("DAY" not in l.raw_name for l in lines)


def test_default_pax_fills_in_when_there_is_no_pax_column(wide_itinerary, rate_sheet):
    wb = Workbook(wide_itinerary)
    template = propose_template(wb, "Itinerary")
    template.default_pax = 4
    lines = parse_itinerary(wb, template)
    assert [l.pax for l in lines] == [4, 4]


def test_without_a_date_or_time_column_time_priced_items_need_a_quote(minimal_itinerary,
                                                                     rate_sheet):
    wb = Workbook(minimal_itinerary)
    template = propose_template(wb, "Itinerary")
    template.default_pax = 4
    lines = parse_itinerary(wb, template)
    priced, _ = price_lines(lines, _catalog(), Aliases(), Workbook(rate_sheet))
    uffizi = next(p for p in priced if p.raw_name.startswith("Uffizi"))
    assert uffizi.status == "needs_quote"
    assert "time of day" in uffizi.reason.lower()


def test_price_changes_are_surfaced(itinerary, rate_sheet, tmp_path):
    import openpyxl
    raw = openpyxl.load_workbook(rate_sheet)
    raw["Italy"]["D4"] = 310
    changed = tmp_path / "changed.xlsx"
    raw.save(changed)

    wb = Workbook(itinerary)
    lines = parse_itinerary(wb, propose_template(wb, "Itinerary"))
    _, changes = price_lines(lines, _catalog(), Aliases(), Workbook(changed))
    assert any(c.cell == "Italy!D4" for c in changes)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cost.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.cost'`

- [ ] **Step 3: Write the implementation**

Create `pricing/cost.py`:

```python
"""Orchestration: itinerary lines in, priced lines out.

Nothing here decides a price — patterns.py does that. Nothing here reads a
rate — catalog.py does that. This module's job is to hold the loop together
and to make every not-priced outcome explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from pricing.catalog import Catalog, FingerprintMismatch, PriceChange, resolve_rates
from pricing.itinerary_profile import ItineraryTemplate
from pricing.match import Aliases, candidates
from pricing.patterns import NeedsQuote, PricingRequest, evaluate
from pricing.workbook import CellRef, Workbook

CONFIDENT_MATCH = 0.85


@dataclass
class ItineraryLine:
    row: int
    raw_name: str
    date: Date | None
    pax: int
    day_part: str | None


@dataclass
class PricedLine:
    row: int
    raw_name: str
    item_id: str | None = None
    status: str = "unmatched"
    total: Decimal | None = None
    currency: str | None = None
    reason: str | None = None
    breakdown: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)


def parse_itinerary(wb: Workbook, template: ItineraryTemplate) -> list[ItineraryLine]:
    max_row, _ = wb.dimensions(template.sheet)
    roles = template.roles
    lines: list[ItineraryLine] = []

    for row in range(template.first_data_row, max_row + 1):
        name = wb.read(CellRef(template.sheet, roles["name"], row))
        if name is None or not str(name).strip():
            continue

        pax = _as_pax(_role(wb, template, "pax", row)) or (template.default_pax or 0)
        if pax == 0:
            # A row with a name but nobody travelling is a section heading
            # ('DAY 1 - FLORENCE'), not a line item. Pricing it would put a
            # number next to a date header in her client's document.
            continue

        lines.append(ItineraryLine(
            row=row,
            raw_name=str(name).strip(),
            date=_as_date(_role(wb, template, "date", row)),
            pax=pax,
            day_part=_as_day_part(_role(wb, template, "day_part", row)),
        ))
    return lines


def price_lines(lines: list[ItineraryLine], catalog: Catalog, aliases: Aliases,
                wb_rates: Workbook,
                resolutions: dict[int, str] | None = None
                ) -> tuple[list[PricedLine], list[PriceChange]]:
    resolutions = resolutions or {}
    priced: list[PricedLine] = []
    all_changes: list[PriceChange] = []

    for line in lines:
        result = PricedLine(row=line.row, raw_name=line.raw_name)
        item_id = resolutions.get(line.row)

        if item_id is None:
            ranked = candidates(line.raw_name, catalog.items, aliases)
            result.candidates = [vars(c) for c in ranked]
            if ranked and ranked[0].score >= CONFIDENT_MATCH:
                item_id = ranked[0].item_id
            else:
                result.reason = "No confident match — please choose."
                priced.append(result)
                continue

        result.item_id = item_id
        try:
            item = catalog.get(item_id)
            rates, changes = resolve_rates(item, wb_rates)
            all_changes.extend(changes)
            outcome = evaluate(item.to_dict(), rates,
                               PricingRequest(line.pax, line.date, line.day_part))
        except KeyError:
            result.status = "unmatched"
            result.reason = f"Catalog has no item {item_id!r}."
        except (NeedsQuote, FingerprintMismatch) as exc:
            result.status = "needs_quote"
            result.reason = getattr(exc, "reason", str(exc))
        else:
            result.status = "priced"
            result.total = outcome.total
            result.currency = outcome.currency
            result.breakdown = outcome.breakdown

        priced.append(result)

    return priced, all_changes


def _role(wb: Workbook, template: ItineraryTemplate, role: str, row: int) -> object:
    letter = template.roles.get(role)
    if not letter:
        return None
    return wb.read(CellRef(template.sheet, letter, row))


def _as_date(value: object) -> Date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, Date):
        return value
    try:
        return datetime.fromisoformat(str(value).strip()).date()
    except ValueError:
        return None


def _as_pax(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _as_day_part(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_cost.py -v`
Expected: PASS, 9 passed

- [ ] **Step 5: Commit**

```bash
git add pricing/cost.py tests/test_cost.py
git commit -m "feat: costing orchestration with explicit unmatched and needs-quote outcomes"
```

---

### Task 11: Writing the costed workbook

**Files:**
- Create: `pricing/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `pricing.workbook.copy_for_write`/`Workbook`/`CellRef`, `pricing.cost.PricedLine`, `pricing.catalog.PriceChange`.
- Produces:
  - `pricing.report.output_path(src: Path, today: date) -> Path` — `Trip_Smith_costed_2026-09-03.xlsx`, suffixed `_2`, `_3`… if taken.
  - `pricing.report.write_costed_workbook(src: Path, template, priced: list[PricedLine], today: date) -> Path`
  - `pricing.report.summarize(priced, changes) -> dict` with keys `priced`, `needs_quote`, `unmatched`, `totals_by_currency`, `price_changes`.
  - `pricing.report.write_run_log(runs_dir: Path, payload: dict) -> Path`

**Rule from Task 4b:** read `docs/fidelity.json`, the machine-readable result of the
round-trip fidelity measurement. It has the shape:

```json
{ "images_survive_roundtrip": true, "conditional_formatting_survives": true,
  "openpyxl": "3.1.5", "pillow": "12.3.0" }
```

If `images_survive_roundtrip` is `false`, `summarize` must include in its `warnings` list:
`"Note: your itinerary's logo is not carried into the costed copy."` If it is `true`, or
the file is missing, emit no such warning. Do not grep the prose in
`docs/fidelity-findings.md` — that document is for humans and its wording will drift.

- [ ] **Step 1: Write the failing test**

Create `tests/test_report.py`:

```python
from datetime import date
from decimal import Decimal

from pricing.catalog import PriceChange
from pricing.cost import PricedLine
from pricing.itinerary_profile import propose_template
from pricing.report import output_path, summarize, write_costed_workbook, write_run_log
from pricing.workbook import CellRef, Workbook

PRICED = [
    PricedLine(row=8, raw_name="Uffizi", item_id="IT-1", status="priced",
               total=Decimal("1300.00"), currency="EUR"),
    PricedLine(row=9, raw_name="Vatican", item_id="IT-2", status="needs_quote",
               reason="14 pax is above the highest mapped tier (10 pax)."),
    PricedLine(row=10, raw_name="Catamaran", status="unmatched",
               reason="No confident match — please choose."),
]


def test_output_path_is_dated_and_never_overwrites(tmp_path):
    src = tmp_path / "Trip_Smith.xlsx"
    src.write_bytes(b"x")
    first = output_path(src, date(2026, 9, 3))
    assert first.name == "Trip_Smith_costed_2026-09-03.xlsx"
    first.write_bytes(b"x")
    assert output_path(src, date(2026, 9, 3)).name == "Trip_Smith_costed_2026-09-03_2.xlsx"


def test_writes_totals_and_leaves_the_original_alone(itinerary):
    before = itinerary.read_bytes()
    template = propose_template(Workbook(itinerary), "Itinerary")
    out = write_costed_workbook(itinerary, template, PRICED, date(2026, 9, 3))

    wb = Workbook(out)
    assert wb.read(CellRef("Itinerary", "E", 8)) == 1300.00
    assert itinerary.read_bytes() == before


def test_unpriced_lines_are_never_blank(itinerary):
    template = propose_template(Workbook(itinerary), "Itinerary")
    out = write_costed_workbook(itinerary, template, PRICED, date(2026, 9, 3))
    wb = Workbook(out)
    assert "NEEDS QUOTE" in str(wb.read(CellRef("Itinerary", "E", 9)))
    assert "NOT MATCHED" in str(wb.read(CellRef("Itinerary", "E", 10)))


def test_summary_counts_and_totals_by_currency():
    summary = summarize(PRICED, [PriceChange("Italy!D4", Decimal("285"), Decimal("310"))])
    assert summary["priced"] == 1
    assert summary["needs_quote"] == 1
    assert summary["unmatched"] == 1
    assert summary["totals_by_currency"] == {"EUR": "1300.00"}
    assert len(summary["price_changes"]) == 1


def test_mixed_currencies_are_totalled_separately():
    lines = PRICED + [PricedLine(row=11, raw_name="Safari", item_id="ZA-1",
                                 status="priced", total=Decimal("500.00"), currency="USD")]
    assert summarize(lines, [])["totals_by_currency"] == {"EUR": "1300.00", "USD": "500.00"}


def test_run_log_is_written(tmp_path):
    path = write_run_log(tmp_path / "runs", {"summary": {"priced": 1}})
    assert path.exists() and path.suffix == ".json"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.report'`

- [ ] **Step 3: Write the implementation**

Create `pricing/report.py`:

```python
"""Producing the deliverable: a costed copy, a summary, and an audit trail."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pricing.catalog import PriceChange
from pricing.cost import PricedLine
from pricing.itinerary_profile import ItineraryTemplate
from pricing.workbook import CellRef, Workbook, copy_for_write


def output_path(src: Path, today: Date) -> Path:
    src = Path(src)
    base = f"{src.stem}_costed_{today.isoformat()}"
    candidate = src.with_name(f"{base}.xlsx")
    counter = 2
    while candidate.exists():
        candidate = src.with_name(f"{base}_{counter}.xlsx")
        counter += 1
    return candidate


def write_costed_workbook(src: Path, template: ItineraryTemplate,
                          priced: list[PricedLine], today: Date) -> Path:
    dst = output_path(src, today)
    copy_for_write(src, dst)

    wb = Workbook(dst)
    column = template.roles["cost"]
    for line in priced:
        ref = CellRef(template.sheet, column, line.row)
        if line.status == "priced" and line.total is not None:
            wb.write(ref, float(line.total))
        elif line.status == "needs_quote":
            wb.write(ref, f"NEEDS QUOTE — {line.reason}")
        else:
            wb.write(ref, f"NOT MATCHED — {line.reason or 'no candidate chosen'}")
    wb.save()
    wb.close()
    return dst


def summarize(priced: list[PricedLine], changes: list[PriceChange]) -> dict:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for line in priced:
        if line.status == "priced" and line.total is not None and line.currency:
            totals[line.currency] += line.total

    return {
        "priced": sum(1 for p in priced if p.status == "priced"),
        "needs_quote": sum(1 for p in priced if p.status == "needs_quote"),
        "unmatched": sum(1 for p in priced if p.status == "unmatched"),
        "totals_by_currency": {k: str(v) for k, v in sorted(totals.items())},
        "price_changes": [
            {"cell": c.cell, "was": str(c.last_seen), "now": str(c.current)}
            for c in changes
        ],
        "warnings": _warnings(),
    }


def _warnings() -> list[str]:
    """Carry forward what Task 4b measured about round-trip fidelity.

    Reads a machine-readable result rather than grepping prose, so that
    editing the human-facing findings document cannot silently change what
    the operator is told.
    """
    findings = Path(__file__).resolve().parent.parent / "docs" / "fidelity.json"
    if not findings.exists():
        return []
    try:
        measured = json.loads(findings.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if measured.get("images_survive_roundtrip") is False:
        return ["Note: your itinerary's logo is not carried into the costed copy."]
    return []


def write_run_log(runs_dir: Path, payload: dict) -> Path:
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{datetime.now():%Y-%m-%dT%H-%M-%S}.json"
    path.write_text(json.dumps(payload, indent=2, default=str, ensure_ascii=False),
                    encoding="utf-8")
    return path
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --extra dev pytest tests/test_report.py -v`
Expected: PASS, 6 passed

- [ ] **Step 5: Commit**

```bash
git add pricing/report.py tests/test_report.py
git commit -m "feat: costed workbook output, summary, and run log"
```

---

### Task 12: Configuration and the health check

**Files:**
- Create: `pricing/config.py`
- Create: `pricing/doctor.py`
- Test: `tests/test_config.py`
- Test: `tests/test_doctor.py`

**Interfaces:**
- Produces:
  - `pricing.config.Config` — dataclass `root: Path`, `costing_workbook: Path | None`. Properties `data_dir`, `catalog_path`, `aliases_path`, `profiles_dir`, `runs_dir`, `template_path`.
  - `pricing.config.load_config(root: Path | None = None) -> Config`
  - `pricing.config.save_config(config: Config) -> None`
  - `pricing.doctor.Check` — dataclass `name: str`, `ok: bool`, `message: str`.
  - `pricing.doctor.run_checks(config: Config) -> list[Check]`

Every `Check.message` is written for a non-technical reader. No exception text, no paths
longer than they need to be, and every failure says what to do next.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
from pricing.config import Config, load_config, save_config


def test_paths_derive_from_root(tmp_path):
    config = Config(root=tmp_path, costing_workbook=None)
    assert config.data_dir == tmp_path / "data"
    assert config.catalog_path == tmp_path / "data" / "catalog.json"
    assert config.aliases_path == tmp_path / "data" / "aliases.json"
    assert config.profiles_dir == tmp_path / "data" / "profiles"
    assert config.runs_dir == tmp_path / "data" / "runs"


def test_config_roundtrips(tmp_path, rate_sheet):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    assert load_config(tmp_path).costing_workbook == rate_sheet


def test_missing_config_is_not_an_error(tmp_path):
    assert load_config(tmp_path).costing_workbook is None
```

Create `tests/test_doctor.py`:

```python
from pricing.config import Config
from pricing.doctor import run_checks


def test_all_green_when_configured(tmp_path, rate_sheet):
    checks = run_checks(Config(root=tmp_path, costing_workbook=rate_sheet))
    assert all(c.ok for c in checks), [c.message for c in checks if not c.ok]


def test_missing_workbook_explains_what_to_do(tmp_path):
    checks = run_checks(Config(root=tmp_path, costing_workbook=tmp_path / "gone.xlsx"))
    failure = next(c for c in checks if not c.ok)
    assert "costing" in failure.message.lower()
    assert "traceback" not in failure.message.lower()


def test_unconfigured_workbook_asks_for_it(tmp_path):
    checks = run_checks(Config(root=tmp_path, costing_workbook=None))
    assert any("haven't told me where" in c.message for c in checks)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --extra dev pytest tests/test_config.py tests/test_doctor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.config'`

- [ ] **Step 3: Write `pricing/config.py`**

```python
"""Where everything lives. One file, one source of truth for paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    root: Path
    costing_workbook: Path | None = None

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "catalog.json"

    @property
    def aliases_path(self) -> Path:
        return self.data_dir / "aliases.json"

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def template_path(self) -> Path:
        return self.profiles_dir / "itinerary_template.json"

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"


def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config(root: Path | None = None) -> Config:
    config = Config(root=Path(root) if root else _default_root())
    if config.config_path.exists():
        data = json.loads(config.config_path.read_text(encoding="utf-8"))
        raw = data.get("costing_workbook")
        config.costing_workbook = Path(raw) if raw else None
    return config


def save_config(config: Config) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "costing_workbook": str(config.costing_workbook) if config.costing_workbook else None
    }
    config.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Write `pricing/doctor.py`**

```python
"""The health check. Its entire audience is a non-technical operator on the
phone to a developer, so every message must be readable aloud.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import openpyxl

from pricing.config import Config


@dataclass
class Check:
    name: str
    ok: bool
    message: str


def run_checks(config: Config) -> list[Check]:
    return [
        _python_check(),
        _openpyxl_check(),
        _workbook_check(config),
        _data_dir_check(config),
    ]


def _python_check() -> Check:
    ok = sys.version_info >= (3, 12)
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    return Check(
        "python", ok,
        f"Python {version} is installed and working." if ok
        else f"Python {version} is too old. Ask for help reinstalling — we need 3.12 or newer.",
    )


def _openpyxl_check() -> Check:
    return Check("openpyxl", True,
                 f"Excel support is installed (openpyxl {openpyxl.__version__}).")


def _workbook_check(config: Config) -> Check:
    if config.costing_workbook is None:
        return Check("workbook", False,
                     "You haven't told me where your costing workbook is yet. "
                     "Run /profile and point me at it.")
    if not config.costing_workbook.exists():
        return Check("workbook", False,
                     f"I can't find your costing workbook — I was looking for "
                     f"{config.costing_workbook.name}. Has it been moved or renamed? "
                     "Run /profile to point me at it again.")
    try:
        openpyxl.load_workbook(config.costing_workbook, read_only=True).close()
    except Exception:
        return Check("workbook", False,
                     f"I found {config.costing_workbook.name} but couldn't open it. "
                     "If it's open in Excel, please close it and try again.")
    return Check("workbook", True,
                 f"Found and opened your costing workbook ({config.costing_workbook.name}).")


def _data_dir_check(config: Config) -> Check:
    try:
        config.data_dir.mkdir(parents=True, exist_ok=True)
        probe = config.data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception:
        return Check("data", False,
                     "I can't save anything to the pricing folder. "
                     "Ask for help — the folder's permissions need changing.")
    return Check("data", True, "I can save your mappings and quotes.")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --extra dev pytest tests/test_config.py tests/test_doctor.py -v`
Expected: PASS, 6 passed

- [ ] **Step 6: Commit**

```bash
git add pricing/config.py pricing/doctor.py tests/
git commit -m "feat: configuration and plain-English health check"
```

---

### Task 13: The CLI

Every command Claude runs goes through here, and every one prints exactly one JSON object to stdout.

**Files:**
- Create: `pricing/cli.py`
- Create: `pricing/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: every other `pricing` module.
- Produces: `pricing.cli.main(argv: list[str] | None = None) -> int`. Subcommands:

| Subcommand | Arguments | Output keys |
|---|---|---|
| `doctor` | — | `ok`, `checks` |
| `profile` | `--workbook PATH` | `ok`, `sheets`, `written` |
| `rows` | `--sheet NAME --from N --to M` | `ok`, `rows` |
| `profile-itinerary` | `--file PATH` | `ok`, `template` |
| `catalog-add` | `--file PATH` | `ok`, `id`, `count` |
| `cost` | `--file PATH [--resolutions PATH]` | `ok`, `output`, `summary`, `lines`, `run_log` |

Arguments are always paths, never inline JSON — Windows shell quoting makes inline JSON unreliable.

Any uncaught exception is converted to `{"ok": false, "error": "<plain English>"}` on
stdout, exit code 1, with the traceback written to `data/runs/`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
import json

from pricing.cli import main
from pricing.config import Config, save_config


def _run(capsys, argv):
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_doctor_reports_json(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out = _run(capsys, ["--root", str(tmp_path), "doctor"])
    assert code == 0 and out["ok"] is True
    assert len(out["checks"]) == 4


def test_profile_writes_files_and_lists_sheets(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out = _run(capsys, ["--root", str(tmp_path), "profile",
                              "--workbook", str(rate_sheet)])
    assert code == 0
    assert [s["name"] for s in out["sheets"]] == ["Italy", "Greece"]
    assert (tmp_path / "data" / "profiles" / "Italy.json").exists()


def test_rows_returns_raw_values_for_mapping(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    code, out = _run(capsys, ["--root", str(tmp_path), "rows",
                              "--sheet", "Italy", "--from", "4", "--to", "5"])
    assert code == 0
    assert out["rows"][0]["values"][0] == "Uffizi Gallery — Private Guided Tour"


def test_catalog_add_persists(tmp_path, rate_sheet, capsys):
    save_config(Config(root=tmp_path, costing_workbook=rate_sheet))
    item = tmp_path / "item.json"
    item.write_text(json.dumps({
        "id": "IT-1", "name": "Vatican Museums — Skip the Line",
        "name_cell": "Italy!A6", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "Italy!D6", "last_seen": "95"},
        "modifiers": [], "source_rows": [6],
        "row_fingerprint": "", "confirmed_at": "2026-09-03"}), encoding="utf-8")

    code, out = _run(capsys, ["--root", str(tmp_path), "catalog-add", "--file", str(item)])
    assert code == 0 and out["id"] == "IT-1" and out["count"] == 1


def test_errors_are_plain_english_json(tmp_path, capsys):
    code, out = _run(capsys, ["--root", str(tmp_path), "profile",
                              "--workbook", str(tmp_path / "missing.xlsx")])
    assert code == 1
    assert out["ok"] is False
    assert "traceback" not in out["error"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.cli'`

- [ ] **Step 3: Write `pricing/cli.py`**

```python
"""The only surface Claude talks to. One JSON object per invocation."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date
from pathlib import Path

from pricing import profile as profile_mod
from pricing.catalog import Catalog, CatalogItem
from pricing.config import load_config, save_config
from pricing.cost import parse_itinerary, price_lines
from pricing.doctor import run_checks
from pricing.itinerary_profile import propose_template, save_template
from pricing.match import Aliases
from pricing.report import summarize, write_costed_workbook, write_run_log
from pricing.workbook import Workbook


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_config(Path(args.root) if args.root else None)

    try:
        payload = _dispatch(args, config)
    except Exception as exc:  # noqa: BLE001 — the boundary converts everything
        _log_traceback(config)
        print(json.dumps({"ok": False, "error": _friendly(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, **payload}, ensure_ascii=False, default=str))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pricing")
    parser.add_argument("--root")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")

    p = sub.add_parser("profile")
    p.add_argument("--workbook", required=True)

    p = sub.add_parser("rows")
    p.add_argument("--sheet", required=True)
    p.add_argument("--from", dest="start", type=int, required=True)
    p.add_argument("--to", dest="end", type=int, required=True)

    p = sub.add_parser("profile-itinerary")
    p.add_argument("--file", required=True)

    p = sub.add_parser("catalog-add")
    p.add_argument("--file", required=True)

    p = sub.add_parser("cost")
    p.add_argument("--file", required=True)
    p.add_argument("--resolutions")

    return parser


def _dispatch(args, config) -> dict:
    if args.command == "doctor":
        checks = run_checks(config)
        return {"ok_all": all(c.ok for c in checks),
                "checks": [vars(c) for c in checks]}

    if args.command == "profile":
        workbook_path = Path(args.workbook)
        wb = Workbook(workbook_path)
        profiles = profile_mod.profile_workbook(wb)
        config.profiles_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for sheet_profile in profiles:
            path = config.profiles_dir / f"{sheet_profile.name}.json"
            path.write_text(
                json.dumps(profile_mod.to_dict([sheet_profile]), indent=2, ensure_ascii=False),
                encoding="utf-8")
            written.append(str(path))
        config.costing_workbook = workbook_path
        save_config(config)
        return {"sheets": profile_mod.to_dict(profiles)["sheets"], "written": written}

    if args.command == "rows":
        wb = Workbook(config.costing_workbook)
        return {"rows": [{"row": r, "values": wb.read_row(args.sheet, r)}
                         for r in range(args.start, args.end + 1)]}

    if args.command == "profile-itinerary":
        wb = Workbook(Path(args.file))
        template = propose_template(wb, wb.sheet_names()[0])
        save_template(template, config.template_path)
        return {"template": vars(template)}

    if args.command == "catalog-add":
        item = CatalogItem.from_dict(json.loads(Path(args.file).read_text(encoding="utf-8")))
        catalog = Catalog.load(config.catalog_path)
        catalog.upsert(item)
        catalog.save(config.catalog_path)
        return {"id": item.id, "count": len(catalog.items)}

    if args.command == "cost":
        return _cost(args, config)

    raise ValueError(f"unknown command {args.command!r}")


def _cost(args, config) -> dict:
    from pricing.itinerary_profile import load_template

    src = Path(args.file)
    wb_itinerary = Workbook(src)
    template = (load_template(config.template_path)
                if config.template_path.exists()
                else propose_template(wb_itinerary, wb_itinerary.sheet_names()[0]))

    resolutions = {}
    if args.resolutions:
        raw = json.loads(Path(args.resolutions).read_text(encoding="utf-8"))
        resolutions = {int(k): v for k, v in raw.items()}

    lines = parse_itinerary(wb_itinerary, template)
    catalog = Catalog.load(config.catalog_path)
    aliases = Aliases.load(config.aliases_path)
    priced, changes = price_lines(lines, catalog, aliases,
                                  Workbook(config.costing_workbook), resolutions)

    for row, item_id in resolutions.items():
        match = next((line for line in lines if line.row == row), None)
        if match:
            aliases.add(match.raw_name, item_id)
    aliases.save(config.aliases_path)

    output = write_costed_workbook(src, template, priced, date.today())
    summary = summarize(priced, changes)
    log = write_run_log(config.runs_dir, {
        "input": str(src), "output": str(output),
        "summary": summary, "lines": [vars(p) for p in priced]})

    return {"output": str(output), "summary": summary,
            "lines": [vars(p) for p in priced], "run_log": str(log)}


def _friendly(exc: Exception) -> str:
    from pricing.itinerary_profile import MissingRoleError
    from pricing.workbook import WorkbookLockedError

    if isinstance(exc, WorkbookLockedError):
        return str(exc)
    if isinstance(exc, MissingRoleError):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        name = Path(getattr(exc, "filename", "") or "that file").name
        return f"I couldn't find {name}. Has it been moved or renamed?"
    return ("Something went wrong that I don't have a friendly explanation for. "
            "The details are saved in the runs folder — please send them on.")


def _log_traceback(config) -> None:
    try:
        config.runs_dir.mkdir(parents=True, exist_ok=True)
        (config.runs_dir / "last-error.txt").write_text(
            traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass
```

- [ ] **Step 4: Write `pricing/__main__.py`**

```python
import sys

from pricing.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the whole suite**

Run: `uv run --extra dev pytest -v`
Expected: PASS, all tests

Note `test_doctor_reports_json` asserts `out["ok"]` — that key is added by `main` as the
"the command succeeded" flag, while `ok_all` reports whether every check passed. If the
test fails on this, keep both keys and fix the test's expectation, not the CLI contract.

- [ ] **Step 6: Commit**

```bash
git add pricing/cli.py pricing/__main__.py tests/test_cli.py
git commit -m "feat: JSON CLI for every engine operation"
```

---

### Task 14: Verify and refresh

Both are read-only diff reports, so they share a task.

**Files:**
- Create: `pricing/verify.py`
- Modify: `pricing/cli.py` (add `verify` and `refresh` subcommands to `_build_parser` and `_dispatch`)
- Test: `tests/test_verify.py`

**Interfaces:**
- Consumes: `pricing.cost`, `pricing.catalog`, `pricing.report`.
- Produces:
  - `pricing.verify.LineDiff` — dataclass `row: int`, `name: str`, `expected: Decimal | None`, `computed: Decimal | None`, `delta: Decimal | None`, `status: str` (`match`, `mismatch`, `not_priced`, `no_expected`).
  - `pricing.verify.verify_itinerary(src, template, catalog, aliases, wb_rates) -> tuple[list[LineDiff], dict]`
  - `pricing.verify.refresh(catalog, wb_rates) -> dict` with keys `price_changes`, `broken_items`, `checked`.

New CLI subcommands: `verify --file PATH` → `ok`, `diffs`, `summary`; `refresh` → `ok`, `price_changes`, `broken_items`, `checked`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_verify.py`:

```python
from decimal import Decimal

import openpyxl

from pricing.catalog import Catalog, CatalogItem, fingerprint
from pricing.itinerary_profile import propose_template
from pricing.match import Aliases
from pricing.verify import refresh, verify_itinerary
from pricing.workbook import Workbook


def _catalog():
    catalog = Catalog()
    catalog.upsert(CatalogItem(
        id="IT-FLR-0032", name="Uffizi Gallery — Private Guided Tour",
        name_cell="Italy!A4", region="Italy", currency="EUR", unit="per_person",
        pricing={"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"}]},
        modifiers=[{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                    "cell": "Italy!F4", "last_seen": "40"}],
        source_rows=[4, 5],
        row_fingerprint=fingerprint("Uffizi Gallery — Private Guided Tour")))
    return catalog


def _hand_priced(itinerary, tmp_path, value):
    raw = openpyxl.load_workbook(itinerary)
    raw["Itinerary"]["E8"] = value
    path = tmp_path / "hand.xlsx"
    raw.save(path)
    return path


def test_matching_hand_price_reports_a_match(itinerary, rate_sheet, tmp_path):
    hand = _hand_priced(itinerary, tmp_path, 1300)
    wb = Workbook(hand)
    diffs, summary = verify_itinerary(hand, propose_template(wb, "Itinerary"),
                                      _catalog(), Aliases(), Workbook(rate_sheet))
    row8 = next(d for d in diffs if d.row == 8)
    assert row8.status == "match"
    assert summary["matches"] == 1


def test_mismatch_reports_the_delta(itinerary, rate_sheet, tmp_path):
    hand = _hand_priced(itinerary, tmp_path, 1250)
    wb = Workbook(hand)
    diffs, summary = verify_itinerary(hand, propose_template(wb, "Itinerary"),
                                      _catalog(), Aliases(), Workbook(rate_sheet))
    row8 = next(d for d in diffs if d.row == 8)
    assert row8.status == "mismatch"
    assert row8.delta == Decimal("50.00")
    assert summary["mismatches"] == 1


def test_refresh_reports_price_changes(rate_sheet, tmp_path):
    raw = openpyxl.load_workbook(rate_sheet)
    raw["Italy"]["D4"] = 310
    changed = tmp_path / "changed.xlsx"
    raw.save(changed)

    result = refresh(_catalog(), Workbook(changed))
    assert result["checked"] == 1
    assert result["price_changes"][0]["now"] == "310"
    assert result["broken_items"] == []


def test_refresh_reports_broken_items(rate_sheet, tmp_path):
    raw = openpyxl.load_workbook(rate_sheet)
    raw["Italy"].insert_rows(4)
    raw["Italy"]["A4"] = "Colosseum — Underground Tour"
    shifted = tmp_path / "shifted.xlsx"
    raw.save(shifted)

    result = refresh(_catalog(), Workbook(shifted))
    assert result["broken_items"][0]["id"] == "IT-FLR-0032"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --extra dev pytest tests/test_verify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pricing.verify'`

- [ ] **Step 3: Write `pricing/verify.py`**

```python
"""Trust-building reports.

verify_itinerary re-costs work the operator already did by hand and diffs
it — the acceptance test that neither developer nor model can run, because
only she has the data.

refresh sweeps the catalog against the live workbook and reports what moved.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from pricing.catalog import Catalog, FingerprintMismatch, resolve_rates
from pricing.cost import parse_itinerary, price_lines
from pricing.itinerary_profile import ItineraryTemplate
from pricing.match import Aliases
from pricing.money import MoneyParseError, parse_money
from pricing.workbook import CellRef, Workbook


@dataclass
class LineDiff:
    row: int
    name: str
    expected: Decimal | None
    computed: Decimal | None
    delta: Decimal | None
    status: str


def verify_itinerary(src: Path, template: ItineraryTemplate, catalog: Catalog,
                     aliases: Aliases, wb_rates: Workbook) -> tuple[list[LineDiff], dict]:
    wb = Workbook(src)
    lines = parse_itinerary(wb, template)
    priced, _ = price_lines(lines, catalog, aliases, wb_rates)
    cost_column = template.roles["cost"]

    diffs: list[LineDiff] = []
    for line in priced:
        raw = wb.read(CellRef(template.sheet, cost_column, line.row))
        try:
            expected = parse_money(raw)
        except MoneyParseError:
            expected = None

        computed = line.total
        if computed is None:
            status, delta = "not_priced", None
        elif expected is None:
            status, delta = "no_expected", None
        elif expected == computed:
            status, delta = "match", Decimal("0.00")
        else:
            status, delta = "mismatch", abs(computed - expected)

        diffs.append(LineDiff(line.row, line.raw_name, expected, computed, delta, status))

    summary = {
        "matches": sum(1 for d in diffs if d.status == "match"),
        "mismatches": sum(1 for d in diffs if d.status == "mismatch"),
        "not_priced": sum(1 for d in diffs if d.status == "not_priced"),
        "no_expected": sum(1 for d in diffs if d.status == "no_expected"),
    }
    return diffs, summary


def refresh(catalog: Catalog, wb_rates: Workbook) -> dict:
    changes: list[dict] = []
    broken: list[dict] = []

    for item in catalog.items:
        try:
            _, item_changes = resolve_rates(item, wb_rates)
        except FingerprintMismatch as exc:
            broken.append({"id": item.id, "name": item.name, "message": str(exc)})
            continue
        changes.extend(
            {"id": item.id, "name": item.name, "cell": c.cell,
             "was": str(c.last_seen), "now": str(c.current)}
            for c in item_changes
        )

    return {"checked": len(catalog.items), "price_changes": changes, "broken_items": broken}
```

- [ ] **Step 4: Add the CLI subcommands**

In `pricing/cli.py`, add to `_build_parser` after the `cost` parser:

```python
    p = sub.add_parser("verify")
    p.add_argument("--file", required=True)

    sub.add_parser("refresh")
```

And add to `_dispatch` before the final `raise`:

```python
    if args.command == "verify":
        from pricing.itinerary_profile import load_template
        from pricing.verify import verify_itinerary

        src = Path(args.file)
        wb = Workbook(src)
        template = (load_template(config.template_path)
                    if config.template_path.exists()
                    else propose_template(wb, wb.sheet_names()[0]))
        diffs, summary = verify_itinerary(
            src, template, Catalog.load(config.catalog_path),
            Aliases.load(config.aliases_path), Workbook(config.costing_workbook))
        return {"diffs": [vars(d) for d in diffs], "summary": summary}

    if args.command == "refresh":
        from pricing.verify import refresh

        return refresh(Catalog.load(config.catalog_path),
                       Workbook(config.costing_workbook))
```

- [ ] **Step 5: Run the suite**

Run: `uv run --extra dev pytest -v`
Expected: PASS, all tests

- [ ] **Step 6: Commit**

```bash
git add pricing/verify.py pricing/cli.py tests/test_verify.py
git commit -m "feat: verify against hand-priced itineraries and refresh price sweep"
```

---

### Task 15: Skills and commands

The engine is complete. This task is the conversational layer the operator actually touches.

**Files:**
- Create: `.claude/skills/profile-rate-sheet/SKILL.md`
- Create: `.claude/skills/map-rate-sheet/SKILL.md`
- Create: `.claude/skills/cost-itinerary/SKILL.md`
- Create: `.claude/skills/refresh-rates/SKILL.md`
- Create: `.claude/commands/{profile,map,cost,refresh,verify,doctor,update}.md`

**Interfaces:**
- Consumes: the CLI contract from Tasks 13 and 14.
- Produces: nothing importable. Verified by Task 16's end-to-end walkthrough.

**Writing rules for every file in this task:**
- The reader is a non-technical travel agent. No jargon, no file paths in prose, no JSON shown to her.
- Never state a price you calculated yourself. Every number comes from a CLI result.
- Never write to the catalog without an explicit confirmation in the immediately preceding turn.

- [ ] **Step 1: Write the profiling skill**

Create `.claude/skills/profile-rate-sheet/SKILL.md`:

```markdown
---
name: profile-rate-sheet
description: Use when the operator runs /profile, or attaches a costing workbook for the first time, or says her rate sheet has changed shape. Reads the workbook's structure, proposes the pricing model, and gets it confirmed.
---

# Profiling a rate sheet

## 1. Locate the workbook

Ask which file is her costing workbook if you don't already know. Then run:

`uv run python -m pricing.cli profile --workbook "<path>"`

This saves a structural profile per sheet and remembers the workbook location.

## 2. Read the profile back to her, one sheet at a time

For each sheet in the result, tell her in plain language what you found:

> **Italy** — 7 rows, headers on row 3: Experience, Min Pax, Max Pax, Net Rate, Unit, PM Supplement.
> I can see two data blocks and one merged title cell.

## 3. Propose the pricing model, axis by axis

From the column headers and the sample values, name the axes you believe exist and ask
about each **separately**. One question per message.

- "The `Unit` column has two values, `per person` and `per group`. Am I right that this
  says whether the rate is charged once or per traveller?"
- "There's a `PM Supplement` column. Is that added per person, or once per booking?"
- "I don't see anything about seasons or blackout dates on this sheet. Are there any I
  should know about, or are rates the same year-round?"

Record her answers. They determine which pricing patterns Task 5's engine will use.

## 4. Profile the itinerary template

Ask her to attach a blank itinerary. Run:

`uv run python -m pricing.cli profile-itinerary --file "<path>"`

Read the proposed column roles back and confirm each. If the command reports missing
roles, ask her directly which column holds the experience name and which is the empty
cost column.

## 5. Tell her what's safe to share

Finish by telling her the profile files contain no prices and no client names, so they
are safe to send to whoever supports this tool.

## 6. Point at the next step

> Next, run `/map Italy` (or whichever region you want first). You only need to map a
> region once, and you can stop partway through — it picks up where you left off.
```

- [ ] **Step 2: Write the mapping skill**

Create `.claude/skills/map-rate-sheet/SKILL.md`:

```markdown
---
name: map-rate-sheet
description: Use when the operator runs /map, names a region to map, or asks to review or fix existing mappings. Walks a sheet's rows, proposes a catalog entry for each, and saves only what she confirms.
---

# Mapping a region sheet

## 1. Read the rows

`uv run python -m pricing.cli rows --sheet "<region>" --from <first> --to <last>`

Use the sheet's profile to find where the data starts and stops. Work in blocks of
about 15 rows so you never hold more than you can reason about.

## 2. Propose one entry, and get the shape confirmed

Present the first row group in her language, not in JSON:

> **Rows 14–15 — Uffizi Gallery, Private Guided Tour**
> I read this as **per person, tiered by group size**: €285 for 1–4, €240 for 5–10.
> PM departures add €40 per person.
>
> `1` Correct  ·  `2` Not quite  ·  `3` Skip for now  ·  `4` Not a sellable item

## 3. Batch everything that matches that shape

Once she confirms a shape, scan the remaining rows for the same structure and present
them **as a group**:

> Rows 20–34 all follow that same structure. Here they are — tell me if any are different.

A 90-row sheet should cost her about 8 decisions, not 90.

## 4. Save after every confirmation

For each confirmed entry, write the item to a temporary JSON file and run:

`uv run python -m pricing.cli catalog-add --file "<path>"`

Do this **immediately after each confirmation**, never in a batch at the end. She must be
able to walk away mid-sheet and lose nothing.

Item fields: `id` (region prefix plus a number, e.g. `IT-FLR-0032`), `name` exactly as it
appears in the sheet, `name_cell` (the cell holding that name), `region`, `currency`,
`unit` (`per_person` or `per_group`), `pricing`, `modifiers`, `source_rows`,
`row_fingerprint`, `confirmed_at`, and `min_billable_pax` when there's a minimum.

For `row_fingerprint`, use the value the `rows` command reported for `name_cell`, run
through the same normalisation the engine uses: run
`uv run python -c "from pricing.catalog import fingerprint; print(fingerprint('<name>'))"`.

## 5. Close the loop

Report how many entries were saved and how many rows were skipped, then:

> `/map <next region>` when you're ready, or `/cost` to price an itinerary using what
> you've mapped so far.
```

- [ ] **Step 3: Write the costing skill**

Create `.claude/skills/cost-itinerary/SKILL.md`:

```markdown
---
name: cost-itinerary
description: Use when the operator runs /cost or attaches an itinerary to be priced. Prices every line it can, asks about the ones it can't, and produces a costed copy of her file.
---

# Costing an itinerary

## 1. First pass

`uv run python -m pricing.cli cost --file "<path>"`

## 2. Resolve what came back unmatched

For each line with status `unmatched`, show her the candidates the engine returned, with
its reasoning — never invent options that aren't in the result:

> Line 10 says **"Sunset catamaran w/ open bar"**. The closest things in your catalog are:
> `1` Catamaran Cruise — PM (beverages incl.)  ·  `2` Santorini Sailing — Half Day
> `3` None of these

Collect her answers into a resolutions file keyed by row number, then run the command
again with `--resolutions "<path>"`. Her choices are saved as aliases, so the same
phrasing prices itself next time.

## 3. Report the price changes

If the summary contains price changes, tell her plainly:

> Heads up — the Uffizi rate is €310 now. It was €285 when you mapped it.

## 4. Report what still needs a quote

Lines with status `needs_quote` are **not failures** — they're the engine refusing to
invent a number. Read the reason back to her:

> One line needs a manual quote: 14 pax on the Uffizi tour is above the highest rate in
> your sheet, which stops at 10. You'll need a group rate from the supplier.

## 5. Hand over the file

Give her the output filename and the summary. Include any warnings from the result
verbatim. Never restate a total you computed yourself — use the numbers in the result.

## Rules

- Never guess a match to avoid asking. A question costs her ten seconds; a wrong price
  costs her a client.
- Never fill a `needs_quote` cell with an estimate.
- If the engine reports that a sheet has changed shape, stop and tell her to run
  `/map` for that region. Do not work around it.
```

- [ ] **Step 4: Write the refresh skill**

Create `.claude/skills/refresh-rates/SKILL.md`:

```markdown
---
name: refresh-rates
description: Use when the operator runs /refresh, asks whether any prices have changed, or says she has updated her costing workbook.
---

# Refreshing rates

## 1. Sweep the catalog

`uv run python -m pricing.cli refresh`

## 2. Report changes as a list she can act on

> **3 rates have changed since you mapped them:**
> - Uffizi Gallery private tour: €285 → €310
> - Vatican Museums: €95 → €99
> - Rome airport transfer: €110 → €120

These are informational. The catalog reads live cells, so quotes are already using the
new numbers — nothing needs re-mapping because a price moved.

## 3. Report broken items as work she must do

Items under `broken_items` **cannot be priced at all** until they're re-mapped:

> **1 item needs re-mapping.** The Uffizi tour is no longer where it was in your Italy
> sheet — rows have been inserted or moved. Run `/map Italy` to fix it.

Be clear that this is different from a price change, and that until she fixes it those
lines won't price.

## 4. Suggest a verification

> Once you've re-mapped, run `/verify` on a recent trip you priced by hand to confirm
> everything still lines up.
```

- [ ] **Step 5: Write the seven commands**

Each command file is a one-line front door. Create `.claude/commands/profile.md`:

```markdown
---
description: Read my costing workbook and work out how its pricing is structured
---

Use the profile-rate-sheet skill. If the operator named a file, use it; otherwise ask
which workbook to read.
```

Create `.claude/commands/map.md`:

```markdown
---
description: Map one region's experiences so they can be priced automatically
---

Use the map-rate-sheet skill for the region named in $ARGUMENTS. If no region was named,
list the regions in her workbook and ask which one to map.
```

Create `.claude/commands/cost.md`:

```markdown
---
description: Fill in the cost sheet on an itinerary
---

Use the cost-itinerary skill. If the operator named a file, use it; otherwise ask her to
attach the itinerary.
```

Create `.claude/commands/refresh.md`:

```markdown
---
description: Check whether any of my rates have changed
---

Use the refresh-rates skill.
```

Create `.claude/commands/verify.md`:

```markdown
---
description: Check my pricing against a trip I already priced by hand
---

Run `uv run python -m pricing.cli verify --file "<path>"` on the itinerary named in
$ARGUMENTS, asking for it if not given.

Report the result plainly. Every line matching is the good outcome — say so clearly:
"All 12 lines match to the cent." For mismatches, show the row, the experience, what she
had, what the tool computed, and the difference. Do not speculate about which is right;
tell her a mismatch usually means that experience needs re-mapping, and offer to run
`/map` for its region.
```

Create `.claude/commands/doctor.md`:

```markdown
---
description: Check that everything is working
---

Run `uv run python -m pricing.cli doctor` and read every check back in plain language,
each on its own line with a tick or a cross. If anything failed, say what she should do
next. If she can't fix it herself, tell her to send the whole output to whoever supports
this tool.
```

Create `.claude/commands/update.md`:

```markdown
---
description: Get the latest version of the pricing tool
---

Run `git pull` in the project folder, then `uv sync`, then
`uv run python -m pricing.cli doctor`.

Report only whether the update worked and whether everything still checks out. Do not
show her git output.
```

- [ ] **Step 6: Commit**

```bash
git add .claude/
git commit -m "feat: skills and commands for the operator-facing workflow"
```

---

### Task 16: End-to-end walkthrough, setup docs, and README

**Files:**
- Create: `tests/test_end_to_end.py`
- Create: `SETUP.md`
- Create: `README.md`

**Interfaces:**
- Consumes: the whole system.
- Produces: nothing importable.

- [ ] **Step 1: Write the end-to-end test**

Create `tests/test_end_to_end.py`:

```python
"""The full journey, exercised the way the skills exercise it: CLI only."""

import json

from pricing.cli import main


def _run(capsys, argv):
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_profile_map_cost_verify(tmp_path, rate_sheet, itinerary, capsys):
    root = ["--root", str(tmp_path)]

    code, _ = _run(capsys, root + ["profile", "--workbook", str(rate_sheet)])
    assert code == 0

    code, out = _run(capsys, root + ["profile-itinerary", "--file", str(itinerary)])
    assert code == 0 and out["template"]["roles"]["cost"] == "E"

    item = tmp_path / "uffizi.json"
    item.write_text(json.dumps({
        "id": "IT-FLR-0032", "name": "Uffizi Gallery — Private Guided Tour",
        "name_cell": "Italy!A4", "region": "Italy", "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "tiered_by_pax", "tiers": [
            {"max_pax": 4, "cell": "Italy!D4", "last_seen": "285"},
            {"max_pax": 10, "cell": "Italy!D5", "last_seen": "240"}]},
        "modifiers": [{"type": "day_part", "when": ["PM"], "op": "add_per_unit",
                       "cell": "Italy!F4", "last_seen": "40"}],
        "source_rows": [4, 5],
        "row_fingerprint": "", "confirmed_at": "2026-09-03"}), encoding="utf-8")
    code, _ = _run(capsys, root + ["catalog-add", "--file", str(item)])
    assert code == 0

    code, out = _run(capsys, root + ["cost", "--file", str(itinerary)])
    assert code == 0
    assert out["summary"]["priced"] == 1
    assert out["summary"]["unmatched"] == 2
    uffizi = next(l for l in out["lines"] if l["row"] == 8)
    assert uffizi["total"] == "1300.00"

    code, out = _run(capsys, root + ["refresh"])
    assert code == 0 and out["checked"] == 1

    code, out = _run(capsys, root + ["doctor"])
    assert code == 0 and out["ok_all"] is True


def test_original_itinerary_is_never_modified(tmp_path, rate_sheet, itinerary, capsys):
    before = itinerary.read_bytes()
    root = ["--root", str(tmp_path)]
    _run(capsys, root + ["profile", "--workbook", str(rate_sheet)])
    _run(capsys, root + ["cost", "--file", str(itinerary)])
    assert itinerary.read_bytes() == before
```

- [ ] **Step 2: Run it**

Run: `uv run --extra dev pytest tests/test_end_to_end.py -v`
Expected: PASS, 2 passed

If `uffizi["total"]` comes back as a float rather than the string `"1300.00"`, the JSON
encoder is losing Decimal precision. Fix it in `cli.main`'s `default=str`, not in the test.

- [ ] **Step 3: Write `SETUP.md`**

Written for the operator. Must contain, in this order: what the tool does in two
sentences; the one-time install (install the Claude desktop app; install `uv` — give the
exact Mac and Windows commands; download the project folder); how to open the folder in
Claude; the instruction to run `/doctor` first and what a good result looks like; then
`/profile`, `/map`, `/cost` in order, one paragraph each. Finish with "If something goes
wrong": run `/doctor`, and send whoever supports this tool everything it prints.

No file paths in prose beyond the project folder name. No mention of Python, JSON, or git
anywhere in the document.

- [ ] **Step 4: Write `README.md`**

Written for a developer. Must contain: what the system does; the Claude-does-language /
Python-does-money principle; the module table from this plan's File Structure section;
how to run the tests (`uv run --extra dev pytest`); the CLI subcommand table from Task 13
plus `verify` and `refresh`; a note that `data/` is gitignored and holds proprietary
rates; and a pointer to the design spec at
`docs/superpowers/specs/2026-09-03-itinerary-pricing-design.md`.

- [ ] **Step 5: Run the whole suite one last time**

Run: `uv run --extra dev pytest -v`
Expected: PASS, all tests, no warnings about Decimal or float in pricing paths.

- [ ] **Step 6: Commit**

```bash
git add tests/test_end_to_end.py SETUP.md README.md
git commit -m "test: end-to-end walkthrough; docs: setup guide and README"
```

---

## Known risks

**Round-trip fidelity (Task 4).** If openpyxl drops embedded images, her costed itinerary
loses its logo. Task 4 measures this rather than assuming it, and Task 11 surfaces a
warning if so. If it turns out to matter to her, the fallback is to write the costs into
a copy she pastes from, rather than a copy she sends — a UX change, not an architecture
change.

**Header-row detection is a heuristic.** `find_header_row` takes the first row with three
or more text cells. Sheets with multi-row headers or a subtitle band will fool it. This is
mitigated by the operator confirming the profile in Phase 0.5, and it is why `/profile`
reads its findings back rather than proceeding silently.

**Fingerprints protect the name cell, not the rate cells.** If a rate column is inserted,
the name stays put and rates shift sideways undetected. If Phase 0 reveals that her sheets
get columns inserted regularly, extend the fingerprint to cover the header row — but do
not build that until the profile shows it's needed.

**Redaction is heuristic and conservative.** Unlabelled numeric columns are masked. If a
real sheet has an unlabelled column of pax counts, the profile will hide it and be less
useful — the safe direction to fail.

## Self-review

**Spec coverage:** every section of the design spec maps to a task — Phase 0 → Tasks 6, 7;
Phase 0.5 → Task 15's profiling skill; Phase 1 → Tasks 8, 15; Phase 2 → Tasks 9, 10, 11;
Phase 3 → Task 14; data model → Task 8; failure handling → Tasks 3, 5, 8, 10, 13; testing
→ Tasks 2, 4, 16; setup and support → Tasks 12, 15, 16.

**Deviation from the spec, deliberately:** the spec's four pricing patterns are implemented
as two orthogonal axes (pattern × unit, plus `min_billable_pax`), which covers all four
cases with fewer code paths. Task 5 documents the mapping. **The spec must be updated to
match before implementation begins.**

**Type consistency:** `CatalogItem.to_dict()` feeds `patterns.evaluate(item: dict, ...)`,
so the dataclass field names and the keys `evaluate` reads are the same names —
`unit`, `pricing`, `modifiers`, `currency`, `min_billable_pax`. `PricedLine.status` uses
exactly three values (`priced`, `needs_quote`, `unmatched`) in Tasks 10, 11, 14.
`ItineraryTemplate.roles` keys are `name`, `date`, `pax`, `day_part`, `cost` in Tasks 7,
10, 11, 14.
