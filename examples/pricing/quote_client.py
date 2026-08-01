# book-example: mode=script
"""Quote a swap from a client, without re-implementing the contract wrong.

The pairing is the point. A wallet that shows a number the chain will not
honour is worse than one that shows nothing, and the only way to be sure is
to reproduce the contract's arithmetic exactly -- including which way each
division leans. Integers for anything the user will act on; floats only for
something a human reads.
"""

FEE_BPS = 30
BPS = 10_000


def amount_out(amount_in: int, res_in: int, res_out: int) -> int:
    """Floors, because the contract floors. Use this for `min_output`."""
    net = amount_in * (BPS - FEE_BPS)
    return net * res_out // (res_in * BPS + net)


def amount_in_for(wanted_out: int, res_in: int, res_out: int) -> int:
    """Rounds up, because the contract rounds up. Quote this, not one less."""
    if wanted_out >= res_out:
        raise ValueError("not that much liquidity")
    num = res_in * wanted_out * BPS
    den = (res_out - wanted_out) * (BPS - FEE_BPS)
    return -(-num // den)          # Python's ceiling idiom for integers


def display_price(res_in: int, res_out: int) -> float:
    """The one place a float belongs: a number a person reads and nothing else."""
    return res_out / res_in
