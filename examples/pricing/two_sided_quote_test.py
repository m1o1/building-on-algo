"""Chapter 13's two acceptance checks for the repaired quote.

`test_client_and_contract_agree` is the driver behind the transcript: nine
sizes, both directions, contract against the Python client of Example 13-9.
`test_no_quote_lowers_the_product` is the invariant the first pass broke,
asserted across four trade sizes.
"""

from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.pricing.quote_client import amount_in_for, amount_out
from examples.pricing.two_sided_quote import PriceQuote

RESERVE_A = 10_000_000
RESERVE_B = 4_000_000

SIZES = [1, 10, 100, 333, 1_000, 9_999, 100_000, 500_000, 1_000_000]
TRADE_SIZES = [1, 1_000, 100_000, 1_000_000]


def seeded() -> PriceQuote:
    contract = PriceQuote()
    contract.seed(UInt64(RESERVE_A), UInt64(RESERVE_B))
    return contract


def test_client_and_contract_agree() -> None:
    with algopy_testing_context():
        contract = seeded()
        for size in SIZES:
            assert contract.quote_in_to_out(UInt64(size)) == amount_out(
                size, RESERVE_A, RESERVE_B
            )
            assert contract.quote_out_to_in(UInt64(size)) == amount_in_for(
                size, RESERVE_A, RESERVE_B
            )


def test_transcript_numbers() -> None:
    with algopy_testing_context():
        contract = seeded()
        assert contract.quote_in_to_out(UInt64(1)) == 0
        assert contract.quote_in_to_out(UInt64(100)) == 39
        assert contract.quote_in_to_out(UInt64(1_000)) == 398


def test_no_quote_lowers_the_product() -> None:
    with algopy_testing_context():
        contract = seeded()
        before = RESERVE_A * RESERVE_B
        for size in TRADE_SIZES:
            out = int(contract.quote_in_to_out(UInt64(size)))
            assert (RESERVE_A + size) * (RESERVE_B - out) >= before

            need = int(contract.quote_out_to_in(UInt64(size)))
            assert (RESERVE_A + need) * (RESERVE_B - size) >= before
