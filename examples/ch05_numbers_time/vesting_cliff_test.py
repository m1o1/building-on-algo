from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch05_numbers_time.vesting_cliff import vested_with_cliff

TOTAL = 1_200
START = 1_000
CLIFF = 1_300
END = 2_200


def test_the_cliff_releases_at_the_cliff_round_not_the_one_after() -> None:
    with algopy_testing_context():
        args = (UInt64(TOTAL), UInt64(START), UInt64(CLIFF), UInt64(END))
        assert vested_with_cliff(*args, UInt64(CLIFF - 1)) == 0
        # At exactly the cliff, the lump sum for the elapsed 300 rounds
        # is already payable: 1200 * 300 / 1200.
        assert vested_with_cliff(*args, UInt64(CLIFF)) == 300
        assert vested_with_cliff(*args, UInt64(END)) == TOTAL
