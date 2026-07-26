import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch05_numbers_time.overflow_panics import MAX_UINT64, Ledger


def test_add_aborts_at_the_ceiling_where_add_checked_refuses() -> None:
    with algopy_testing_context():
        contract = Ledger()
        assert contract.add(UInt64(MAX_UINT64 - 1), UInt64(1)) == MAX_UINT64
        # Unit tests report the emulator's wording, `+ overflows`.
        # On chain the same failure reads `+ overflowed`.
        with pytest.raises(OverflowError):
            contract.add(UInt64(MAX_UINT64), UInt64(1))
        with pytest.raises(AssertionError):
            contract.add_checked(UInt64(MAX_UINT64), UInt64(1))
