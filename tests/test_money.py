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


# --- I4: a lone dot + exactly 3 trailing digits is ambiguous -------------
#
# "1.250" could be the European thousands separator (1250) or a literal
# fraction (1.25) -- there is no comma anywhere to disambiguate it, so
# guessing either way risks a silent 1000x mispricing. This must raise,
# never guess, while ordinary two-decimal amounts and fully-disambiguated
# European/US notation keep working exactly as before.

@pytest.mark.parametrize(
    "raw",
    ["1.250", "€1.250", "12.500", "1.234", "-1.250"],
)
def test_lone_dot_with_three_trailing_digits_is_ambiguous(raw):
    with pytest.raises(MoneyParseError):
        parse_money(raw)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.25", Decimal("1.25")),          # ordinary two-decimal amount
        ("1.2500", Decimal("1.2500")),      # four trailing digits: not the ambiguous shape
        ("1.234,50", Decimal("1234.50")),   # European: comma present, unambiguous
        ("1,234.50", Decimal("1234.50")),   # US: comma present, unambiguous
    ],
)
def test_unambiguous_dot_shapes_still_parse(raw, expected):
    assert parse_money(raw) == expected


def test_float_input_does_not_leak_binary_error():
    # Excel hands back floats; 0.1 + 0.2 must not become 0.30000000000000004
    assert parse_money(0.1) + parse_money(0.2) == Decimal("0.3")


def test_round_money_uses_half_up():
    assert round_money(Decimal("2.345")) == Decimal("2.35")
    assert round_money(Decimal("2.344")) == Decimal("2.34")
