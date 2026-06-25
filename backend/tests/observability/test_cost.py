from decimal import Decimal

from agentic_travel.observability.cost import CostModel, ModelPrice
from agentic_travel.observability.span import TokenUsage


def test_estimate_known_model() -> None:
    model = CostModel(
        {"m": ModelPrice(input_per_million_usd=Decimal("3"), output_per_million_usd=Decimal("15"))}
    )
    cost = model.estimate("m", TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000))
    assert cost == Decimal("18")


def test_unknown_model_is_zero() -> None:
    usage = TokenUsage(prompt_tokens=10, completion_tokens=10)
    assert CostModel({}).estimate("nope", usage) == Decimal("0")


def test_register_then_estimate() -> None:
    model = CostModel({})
    model.register(
        "x", ModelPrice(input_per_million_usd=Decimal("1"), output_per_million_usd=Decimal("2"))
    )
    cost = model.estimate("x", TokenUsage(prompt_tokens=500_000, completion_tokens=0))
    assert cost == Decimal("0.5")
