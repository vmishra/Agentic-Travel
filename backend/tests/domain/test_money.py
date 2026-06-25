from decimal import Decimal

import pytest

from agentic_travel.domain.money import Currency, Money


def test_same_currency_addition() -> None:
    total = Money(amount=Decimal("100"), currency=Currency.INR) + Money(
        amount=Decimal("50"), currency=Currency.INR
    )
    assert total.amount == Decimal("150")
    assert total.currency is Currency.INR


def test_cross_currency_addition_raises() -> None:
    with pytest.raises(ValueError):
        Money(amount=Decimal("1"), currency=Currency.INR) + Money(
            amount=Decimal("1"), currency=Currency.USD
        )
