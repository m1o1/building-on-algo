"""The same behaviour asserted twice. Only one assertion can fail."""

import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch07_proving_it_works.requirement_vs_code import (CAP,
                                                                ClampingVault,
                                                                RefusingVault)


def test_the_assertion_written_from_the_code_holds_for_both() -> None:
    """`withdraw` returns what it paid. True of both contracts."""
    with algopy_testing_context():
        assert ClampingVault().withdraw(UInt64(CAP)) == CAP
    with algopy_testing_context():
        assert RefusingVault().withdraw(UInt64(CAP)) == CAP


def test_the_assertion_written_from_the_requirement_separates_them() -> None:
    """"Over the cap is refused." Only one contract does that."""
    with algopy_testing_context():
        with pytest.raises(AssertionError, match="over the cap"):
            RefusingVault().withdraw(UInt64(CAP + 1))

    with algopy_testing_context():
        # The same request, the same green tick, and a caller who is
        # short by one unit and has nothing in the response saying so.
        assert ClampingVault().withdraw(UInt64(CAP + 1)) == CAP
