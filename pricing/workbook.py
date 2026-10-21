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

class WorkbookLockedError(RuntimeError):
    """The file is open in Excel, or otherwise not writable."""


@dataclass(frozen=True)
class CellRef:
    sheet: str
    column: str
    row: int

    @classmethod
    def parse(cls, ref: str) -> "CellRef":
        ref = ref.strip()

        # Parse sheet name (quoted or unquoted)
        if ref.startswith("'"):
            # Quoted sheet name: 'name'!col row
            # Within quotes, '' represents a single apostrophe
            end_idx = 1
            while end_idx < len(ref):
                if ref[end_idx] == "'":
                    # Check what follows the quote
                    if end_idx + 1 < len(ref) and ref[end_idx + 1] == "!":
                        # Found the closing quote followed by !
                        sheet = ref[1:end_idx].replace("''", "'")
                        rest = ref[end_idx + 2:]  # Skip the '!
                        break
                    elif end_idx + 1 < len(ref) and ref[end_idx + 1] == "'":
                        # Doubled apostrophe, skip both
                        end_idx += 2
                    else:
                        # Single quote not followed by ! or another quote
                        raise ValueError(f"not a cell reference: {ref!r}")
                else:
                    end_idx += 1
            else:
                # Reached end of string without finding closing '!
                raise ValueError(f"not a cell reference: {ref!r}")
        else:
            # Unquoted sheet name: everything before !
            if "!" not in ref:
                raise ValueError(f"not a cell reference: {ref!r}")
            parts = ref.split("!", 1)
            sheet = parts[0]
            rest = parts[1]

        # Parse column and row from rest
        match = re.match(r"^([A-Z]{1,3})(\d+)$", rest)
        if not match:
            raise ValueError(f"not a cell reference: {ref!r}")

        return cls(sheet, match.group(1).upper(), int(match.group(2)))

    def __str__(self) -> str:
        # Quote the sheet name if it contains ', space, or !
        if "'" in self.sheet or " " in self.sheet or "!" in self.sheet:
            # Double any apostrophes in the sheet name
            quoted_sheet = self.sheet.replace("'", "''")
            return f"'{quoted_sheet}'!{self.column}{self.row}"
        else:
            return f"{self.sheet}!{self.column}{self.row}"

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
        """Write a value to a cell. The change is buffered until save().

        Note: read() after write() on the same instance returns the stale
        pre-write value until save() and reopen.
        """
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


_MISSING_SHEET_RE = re.compile(r"^Worksheet (.+) does not exist\.$")


def missing_sheet_name(exc: KeyError) -> str | None:
    """If `exc` is the KeyError openpyxl raises for a sheet lookup miss
    (`workbook[name]` on an unknown sheet raises exactly
    `KeyError("Worksheet <name> does not exist.")`), return `<name>`.
    Otherwise return None.

    Two callers (pricing/cli.py's _friendly, pricing/cost.py's malformed-
    catalog-item reason) used to treat every bare KeyError as this case,
    which produced a confidently wrong message for a KeyError from
    somewhere else entirely (a template missing a role, a catalog item
    missing a dict key) -- and, even when it genuinely was this case,
    read the raw openpyxl sentence back at the operator instead of just
    the sheet name (`exc.args[0]` is the whole sentence, not a bare
    name). This is the one place both problems get fixed, so neither
    caller can regress independently.
    """
    if not exc.args or not isinstance(exc.args[0], str):
        return None
    match = _MISSING_SHEET_RE.match(exc.args[0])
    return match.group(1) if match else None
