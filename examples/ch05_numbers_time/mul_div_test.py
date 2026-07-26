import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch05_numbers_time.mul_div import Rates

HUGE = 2**63


def test_mul_div_survives_a_product_that_plain_multiplication_cannot() -> None:
    with algopy_testing_context():
        contract = Rates()
        # HUGE * 10 is well past 2**64, so `(a * b) // d` would abort.
        assert contract.scale(UInt64(HUGE), UInt64(10), UInt64(10)) == HUGE
        assert contract.share_of(UInt64(HUGE), UInt64(1), UInt64(4)) == HUGE // 4
        with pytest.raises(AssertionError):
            contract.scale(UInt64(7), UInt64(3), UInt64(0))
