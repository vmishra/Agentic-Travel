"""Approximate currency conversion for cost estimation.

Rates are illustrative and fixed for reproducible local estimates; a production
system should source live FX rates. Each rate is the value of one unit of the
currency expressed in INR.
"""

from __future__ import annotations

from decimal import Decimal

from agentic_travel.domain.money import Currency, Money

_INR_PER_UNIT: dict[Currency, Decimal] = {
    Currency.INR: Decimal("1"),
    Currency.USD: Decimal("86"),
    Currency.EUR: Decimal("93"),
    Currency.GBP: Decimal("108"),
    Currency.AED: Decimal("23.4"),
    Currency.SGD: Decimal("64"),
    Currency.THB: Decimal("2.4"),
    Currency.JPY: Decimal("0.55"),
}


def convert(money: Money, target: Currency) -> Money:
    """Convert ``money`` to ``target`` using the illustrative rate table."""
    if money.currency is target:
        return money
    in_inr = money.amount * _INR_PER_UNIT[money.currency]
    converted = in_inr / _INR_PER_UNIT[target]
    return Money(amount=converted.quantize(Decimal("0.01")), currency=target)


def to_inr(money: Money) -> Money:
    """Convert ``money`` to INR, rounded to whole rupees."""
    converted = convert(money, Currency.INR)
    return Money(amount=converted.amount.quantize(Decimal("1")), currency=Currency.INR)
