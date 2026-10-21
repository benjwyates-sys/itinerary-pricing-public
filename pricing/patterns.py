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

    total = round_money(subtotal)
    if total <= 0:
        # A zero or negative total is never a real price -- it is a
        # placeholder rate cell, a cleared cell, a formula that evaluated
        # to 0, or a `multiply` modifier with factor 0 (a comped item).
        # Writing it into the client's quote reads as "free" or as a
        # routine price change, and both are silent mispricings. Refuse
        # and ask a human to confirm instead of ever writing it down.
        raise NeedsQuote(
            f"This priced out to {total} {item['currency']} -- a zero or "
            "negative rate needs confirming before I can quote it. It "
            "might be a placeholder, a cleared cell, or a genuinely "
            "comped item, but I won't guess which."
        )

    return PricingResult(total, item["currency"], lines)


def _base_rate(item: dict, rates: Mapping[str, Decimal],
               request: PricingRequest) -> tuple[Decimal, list[str]]:
    pricing = item["pricing"]
    pattern = pricing["pattern"]

    if pattern == "flat":
        rate = _lookup(rates, pricing["cell"])
        return rate, [f"base {rate} ({pricing['cell']})"]

    if pattern == "tiered_by_pax":
        tiers = sorted(pricing["tiers"], key=lambda t: t["max_pax"])
        if not tiers:
            raise NeedsQuote(
                "This experience has no rates mapped yet. "
                "Run /map to fetch rates for its region."
            )
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
    unit = item["unit"]
    if unit == "per_group":
        return 1
    if unit == "per_person":
        return max(request.pax, item.get("min_billable_pax") or 0)
    raise NeedsQuote(f"unknown unit {unit!r}")


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
