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


def test_empty_tiered_pricing_needs_a_quote():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {
            "pattern": "tiered_by_pax",
            "tiers": [],
        },
        "modifiers": [],
    }
    with pytest.raises(NeedsQuote) as exc:
        evaluate(item, {}, PricingRequest(pax=2))
    assert "no rates mapped" in exc.value.reason.lower()


def test_unrecognized_unit_raises_needs_quote():
    item = {
        "currency": "EUR",
        "unit": "per_prson",  # typo
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [],
    }
    with pytest.raises(NeedsQuote) as exc:
        evaluate(item, {"X!A1": Decimal("100")}, PricingRequest(pax=2))
    assert "per_prson" in exc.value.reason


# --- C1: a non-positive total must never be silently quoted --------------
#
# `test_zero_multiplier_factor_produces_zero_total` used to assert that a
# `multiply` factor of 0 yields exactly Decimal("0.00") and does NOT raise.
# That encoded the old belief that a comped item is a legitimate price. It
# is not: `0` written into a client's quote is indistinguishable from a
# real price of zero, and both a placeholder rate cell and a genuine comp
# must be confirmed by a human, never quoted silently. This is now the
# blanket invariant: any total that rounds to <= 0, however it got there,
# raises NeedsQuote instead of returning a PricingResult.


def test_zero_multiplier_factor_needs_a_quote():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [
            {"type": "day_of_week", "when": ["MON"], "op": "multiply", "factor": "0"}
        ],
    }
    monday = date(2026, 6, 15)
    with pytest.raises(NeedsQuote) as exc:
        evaluate(item, {"X!A1": Decimal("100")}, PricingRequest(pax=2, date=monday))
    assert "0" in exc.value.reason


def test_pax_zero_needs_a_quote():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [],
    }
    with pytest.raises(NeedsQuote):
        evaluate(item, {"X!A1": Decimal("100")}, PricingRequest(pax=0))


def test_zero_rate_cell_needs_a_quote():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [],
    }
    with pytest.raises(NeedsQuote) as exc:
        evaluate(item, {"X!A1": Decimal("0")}, PricingRequest(pax=4))
    assert "0" in exc.value.reason


def test_negative_rate_cell_needs_a_quote():
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [],
    }
    with pytest.raises(NeedsQuote) as exc:
        evaluate(item, {"X!A1": Decimal("-50")}, PricingRequest(pax=4))
    assert "-200" in exc.value.reason


def test_negative_total_from_a_negative_add_per_booking_needs_a_quote():
    """Reachable via a negative fixed modifier amount, not just a
    negative base rate -- the guard is on the final total, not any one
    input."""
    item = {
        "currency": "EUR",
        "unit": "per_person",
        "pricing": {"pattern": "flat", "cell": "X!A1"},
        "modifiers": [
            {"type": "day_of_week", "when": ["MON"], "op": "add_per_booking",
             "cell": "X!B1"}
        ],
    }
    monday = date(2026, 6, 15)
    with pytest.raises(NeedsQuote):
        evaluate(item, {"X!A1": Decimal("10"), "X!B1": Decimal("-100")},
                 PricingRequest(pax=2, date=monday))
