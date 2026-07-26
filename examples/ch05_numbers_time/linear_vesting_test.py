from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch05_numbers_time.linear_vesting import vested
from examples.ch05_numbers_time.linear_vesting_wrong import vested_wrong

TOTAL = 1_000_000
START = 0
END = 2_830_000  # about ninety days at 2.75 seconds a round


def test_dividing_first_pays_nothing_until_the_very_last_round() -> None:
    with algopy_testing_context():
        third = UInt64(END // 3)
        args = (UInt64(TOTAL), UInt64(START), UInt64(END))
        assert vested(*args, third) == 333_333
        assert vested_wrong(*args, third) == 0
        # The wrong form only ever produces two answers: 0, then all.
        assert vested_wrong(*args, UInt64(END - 1)) == 0
        assert vested_wrong(*args, UInt64(END)) == TOTAL


def test_the_guards_bound_the_schedule_at_both_ends() -> None:
    with algopy_testing_context():
        args = (UInt64(TOTAL), UInt64(START), UInt64(END))
        assert vested(*args, UInt64(START)) == 0
        assert vested(*args, UInt64(END)) == TOTAL
        assert vested(*args, UInt64(END * 2)) == TOTAL
