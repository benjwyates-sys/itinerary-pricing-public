import json

import pytest

from pricing.itinerary_profile import (
    MissingRoleError,
    load_template,
    propose_template,
    save_template,
    template_fits,
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


def test_load_template_ignores_a_persisted_default_pax(itinerary, tmp_path):
    """CRITICAL regression (code review): a template.json written before
    this fix (or hand-edited) may still carry a persisted default_pax --
    load_template must keep parsing it (the field stays on the dataclass)
    but never hand a persisted party size back to a caller for pricing.
    A template describes a SHAPE that is legitimately reused across
    different clients' files; a party size is data about one client's
    booking and must never travel with it."""
    wb = Workbook(itinerary)
    template = propose_template(wb, "Itinerary")
    path = tmp_path / "template.json"
    save_template(template, path)

    # Simulate an old file (or one written by an older version of the
    # tool) that persisted a party size.
    data = json.loads(path.read_text(encoding="utf-8"))
    data["default_pax"] = 2
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_template(path)
    assert loaded.default_pax is None


def test_token_matching_prevents_substring_collisions_day_vs_date(tmp_path):
    """When 'Date' column exists, it wins over 'Day' (keyword priority)."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    # Header row with Day in A, Experience in B, Date in C
    ws["A7"] = "Day"
    ws["B7"] = "Experience"
    ws["C7"] = "Date"
    ws["D7"] = "Pax"
    ws["E7"] = "Cost"
    # Add data below header to establish it as header row
    ws["A8"] = "Day 1"
    ws["B8"] = "Hotel"
    ws["C8"] = "2025-01-01"
    ws["D8"] = "2"
    ws["E8"] = "100"

    path = tmp_path / "day_vs_date.xlsx"
    wb_raw.save(path)

    template = propose_template(Workbook(path), "Itinerary")
    # 'date' role should match column C (Date), not column A (Day), because 'date' keyword has higher priority
    assert template.roles["date"] == "C"


def test_day_keyword_matches_when_date_keyword_not_present(tmp_path):
    """When only 'Day' column exists (no 'Date'), it matches the date role."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    ws["A7"] = "Experience"
    ws["B7"] = "Day"
    ws["C7"] = "Pax"
    ws["D7"] = "Cost"
    ws["A8"] = "Hotel"
    ws["B8"] = "2025-01-01"
    ws["C8"] = "2"
    ws["D8"] = "100"

    path = tmp_path / "day_only.xlsx"
    wb_raw.save(path)

    template = propose_template(Workbook(path), "Itinerary")
    # 'date' role should resolve to B (Day) because it's the only date-related column
    assert template.roles["date"] == "B"


def test_token_matching_prevents_substring_collisions_holiday(tmp_path):
    """'Holiday' header should NOT match 'date' role."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    ws["A7"] = "Holiday"
    ws["B7"] = "Experience"
    ws["C7"] = "Cost"
    ws["A8"] = "Christmas"
    ws["B8"] = "Hotel"
    ws["C8"] = "100"

    path = tmp_path / "holiday.xlsx"
    wb_raw.save(path)

    template = propose_template(Workbook(path), "Itinerary")
    # 'date' role should not be found, only 'name' and 'cost'
    assert "date" not in template.roles
    assert template.roles["name"] == "B"
    assert template.roles["cost"] == "C"


def test_token_matching_prevents_substring_collisions_update(tmp_path):
    """'Update' header should NOT match 'date' role."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    ws["A7"] = "Update"
    ws["B7"] = "Experience"
    ws["C7"] = "Cost"
    ws["A8"] = "2025-01-01"
    ws["B8"] = "Hotel"
    ws["C8"] = "100"

    path = tmp_path / "update.xlsx"
    wb_raw.save(path)

    template = propose_template(Workbook(path), "Itinerary")
    # 'date' role should not be found
    assert "date" not in template.roles


def test_token_matching_prevents_substring_collisions_supplier_pax(tmp_path):
    """'Supplier' header should NOT match 'pax' role."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    ws["A7"] = "Activity"
    ws["B7"] = "Supplier"
    ws["C7"] = "Cost"
    ws["A8"] = "Hotel"
    ws["B8"] = "ABC Corp"
    ws["C8"] = "100"

    path = tmp_path / "supplier.xlsx"
    wb_raw.save(path)

    template = propose_template(Workbook(path), "Itinerary")
    # 'pax' role should not be found (Supplier doesn't contain pax token)
    assert "pax" not in template.roles
    assert template.roles["name"] == "A"
    assert template.roles["cost"] == "C"


def test_cost_keyword_priority_rate_over_total(tmp_path):
    """'rate' keyword has higher priority than 'total', so Rate column wins over Total."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    ws["A7"] = "Experience"
    ws["B7"] = "Date"
    ws["C7"] = "Pax"
    ws["D7"] = "Total"
    ws["E7"] = "Rate"
    # Populate Total column (sum/grand total)
    ws["D8"] = "500"
    ws["D9"] = "750"
    # Leave Rate column empty (this is where prices go)
    ws["A8"] = "Hotel"
    ws["B8"] = "2025-01-01"
    ws["C8"] = "2"

    path = tmp_path / "total_vs_rate.xlsx"
    wb_raw.save(path)

    template = propose_template(Workbook(path), "Itinerary")
    # 'cost' role should resolve to E (Rate) because 'rate' keyword has higher priority than 'total'
    assert template.roles["cost"] == "E"


def test_empty_cost_column_preferred_over_populated_in_tie(tmp_path):
    """When two columns match the SAME cost keyword (a tie), prefer empty over populated."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    ws["A7"] = "Experience"
    ws["B7"] = "Cost"
    ws["C7"] = "Net Cost"
    ws["A8"] = "Hotel"
    ws["B8"] = "500"
    # C8 (Net Cost) is left empty - this is where line-item prices should go
    ws["C8"] = None

    path = tmp_path / "cost_vs_net_cost.xlsx"
    wb_raw.save(path)

    template = propose_template(Workbook(path), "Itinerary")
    # Both B and C match 'cost' keyword at same priority, but C (Net Cost) is empty
    # so it should be chosen as the column to fill
    assert template.roles["cost"] == "C"


def test_missing_cost_still_raises_error_with_total_column(tmp_path):
    """When neither 'cost', 'net', 'rate', 'price' found, must raise error."""
    import openpyxl

    wb_raw = openpyxl.Workbook()
    ws = wb_raw.active
    ws.title = "Itinerary"
    ws["A7"] = "Experience"
    ws["B7"] = "Date"
    ws["C7"] = "Notes"  # No cost-related header
    ws["A8"] = "Hotel"
    ws["B8"] = "2025-01-01"
    ws["C8"] = "Good place"

    path = tmp_path / "no_cost_columns.xlsx"
    wb_raw.save(path)

    with pytest.raises(MissingRoleError) as exc:
        propose_template(Workbook(path), "Itinerary")
    assert "cost" in exc.value.missing


# --- C4: default_pax is never set automatically ---------------------------

def test_propose_template_never_sets_default_pax(itinerary, wide_itinerary):
    """propose_template must never guess a party size -- default_pax stays
    None until an operator (or the CLI's --default-pax flag) sets it
    explicitly, on every itinerary shape, including the one with no pax
    column at all."""
    assert propose_template(Workbook(itinerary), "Itinerary").default_pax is None
    assert propose_template(Workbook(wide_itinerary), "Itinerary").default_pax is None


def test_wide_itinerary_confidence_is_low(wide_itinerary):
    template = propose_template(Workbook(wide_itinerary), "Itinerary")
    assert template.confidence == "low"


# --- C3(b): template_fits sanity-checks a saved template against a
# possibly-different file before it's reused -------------------------------

def test_template_fits_the_file_it_was_confirmed_on(itinerary):
    wb = Workbook(itinerary)
    template = propose_template(wb, "Itinerary")
    assert template_fits(wb, template) is True


def test_template_does_not_fit_a_missing_sheet(itinerary, day_grouped_itinerary):
    template = propose_template(Workbook(itinerary), "Itinerary")
    template.sheet = "NoSuchSheet"
    assert template_fits(Workbook(day_grouped_itinerary), template) is False


def test_template_does_not_fit_when_header_row_is_beyond_the_sheet(itinerary, minimal_itinerary):
    template = propose_template(Workbook(itinerary), "Itinerary")  # header_row == 7
    # minimal_itinerary only has 3 rows total -- header_row 7 is out of bounds.
    assert template_fits(Workbook(minimal_itinerary), template) is False


def test_template_does_not_fit_a_differently_shaped_itinerary(itinerary, day_grouped_itinerary):
    """The exact scenario from the review: a template confirmed on the
    flat `itinerary` fixture (header row 7) does not describe the
    day-grouped itinerary (header row 5, headings interleaved) -- reading
    the flat template's roles at row 7 of the day-grouped file lands on a
    real data row, not a header, and its cost column (E) is blank there."""
    template = propose_template(Workbook(itinerary), "Itinerary")
    assert template_fits(Workbook(day_grouped_itinerary), template) is False


def test_template_fits_the_same_shape_reused_on_a_different_file(itinerary, tmp_path):
    """A template DOES still fit a different file with the identical
    layout -- template_fits is about shape, not identity."""
    from tests.fixtures import build
    other = build.build_itinerary(tmp_path / "Trip_Other.xlsx")
    template = propose_template(Workbook(itinerary), "Itinerary")
    assert template_fits(Workbook(other), template) is True
