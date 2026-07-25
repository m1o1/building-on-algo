from algopy_testing import algopy_testing_context

from examples.ch03_state.global_counter import GlobalCounter


def test_bump_increments_from_zero() -> None:
    with algopy_testing_context():
        contract = GlobalCounter()
        assert contract.bump() == 1
        assert contract.bump() == 2
