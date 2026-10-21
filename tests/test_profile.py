import json
from pathlib import Path

import openpyxl

from pricing.profile import profile_sheet, profile_workbook, to_dict
from pricing.workbook import Workbook


def _build_substring_collision_sheet(path: Path) -> Path:
    """Sheet testing count-word substring collisions (age in Beverage, min in Minibar)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Collisions"
    ws["A1"] = "ADVERSARIAL HEADERS"
    for col, header in zip("ABCDE", ["Experience", "Beverage", "Minibar", "Min Spend", "Min Pax"]):
        ws[f"{col}2"] = header
    # Row 3: Beverage with price values
    ws["A3"], ws["B3"], ws["C3"], ws["D3"], ws["E3"] = "Item 1", 15, 20, 150.00, 2
    # Row 4: Minibar with price values
    ws["A4"], ws["B4"], ws["C4"], ws["D4"], ws["E4"] = "Item 2", 12, 18, 2500.00, 4
    wb.save(path)
    return path


def test_finds_the_header_row_below_a_title_block(rate_sheet):
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    assert profile.header_row == 3


def test_captures_headers_verbatim_in_memory(rate_sheet):
    """Headers are still populated on the in-memory ColumnProfile for local use."""
    wb = Workbook(rate_sheet)
    profile = profile_sheet(wb, "Italy")
    headers = [c.header for c in profile.columns]
    assert "Experience" in headers
    assert "Net Rate" in headers
    assert "PM Supplement" in headers


def test_pax_band_headers_captured_verbatim_in_memory(wide_rate_sheet):
    """Task 7b's input contract: pax-band headers must survive in memory."""
    wb = Workbook(wide_rate_sheet)
    profile = profile_sheet(wb, "Japan")
    headers = [c.header for c in profile.columns]
    assert "1-4 Pax" in headers
    assert "5-10 Pax" in headers
    assert "11+ Pax" in headers


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
    """Over-redaction would make the profile useless. Counts must survive in memory."""
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


def test_substring_collisions_beverage_is_price_bearing(tmp_path: Path):
    """Beverage (contains 'age') must be marked price_bearing to prevent leak."""
    sheet_path = _build_substring_collision_sheet(tmp_path / "collisions.xlsx")
    wb = Workbook(sheet_path)
    profile = profile_sheet(wb, "Collisions")
    by_header = {c.header: c for c in profile.columns}
    assert by_header["Beverage"].price_bearing is True


def test_substring_collisions_minibar_is_price_bearing(tmp_path: Path):
    """Minibar (contains 'min') must be marked price_bearing to prevent leak."""
    sheet_path = _build_substring_collision_sheet(tmp_path / "collisions.xlsx")
    wb = Workbook(sheet_path)
    profile = profile_sheet(wb, "Collisions")
    by_header = {c.header: c for c in profile.columns}
    assert by_header["Minibar"].price_bearing is True


def test_min_pax_remains_not_redacted(tmp_path: Path):
    """Min Pax (token match + plausible counts) must stay non-price-bearing and sampled."""
    sheet_path = _build_substring_collision_sheet(tmp_path / "collisions.xlsx")
    wb = Workbook(sheet_path)
    profile = profile_sheet(wb, "Collisions")
    by_header = {c.header: c for c in profile.columns}
    assert by_header["Min Pax"].price_bearing is False
    assert by_header["Min Pax"].sample_values  # non-empty


def test_min_spend_with_large_decimals_is_price_bearing(tmp_path: Path):
    """Min Spend (token match, but large decimals) must be marked price_bearing."""
    sheet_path = _build_substring_collision_sheet(tmp_path / "collisions.xlsx")
    wb = Workbook(sheet_path)
    profile = profile_sheet(wb, "Collisions")
    by_header = {c.header: c for c in profile.columns}
    assert by_header["Min Spend"].price_bearing is True


def test_serialized_profile_has_no_header_or_sample_values(rate_sheet):
    """The shareable dict shape carries no header text and no sample_values key."""
    wb = Workbook(rate_sheet)
    out = to_dict(profile_workbook(wb))
    for sheet in out["sheets"]:
        assert "header" not in sheet
        for column in sheet["columns"]:
            assert "header" not in column
            assert "sample_values" not in column
            assert "header_masked" not in column


def test_serialized_profile_columns_carry_only_structural_keys(rate_sheet):
    wb = Workbook(rate_sheet)
    out = to_dict(profile_workbook(wb))
    expected_keys = {"letter", "fill_rate", "distinct_count", "kind", "price_bearing"}
    for sheet in out["sheets"]:
        for column in sheet["columns"]:
            assert set(column.keys()) == expected_keys


def test_serialized_profile_sheets_carry_only_structural_keys(rate_sheet):
    """Mirrors the column-level key-set pin so a future field added to
    _sheet_to_dict cannot slip cell content through unnoticed."""
    wb = Workbook(rate_sheet)
    out = to_dict(profile_workbook(wb))
    expected_keys = {"name", "max_row", "max_column", "header_row",
                      "header_row_candidates", "merged_ranges", "formula_cells",
                      "data_blocks", "columns"}
    for sheet in out["sheets"]:
        assert set(sheet.keys()) == expected_keys


