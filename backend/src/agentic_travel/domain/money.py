"""Monetary values with explicit currency."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class Currency(StrEnum):
    """Supported ISO-4217 currency codes."""

    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    AED = "AED"
    SGD = "SGD"
    THB = "THB"
    JPY = "JPY"


class Money(BaseModel):
    """An amount in a specific currency."""

    amount: Decimal
    currency: Currency

    def __add__(self, other: Money) -> Money:
        """Add two amounts of the same currency."""
        if self.currency is not other.currency:
            raise ValueError(
                f"cannot add {self.currency.value} to {other.currency.value}"
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)
