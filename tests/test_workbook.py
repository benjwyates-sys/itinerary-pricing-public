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


def test_cellref_roundtrips_with_space():
    """CellRef round-trips a sheet name with a space."""
    ref = CellRef.parse("'South Africa'!AB7")
    assert (ref.sheet, ref.column, ref.row) == ("South Africa", "AB", 7)
    assert str(ref) == "'South Africa'!AB7"
    assert CellRef.parse(str(ref)) == ref


def test_cellref_roundtrips_with_apostrophe():
    """CellRef round-trips a sheet name with an apostrophe (doubled in quoted form)."""
    ref = CellRef.parse("'O''Hare'!D4")
    assert (ref.sheet, ref.column, ref.row) == ("O'Hare", "D", 4)
    assert str(ref) == "'O''Hare'!D4"
    assert CellRef.parse(str(ref)) == ref


def test_cellref_roundtrips_with_space_and_apostrophe():
    """CellRef round-trips a sheet name with both space and apostrophe."""
    ref = CellRef.parse("'Côte d''Azur'!XY99")
    assert (ref.sheet, ref.column, ref.row) == ("Côte d'Azur", "XY", 99)
    assert str(ref) == "'Côte d''Azur'!XY99"
    assert CellRef.parse(str(ref)) == ref


def test_cellref_roundtrips_three_letter_column():
    """CellRef round-trips a three-letter column reference."""
    ref = CellRef.parse("Italy!ABC123")
    assert (ref.sheet, ref.column, ref.row) == ("Italy", "ABC", 123)
    assert str(ref) == "Italy!ABC123"
    assert CellRef.parse(str(ref)) == ref


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


def test_is_formula_detects_formulas(formula_sheet):
    """is_formula() returns True for formula cells and False for literals."""
    wb = Workbook(formula_sheet)
    # C2 contains a formula
    assert wb.is_formula(CellRef.parse("Rates!C2")) is True
    # C3 contains a literal value
    assert wb.is_formula(CellRef.parse("Rates!C3")) is False
    wb.close()


def test_formula_cells_have_no_cached_value(formula_sheet):
    """Formulas that weren't computed by Excel have None as cached value.

    This is a real-world hazard: openpyxl loads with data_only=True returns
    None for formulas that haven't been computed and cached by Excel. When a
    formula is newly added (not calculated by Excel yet), read() returns None
    even though the formula exists. Only formulas computed by Excel have
    cached values.
    """
    wb = Workbook(formula_sheet)
    # C2 has a formula that was not pre-computed by Excel (we just created it)
    formula_value = wb.read(CellRef.parse("Rates!C2"))
    # The cached value is None because the formula was never computed
    assert formula_value is None
    wb.close()


def test_save_raises_friendly_error_when_locked(formula_sheet, monkeypatch):
    """save() raises WorkbookLockedError when the file is locked."""
    wb = Workbook(formula_sheet)
    wb.write(CellRef.parse("Rates!B2"), 999)

    # Monkeypatch openpyxl's save to raise PermissionError
    original_save = wb._formulas.save

    def deny(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    wb._formulas.save = deny

    with pytest.raises(WorkbookLockedError) as exc:
        wb.save()
    assert "close" in str(exc.value).lower()
    assert formula_sheet.name in str(exc.value)

    wb.close()
