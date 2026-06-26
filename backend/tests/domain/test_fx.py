from decimal import Decimal

from agentic_travel.domain.fx import convert, to_inr
from agentic_travel.domain.money import Currency, Money


def test_same_currency_is_identity() -> None:
    money = Money(amount=Decimal("100"), currency=Currency.INR)
    assert convert(money, Currency.INR) is money


def test_to_inr_uses_rate() -> None:
    result = to_inr(Money(amount=Decimal("100"), currency=Currency.AED))
    assert result.currency is Currency.INR
    assert result.amount == Decimal("2340")  # 100 * 23.4


def test_round_trip_is_close() -> None:
    start = Money(amount=Decimal("1000"), currency=Currency.INR)
    usd = convert(start, Currency.USD)
    back = convert(usd, Currency.INR)
    assert abs(back.amount - start.amount) < Decimal("1")
