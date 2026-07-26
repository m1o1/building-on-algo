"""Work out how many box references a call needs for the boxes it touches."""

import sys

BYTES_PER_REF = 2048  # I/O budget per box reference, consensus v41+


def refs_needed(existing_sizes: list[int], written_sizes: list[int]) -> int:
    """Read and write are separate budgets, each charging a box's FULL size."""
    read = sum(existing_sizes)
    write = sum(written_sizes)
    by_budget = -(-max(read, write) // BYTES_PER_REF)  # never summed
    return max(len(existing_sizes), by_budget)


if __name__ == "__main__":
    sizes = [int(a) for a in sys.argv[1:]]
    print(f"{sum(sizes)}B in {len(sizes)} boxes: {refs_needed(sizes, sizes)} refs")
