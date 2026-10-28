from decimal import Decimal, localcontext
import pytest
from jarvis.llm import BudgetExceeded, CostPolicy


def policy(budget='0.006'):
    return CostPolicy(Decimal('2'), Decimal('8'), Decimal(budget))


def test_exact_cost_at_budget_is_allowed_and_larger_request_is_denied():
    assert policy().authorize(1000, 500) == Decimal('0.006')
    with pytest.raises(BudgetExceeded):
        policy().authorize(1000, 501)


@pytest.mark.parametrize('value', [-1, True, 1.5, '20', 10_000_001, None])
def test_invalid_token_bound_cannot_be_authorized(value):
    with pytest.raises(ValueError):
        policy().authorize(value, 10)


@pytest.mark.parametrize('value', [Decimal('NaN'), Decimal('Infinity'), Decimal('-1'), Decimal('10001'), 0.1, '2'])
def test_invalid_price_is_rejected(value):
    with pytest.raises(ValueError):
        CostPolicy(value, Decimal('1'), Decimal('1'))


def test_explicit_zero_price_can_be_used_but_zero_budget_cannot():
    assert CostPolicy(Decimal('0'), Decimal('0'), Decimal('1')).authorize(1000, 500) == 0
    with pytest.raises(ValueError):
        CostPolicy(Decimal('0'), Decimal('0'), Decimal('0'))


def test_cost_does_not_inherit_callers_rounding_precision():
    with localcontext() as context:
        context.prec = 2
        assert policy('1').authorize(1234, 5678) == Decimal('0.047892')


@pytest.mark.parametrize('value', [Decimal('1e-13'), Decimal('0e9999999'), Decimal('1.0000000000000000001')])
def test_unbounded_decimal_precision_is_rejected(value):
    with pytest.raises(ValueError):
        CostPolicy(value, Decimal('1'), Decimal('1'))
