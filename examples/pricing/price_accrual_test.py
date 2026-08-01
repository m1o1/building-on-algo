"""Chapter 13's ordering defect, priced.

One hour during which the price goes from one to five. The correct accrual
credits the hour to the price that held over it; the swapped one credits it
to the price that replaced it, and the two accumulators differ by exactly
the size of the move.
"""

from algopy import UInt64, arc4
from algopy_testing import algopy_testing_context

from examples.pricing.price_accrual import Accrual
from examples.pricing.price_accrual_swapped import Accrual as SwappedAccrual

START = 1_700_000_000
HOUR = 3_600


def test_ordering_changes_the_accumulator_by_the_size_of_the_move() -> None:
    with algopy_testing_context() as ctx:
        correct = Accrual()
        swapped = SwappedAccrual()

        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START))
        correct.touch(UInt64(1))
        swapped.touch(UInt64(1))

        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START + HOUR))
        correct.touch(UInt64(5))
        swapped.touch(UInt64(5))

        assert correct.cumulative.value == HOUR
        assert swapped.cumulative.value == 5 * HOUR


def test_average_since_differences_two_snapshots() -> None:
    with algopy_testing_context() as ctx:
        accrual = Accrual()

        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START))
        accrual.touch(UInt64(7))
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START + HOUR))
        accrual.touch(UInt64(9))

        # Snapshot taken at START: cumulative zero, timestamp START.
        assert accrual.average_since(arc4.UInt512(0), UInt64(START)) == 7
