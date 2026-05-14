import pytest


PRECISION = 10**9
SECONDS_PER_DAY = 86_400
MAX_REWARD_DURATION = 365 * SECONDS_PER_DAY
MAX_REWARD_RATE = 584
MAX_UINT64 = 2**64 - 1


def deposit_model(
    amount: int,
    duration: int,
    remaining: int = 0,
    accumulator_stored: int = 0,
) -> tuple[int, int, int]:
    assert duration > 0
    assert duration <= MAX_REWARD_DURATION
    rate = amount // duration
    assert rate > 0
    assert rate <= MAX_REWARD_RATE
    distributable = rate * duration
    dust = amount - distributable
    assert distributable <= MAX_UINT64 - remaining
    worst_case_increment = distributable * PRECISION
    assert worst_case_increment <= MAX_UINT64 - accumulator_stored
    return rate, distributable, dust


def accumulator_increment(rate: int, delta_t: int, total_effective: int) -> int:
    assert delta_t <= MAX_REWARD_DURATION
    assert rate <= MAX_REWARD_RATE
    rate_time = rate * delta_t
    assert rate_time <= MAX_UINT64
    numerator = rate_time * PRECISION
    increment = numerator // total_effective
    assert increment <= MAX_UINT64
    return increment


def test_reward_deposit_splits_distributable_pool_and_dust() -> None:
    rate, distributable, dust = deposit_model(1_000_000, 86_401)

    assert rate == 11
    assert distributable == 950_411
    assert dust == 49_589
    assert distributable + dust == 1_000_000


def test_reward_conservation_tracks_distributable_not_deposited() -> None:
    rate, distributable, dust = deposit_model(1_000_000, 86_401)
    rewards_remaining = distributable
    claimed = 0

    for claim in (333_000, 333_000, 284_411):
        assert claim <= rewards_remaining
        rewards_remaining -= claim
        claimed += claim
        assert claimed + rewards_remaining == distributable

    assert claimed == distributable
    assert rewards_remaining == 0
    assert dust == 49_589


def test_reward_bounds_keep_rate_time_within_uint64() -> None:
    rate_time = MAX_REWARD_RATE * MAX_REWARD_DURATION
    scaled = rate_time * PRECISION

    assert rate_time <= MAX_UINT64
    assert scaled <= MAX_UINT64


def test_reward_deposit_bounds_reject_unsafe_inputs() -> None:
    assert (
        deposit_model(
            MAX_REWARD_RATE * MAX_REWARD_DURATION,
            MAX_REWARD_DURATION,
        )[0]
        == MAX_REWARD_RATE
    )

    with pytest.raises(AssertionError):
        deposit_model(1_000, MAX_REWARD_DURATION + 1)

    with pytest.raises(AssertionError):
        deposit_model((MAX_REWARD_RATE + 1) * 10, 10)

    with pytest.raises(AssertionError):
        deposit_model(10, 100)


def test_second_max_period_rejected_by_accumulator_capacity() -> None:
    _, distributable, _ = deposit_model(
        MAX_REWARD_RATE * MAX_REWARD_DURATION,
        MAX_REWARD_DURATION,
    )
    accumulator_stored = distributable * PRECISION

    with pytest.raises(AssertionError):
        deposit_model(
            MAX_REWARD_RATE * MAX_REWARD_DURATION,
            MAX_REWARD_DURATION,
            accumulator_stored=accumulator_stored,
        )


def test_accumulator_increment_uses_wide_intermediate_model() -> None:
    rate, _, _ = deposit_model(58_400, 100)
    increment = accumulator_increment(rate, 10, total_effective=5)

    assert increment == 1_168 * PRECISION
