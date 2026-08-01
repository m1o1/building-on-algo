"""The counter's unit test (Chapter 4): `count` is written at creation,
so the first bump returns one and the second returns two."""

from algopy_testing import algopy_testing_context

from examples.state.global_counter import GlobalCounter


def test_bump_counts_from_one_then_two() -> None:
    with algopy_testing_context():
        contract = GlobalCounter()
        assert contract.bump() == 1
        assert contract.bump() == 2
