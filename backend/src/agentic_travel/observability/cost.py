"""Token-usage-to-cost estimation with a configurable price table."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from agentic_travel.observability.span import TokenUsage

_MILLION = Decimal("1000000")


class ModelPrice(BaseModel):
    """Per-million-token input and output prices, in USD."""

    input_per_million_usd: Decimal
    output_per_million_usd: Decimal


class CostModel:
    """Estimates the USD cost of model calls from a price table."""

    def __init__(self, prices: dict[str, ModelPrice]) -> None:
        """Initialize with a mapping of model identifier to price."""
        self._prices: dict[str, ModelPrice] = dict(prices)

    def register(self, model: str, price: ModelPrice) -> None:
        """Add or replace the price for a model."""
        self._prices[model] = price

    def estimate(self, model: str, usage: TokenUsage) -> Decimal:
        """Return the USD cost for the usage, or zero for an unknown model."""
        price = self._prices.get(model)
        if price is None:
            return Decimal("0")
        return (
            usage.prompt_tokens * price.input_per_million_usd
            + usage.completion_tokens * price.output_per_million_usd
        ) / _MILLION


def default_cost_model() -> CostModel:
    """Return a cost model seeded with illustrative, configurable tier prices.

    These values are placeholders for local estimation only and should be
    overridden with current published prices for the configured models.
    """
    return CostModel(
        {
            "planner": ModelPrice(
                input_per_million_usd=Decimal("3.50"),
                output_per_million_usd=Decimal("10.50"),
            ),
            "fast": ModelPrice(
                input_per_million_usd=Decimal("0.30"),
                output_per_million_usd=Decimal("2.50"),
            ),
            "live": ModelPrice(
                input_per_million_usd=Decimal("0.50"),
                output_per_million_usd=Decimal("2.00"),
            ),
            "image": ModelPrice(
                input_per_million_usd=Decimal("0.00"),
                output_per_million_usd=Decimal("30.00"),
            ),
        }
    )
