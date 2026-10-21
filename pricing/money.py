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

# A lone dot followed by exactly three digits at the end of the string,
# with no comma anywhere, is genuinely ambiguous: "1.250" could be the
# European thousands separator (1250) or a literal fraction (1.25). We
# never guess -- see _normalise_separators below for the unambiguous
# cases this deliberately does NOT cover (two-decimal amounts like
# "1.25", and anything where a comma is also present).
_AMBIGUOUS_DOT_THOUSANDS = re.compile(r"^-?\d+\.\d{3}$")


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

    if "," not in cleaned and _AMBIGUOUS_DOT_THOUSANDS.match(cleaned):
        raise MoneyParseError(
            f"ambiguous number {value!r} -- could be a thousands separator "
            f"({cleaned.replace('.', '')}) or a fraction ({cleaned}). "
            "Please confirm the actual rate."
        )

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
