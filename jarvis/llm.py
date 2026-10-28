"""Provider contracts and explicit per-request USD limits (M3.1 foundation).

Adapters must supply verified token bounds before authorizing a request. This
module does not tokenize text, contact a provider or track a daily budget.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal, Protocol, Sequence


@dataclass(frozen=True)
class Message:
    role: Literal['system', 'user', 'assistant']
    content: str


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: str | None = None
    reserved_cost_usd: str | None = None


class Provider(Protocol):
    async def complete(self, messages: Sequence[Message], model: str,
                       max_output_tokens: int) -> Completion: ...


class BudgetExceeded(ValueError):
    pass


def _tokens(value: int) -> int:
    if type(value) is not int or not 0 <= value <= 10_000_000:
        raise ValueError('Token count must be an integer within supported bounds')
    return value


@dataclass(frozen=True)
class CostPolicy:
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    max_request_usd: Decimal

    def __post_init__(self):
        for value in (self.input_usd_per_million, self.output_usd_per_million,
                      self.max_request_usd):
            if not isinstance(value, Decimal) or not value.is_finite() or not 0 <= value <= 10000:
                raise ValueError('Prices and budget require finite nonnegative USD decimals')
            if len(value.as_tuple().digits) > 18 or not -12 <= value.as_tuple().exponent <= 6:
                raise ValueError('USD decimals exceed supported precision')
        if self.max_request_usd == 0:
            raise ValueError('A positive request budget is required')

    def estimate(self, input_tokens: int, output_tokens: int) -> Decimal:
        with localcontext() as context:
            context.prec = 40
            return (self.input_usd_per_million * _tokens(input_tokens)
                    + self.output_usd_per_million * _tokens(output_tokens)) / Decimal(1_000_000)

    def authorize(self, input_token_bound: int, output_token_bound: int) -> Decimal:
        bound = self.estimate(input_token_bound, output_token_bound)
        if bound > self.max_request_usd:
            raise BudgetExceeded('Configured per-request cost limit exceeded')
        return bound
