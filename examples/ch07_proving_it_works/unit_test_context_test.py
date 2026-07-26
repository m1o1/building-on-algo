"""Three things the emulator gives you: an app, a clock, and a sender."""

import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch07_proving_it_works.unit_test_context import Deadline

NOW = 1_700_000_000
HOUR = 60 * 60


def test_an_entry_before_the_deadline_is_counted() -> None:
    with algopy_testing_context() as ctx:
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(NOW))
        contract = Deadline()
        contract.open_until(UInt64(NOW + HOUR))

        assert contract.enter() == 1
        assert contract.enter() == 2


def test_an_entry_after_the_deadline_is_refused() -> None:
    """Time travel, in one assignment."""
    with algopy_testing_context() as ctx:
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(NOW))
        contract = Deadline()
        contract.open_until(UInt64(NOW + HOUR))
        assert contract.enter() == 1

        # The deadline did not move. The ledger did.
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(NOW + 2 * HOUR))
        with pytest.raises(AssertionError, match="closed"):
            contract.enter()


def test_a_deadline_in_the_past_cannot_be_set() -> None:
    with algopy_testing_context() as ctx:
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(NOW))
        contract = Deadline()
        with pytest.raises(AssertionError, match="deadline already passed"):
            contract.open_until(UInt64(NOW - HOUR))


def test_a_stranger_cannot_open_the_deadline() -> None:
    """`ctx.default_sender` is the creator; anyone else is not."""
    with algopy_testing_context() as ctx:
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(NOW))
        contract = Deadline()
        stranger = ctx.any.account()
        with ctx.txn.create_group([ctx.any.txn.application_call(  # noqa: SIM117
            app_id=ctx.ledger.get_app(contract), sender=stranger
        )]):
            with pytest.raises(AssertionError, match="owner only"):
                contract.open_until(UInt64(NOW + HOUR))