def test_sheet_name_is_included_deliberately(tmp_path: Path):
    """Sheet names ARE included in the artifact -- this is intentional, not
    an oversight. See the module docstring on pricing.profile: a sheet name
    is workbook organisation (the operator's region names), not cell data,
    and the artifact would be unintelligible without it. Even a tab name
    that happens to contain a number (as a real region name might, e.g. a
    year) is expected to survive into the shareable profile verbatim; an
    operator with a genuinely sensitive tab name should rename the tab
    rather than rely on this module to hide it."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Acme Tours 2026 Net 4500"
    ws["A2"], ws["B2"], ws["C2"] = "Experience", "Col2", "Col3"
    ws["A3"], ws["B3"], ws["C3"] = "data1", "data2", "data3"
    path = tmp_path / "named.xlsx"
    wb.save(path)

    wb = Workbook(path)
    out = to_dict(profile_workbook(wb))
    blob = json.dumps(out)
    assert out["sheets"][0]["name"] == "Acme Tours 2026 Net 4500"
    assert "Acme Tours 2026 Net 4500" in blob


def _assert_no_cell_content_leaked(path: Path) -> None:
    """Shared by the fixture sweep and the phantom-leak regression test.

    String-typed cell content is checked against the whole serialized blob.
    Numeric cell content is checked more carefully: the blob legitimately
    contains structural integers (max_row, max_column, header_row, every
    data_blocks bound, every distinct_count, formula_cells) that have
    nothing to do with cell values, so a numeric cell whose text happens to
    equal one of those (e.g. a sheet with 12 rows and a cell reading "12")
    must not be flagged as a phantom leak. Those structural integers are
    the only fields excluded -- there is no blanket exclusion list, and
    string content still gets the exhaustive whole-blob check.
    """
    profiles = profile_workbook(Workbook(path))
    out = to_dict(profiles)
    blob = json.dumps(out)

    structural_ints: set[str] = set()
    for sheet in out["sheets"]:
        structural_ints.add(str(sheet["max_row"]))
        structural_ints.add(str(sheet["max_column"]))
        if sheet["header_row"] is not None:
            structural_ints.add(str(sheet["header_row"]))
        for bounds in sheet["data_blocks"]:
            for bound in bounds:
                structural_ints.add(str(bound))
        structural_ints.add(str(sheet["formula_cells"]))
        for column in sheet["columns"]:
            structural_ints.add(str(column["distinct_count"]))

    raw = openpyxl.load_workbook(path)
    for sheet in raw.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                text = str(cell.value).strip()
                if len(text) < 2:
                    continue
                is_numeric = isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool)
                if is_numeric and text in structural_ints:
                    # Ambiguous with a legitimate structural integer -- not
                    # proof of a leak. Real leaks of multi-digit rates are
                    # still caught: a genuine price like 285 essentially
                    # never coincides with a row/column count, a header row
                    # index, a data-block bound, a distinct_count, or a
                    # formula count across these fixtures, and the string-
                    # content check still runs unconditionally for every
                    # non-numeric cell.
                    continue
                assert text not in blob, (
                    f"{path.name}!{sheet.title}!{cell.coordinate} "
                    f"leaked {text!r} into the shareable profile")
    raw.close()


def test_serialized_profile_contains_no_cell_content(rate_sheet, wide_rate_sheet,
                                                     stacked_rate_sheet, nasty_sheet,
                                                     multiheader_sheet):
    """Nothing derived from any cell may appear in the shareable artifact."""
    for path in [rate_sheet, wide_rate_sheet, stacked_rate_sheet,
                 nasty_sheet, multiheader_sheet]:
        _assert_no_cell_content_leaked(path)


def test_no_cell_content_check_does_not_false_positive_on_structural_coincidence(tmp_path: Path):
    """Regression test for a specific false-positive the reviewer found: a
    sheet with 12 data rows (so max_row == 12) whose last data cell's text
    is the numeric value 12. A naive "cell text must not appear anywhere in
    the blob" check flags this as a phantom leak, because "12" legitimately
    appears in the blob as max_row. That reflex -- when the test cries
    wolf, the fix is to raise the length guard or add an exclusion list --
    is exactly what would erode the real protection over time, so this is
    pinned as a permanent regression test rather than left to be
    rediscovered."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test"
    ws["A2"], ws["B2"], ws["C2"] = "Experience", "Col2", "Col3"
    for r in range(3, 12):
        ws[f"A{r}"] = f"item{r}"
        ws[f"B{r}"] = "x"
        ws[f"C{r}"] = "y"
    ws["A12"] = 12  # numeric cell whose text coincides with max_row == 12
    ws["B12"] = "x"
    ws["C12"] = "y"
    path = tmp_path / "phantom_leak.xlsx"
    wb.save(path)

    # Sanity check that the scenario is real: "12" does appear in the blob
    # (as max_row), so a naive whole-blob string check would have failed.
    profiles = profile_workbook(Workbook(path))
    out = to_dict(profiles)
    assert out["sheets"][0]["max_row"] == 12
    assert "12" in json.dumps(out)

    # The real check must not raise on this sheet.
    _assert_no_cell_content_leaked(path)
