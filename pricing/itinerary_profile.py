"""Phase 0 for the itinerary side: where do line items live, and which
column is the empty one we fill in?

Guesses are proposals only. The operator confirms them once, and the
confirmed template is what makes Phase 2 deterministic.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from openpyxl.utils import column_index_from_string, get_column_letter

from pricing.profile import find_header_row, _tokenize_header
from pricing.workbook import CellRef, Workbook

ROLE_WORDS: dict[str, tuple[str, ...]] = {
    "name": ("experience", "service", "item", "activity", "description", "tour"),
    "date": ("date", "day"),  # "date" first (higher priority); token matching prevents "day" from matching Holiday, Sunday, etc.
    "pax": ("pax", "guests", "people", "persons", "qty", "quantity", "adults"),
    "day_part": ("time", "am/pm", "when", "departure", "slot"),
    "cost": ("cost", "net", "rate", "price", "amount", "total"),
}

REQUIRED_ROLES = ("name", "cost")


class MissingRoleError(Exception):
    def __init__(self, missing: list[str], reason: str | None = None) -> None:
        if reason is None:
            reason = "Could not find these columns in the itinerary"
        message = f"{reason}: {', '.join(missing)}"
        super().__init__(message)
        self.missing = missing


@dataclass
class ItineraryTemplate:
    sheet: str
    header_row: int
    first_data_row: int
    roles: dict[str, str]
    # "high" means a pax column was found -- NOT that every role was found.
    # date/day_part are optional and are not reflected in this value; see
    # propose_template.
    confidence: str = "high"
    alternatives: dict[str, list[str]] = field(default_factory=dict)
    default_pax: int | None = None


def propose_template(wb: Workbook, sheet: str) -> ItineraryTemplate:
    max_row, max_col = wb.dimensions(sheet)
    header_row = find_header_row(wb, sheet, max_row, max_col)
    if header_row is None:
        raise MissingRoleError(list(REQUIRED_ROLES), reason="Could not find a header row")

    first_data_row = header_row + 1
    headers = {
        get_column_letter(col): str(wb.read(CellRef(sheet, get_column_letter(col), header_row)) or "")
        for col in range(1, max_col + 1)
    }

    roles: dict[str, str] = {}
    for role, words in ROLE_WORDS.items():
        matched_letter = None
        # Process keywords in order: most specific first
        for word in words:
            candidates = []
            for letter, header in headers.items():
                tokens = _tokenize_header(header)
                # Token-based matching: word must be a complete token, not a substring
                if word in tokens and letter not in roles.values():
                    candidates.append(letter)

            if candidates:
                # Found matches for this keyword; use them and don't check other keywords
                if role == "cost" and len(candidates) > 1:
                    # Prefer empty columns for cost (the column we fill with prices).
                    # The rightmost empty column is preferred.
                    matched_letter = _prefer_empty_cost_column(wb, sheet, candidates, first_data_row, max_row)
                else:
                    # For other roles, just take the first match
                    matched_letter = candidates[0]
                break

        if matched_letter:
            roles[role] = matched_letter

    missing = [r for r in REQUIRED_ROLES if r not in roles]
    if missing:
        raise MissingRoleError(missing, reason="Could not find these column headers in the itinerary")

    # Other columns that plausibly fill each role, for the skill to offer
    # the operator as alternatives to the one we picked.
    alternatives = {
        role: [letter for letter, header in headers.items()
               if header.strip().lower()
               and any(word in _tokenize_header(header) for word in words)
               and roles.get(role) != letter]
        for role, words in ROLE_WORDS.items()
    }

    # 'pax' is not required to find the template, but without it we cannot
    # price anything until the operator tells us the party size.
    confidence = "high" if "pax" in roles else "low"

    return ItineraryTemplate(sheet, header_row, first_data_row, roles,
                             confidence, alternatives)


def template_fits(wb: Workbook, template: ItineraryTemplate) -> bool:
    """C3 (code review): a saved template only describes the file it was
    confirmed on. `data/profiles/itinerary_template.json` is a single
    global file that gets reused for every itinerary /cost is pointed at
    -- if the next file is shaped differently (a different sheet name, a
    different column layout entirely), the saved column letters silently
    point at the wrong cells and real lines vanish with no error at all
    (reproduced: costing a day-grouped itinerary with a flat itinerary's
    template silently priced 1 of 2 lines and dropped the other).

    This is a cheap sanity check, not a full re-validation: the template's
    sheet must still exist in this workbook, its header row must be
    within the sheet's current bounds, and every column it mapped a role
    to must still hold non-blank text at that header row. Any of those
    failing means "this template does not describe this file" -- the
    caller should fall back to propose_template for this file instead of
    trusting stale column letters.
    """
    if template.sheet not in wb.sheet_names():
        return False

    max_row, max_col = wb.dimensions(template.sheet)
    if template.header_row < 1 or template.header_row > max_row:
        return False

    for letter in template.roles.values():
        if column_index_from_string(letter) > max_col:
            return False
        value = wb.read(CellRef(template.sheet, letter, template.header_row))
        if value is None or not str(value).strip():
            return False

    return True


def _prefer_empty_cost_column(wb: Workbook, sheet: str, candidates: list[str],
                               first_data_row: int, max_row: int) -> str:
    """For cost column, prefer empty cells over populated ones, then rightmost.

    The cost column is the one we fill with prices. An empty column signals
    it's ready for data. Among equally empty columns, rightmost is preferred.
    """
    empty_cols = []
    populated_cols = []

    for letter in candidates:
        is_empty = True
        for row in range(first_data_row, max_row + 1):
            value = wb.read(CellRef(sheet, letter, row))
            if value is not None and str(value).strip():
                is_empty = False
                break
        if is_empty:
            empty_cols.append(letter)
        else:
            populated_cols.append(letter)

    # Prefer empty columns (rightmost), then populated columns (rightmost)
    if empty_cols:
        return max(empty_cols)  # max() on letters gives rightmost (Z > A)
    else:
        return max(populated_cols)


def save_template(template: ItineraryTemplate, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(template), indent=2), encoding="utf-8")


def load_template(path: Path) -> ItineraryTemplate:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    template = ItineraryTemplate(**data)
    # C4-regression (code review): a template describes a SHAPE and is
    # legitimately reused across files with template_fits (see its
    # docstring -- deliberately shape-based, not identity-based); a party
    # size is data about one client's booking and must never travel with
    # it. A saved template.json from before this fix may still carry a
    # persisted default_pax -- it is ignored here, unconditionally, so an
    # old file keeps loading (the field stays on the dataclass) but can
    # never silently apply one client's party size to a different
    # client's itinerary just because the two happen to be shaped the
    # same. The only source of default_pax now is `cost --default-pax`,
    # supplied fresh for the run it's used in.
    template.default_pax = None
    return template
