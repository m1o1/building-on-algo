import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch05_numbers_time.underflow_panics import Vault


def test_subtraction_below_zero_aborts_rather_than_going_negative() -> None:
    with algopy_testing_context():
        contract = Vault()
        assert contract.shortfall(UInt64(100), UInt64(40)) == 60
        # The emulator says `- underflows`; the chain says
        # `- would result negative`. Neither is a negative number.
        with pytest.raises(ArithmeticError):
            contract.shortfall(UInt64(40), UInt64(100))
        assert contract.shortfall_or_zero(UInt64(40), UInt64(100)) == 0
