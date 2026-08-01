"""The Chapter 19 workflow, end to end, on LocalNet.

Two lotteries run, because a lottery has two endings. The first one draws:
five entrants pay in, the operator commits to a future round, the beacon
publishes a value for it, and the pot goes to whoever that value picks. The
second one does not: nothing is ever published for its target round, the draw
window closes, and every entrant takes their money back.

The second ending is the whole reason the beacon is a stub here. On TestNet
you can read a real beacon and you cannot ask it to go quiet, so the branch
that matters most is the one production cannot show you.
"""

from __future__ import annotations

import time

from algokit_utils import AlgorandClient

from scripts.localnet_helpers import (
    BEACON_APP_ID,
    BEACON_ROUND_MODULUS,
    CREATOR_APP_MBR,
    DEMO_BEACON_VALUE,
    DRAW_WINDOW_ROUNDS,
    ENTRY_BOX_COST,
    LOTTERY_APP_BASE_MBR,
    MICRO_UNITS,
    MIN_LEAD_ROUNDS,
    advance_to,
    algo_balance,
    assert_app_sits_at_its_floor,
    assert_creator_holds_the_schema,
    box_names,
    commit,
    commit_with_round,
    current_round,
    deploy_lottery,
    draw,
    draw_call,
    enter,
    fund_account,
    get_localnet_algorand,
    min_balance,
    publish,
    read_entry,
    read_state,
    refuses,
    require_artifacts,
    resolve_beacon,
    settle,
    won_event,
)

TICKET_PRICE = 2 * MICRO_UNITS
DRAWN_ENTRANTS = 5
ABANDONED_ENTRANTS = 3


def get_algorand() -> AlgorandClient:
    """LocalNet unless the beacon has been pointed at a public network."""
    if BEACON_APP_ID:
        return AlgorandClient.from_environment()
    return get_localnet_algorand()


def reach_round(algorand, funder, target_round: int) -> int:
    """Get to `target_round`, by making blocks or by waiting for them."""
    if BEACON_APP_ID:
        while current_round(algorand) <= target_round:
            time.sleep(3)
        return current_round(algorand)
    return advance_to(algorand, funder, target_round)


def run_drawn_lottery(algorand, operator, entrants, caller, beacon, stub):
    operator_floor = min_balance(algorand, operator.address)
    lottery = deploy_lottery(
        algorand, operator, beacon_app_id=beacon, ticket_price=TICKET_PRICE
    )
    print("Lottery deployed, reading a beacon it does not own")
    print(
        f"  app account seeded to {LOTTERY_APP_BASE_MBR:,} microAlgo, "
        f"which is its whole min-balance"
    )
    assert_creator_holds_the_schema(
        algorand, operator, before=operator_floor, apps=1
    )
    print(
        f"  operator's min-balance rose {CREATOR_APP_MBR:,} for the app "
        f"and its 7+1 slots"
    )

    for entrant in entrants:
        index = enter(algorand, lottery, entrant, ticket_price=TICKET_PRICE)
        assert read_entry(algorand, lottery.app_id, index) == entrant.address
    state = read_state(algorand, lottery.app_id)
    assert state["entries"] == len(entrants), state
    assert state["pot"] == len(entrants) * TICKET_PRICE, state
    print(
        f"  {len(entrants)} entries, pot {state['pot']:,} microAlgo, "
        f"{len(box_names(algorand, lottery.app_id))} boxes at "
        f"{ENTRY_BOX_COST:,} each"
    )

    refuses(lambda: draw(lottery, caller, beacon_app_id=beacon, quiet=True),
            "nothing committed yet")

    target, committed_at = commit_with_round(
        algorand, lottery, operator, lead=MIN_LEAD_ROUNDS
    )
    # Rounding up to a multiple of eight can only lengthen the lead, so a
    # 16-round request buys somewhere between 16 and 23 rounds. The exact
    # number depends on where the commit landed and is not worth printing.
    assert target % BEACON_ROUND_MODULUS == 0, target
    lead = target - committed_at
    assert MIN_LEAD_ROUNDS <= lead <= MIN_LEAD_ROUNDS + 7, lead
    print(
        f"  committed to a multiple of {BEACON_ROUND_MODULUS}, at least "
        f"{MIN_LEAD_ROUNDS} rounds ahead"
    )

    refuses(
        lambda: enter(algorand, lottery, entrants[0],
                      ticket_price=TICKET_PRICE, quiet=True),
        "entries are closed")
    refuses(lambda: draw(lottery, caller, beacon_app_id=beacon, quiet=True),
            "target round is future")

    reach_round(algorand, operator, target)
    if stub is not None:
        refuses(
            lambda: draw(lottery, caller, beacon_app_id=beacon, quiet=True),
            "beacon published nothing")
        publish(stub, operator, rnd=target, value=DEMO_BEACON_VALUE)
        print("  beacon published 32 bytes for the target round")

    pot = read_state(algorand, lottery.app_id)["pot"]
    before = [algo_balance(algorand, one.address) for one in entrants]
    result = draw_call(lottery, caller, beacon_app_id=beacon)
    index = int(result.abi_return)
    winner = read_state(algorand, lottery.app_id)["winner"]
    assert winner == entrants[index].address, (winner, index)
    after = [algo_balance(algorand, one.address) for one in entrants]
    # The winner is up the whole pot and nobody else moved -- including the
    # account that called `draw`, which pays the fees and takes no cut.
    for position, (was, now) in enumerate(zip(before, after)):
        assert now - was == (pot if position == index else 0), position
    print(f"  draw picked entrant {index} of {len(entrants)}, paid {pot:,}")
    # The same result twice: `winner` in state for whoever asks, and a `Won`
    # log for whoever is listening. The event costs no fee and no transaction.
    announced, amount = won_event(result)
    assert (announced, amount) == (winner, pot), (announced, amount)
    print(f"  Won(address,uint64) logged {amount:,} to the same account")

    refuses(lambda: draw(lottery, caller, beacon_app_id=beacon, quiet=True),
            "already drawn")
    refuses(
        lambda: settle(lottery, caller, method="refund", index=0, quiet=True),
        "the draw already happened")
    held = assert_app_sits_at_its_floor(
        algorand, lottery, entries=len(entrants)
    )
    print(f"  pot gone: balance and min-balance both {held:,} microAlgo")

    for position in range(len(entrants)):
        assert settle(lottery, caller, method="sweep", index=position) == (
            ENTRY_BOX_COST
        )
    refuses(
        lambda: settle(lottery, caller, method="sweep", index=0, quiet=True),
        "no such entry")
    held = assert_app_sits_at_its_floor(algorand, lottery, entries=0)
    print(
        f"  {len(entrants)} boxes swept, {ENTRY_BOX_COST:,} each returned, "
        f"back to {held:,}"
    )


def run_abandoned_lottery(algorand, operator, entrants, caller, beacon):
    lottery = deploy_lottery(
        algorand, operator, beacon_app_id=beacon, ticket_price=TICKET_PRICE
    )
    for entrant in entrants:
        enter(algorand, lottery, entrant, ticket_price=TICKET_PRICE)
    target = commit(algorand, lottery, operator, lead=MIN_LEAD_ROUNDS)
    refund_round = read_state(algorand, lottery.app_id)["refund"]
    assert refund_round == target + DRAW_WINDOW_ROUNDS, refund_round
    print(
        f"Abandoned lottery: {len(entrants)} entries, draw window "
        f"{DRAW_WINDOW_ROUNDS} rounds"
    )

    reach_round(algorand, operator, target)
    refuses(
        lambda: settle(lottery, caller, method="refund", index=0, quiet=True),
        "draw still possible")

    reach_round(algorand, operator, refund_round)
    refuses(lambda: draw(lottery, caller, beacon_app_id=beacon, quiet=True),
            "draw window closed")
    refuses(
        lambda: settle(lottery, caller, method="sweep", index=0, quiet=True),
        "no draw yet")

    stake = TICKET_PRICE + ENTRY_BOX_COST
    for position in range(len(entrants)):
        assert settle(lottery, caller, method="refund", index=position) == stake
    refuses(
        lambda: settle(lottery, caller, method="refund", index=0, quiet=True),
        "no such entry")
    assert read_state(algorand, lottery.app_id)["pot"] == 0
    held = assert_app_sits_at_its_floor(algorand, lottery, entries=0)
    print(
        f"  beacon silent: each entrant took back {stake:,}, "
        f"back to {held:,}"
    )


def main() -> int:
    try:
        algorand = get_algorand()
        require_artifacts()
    except RuntimeError as exc:
        print(exc)
        return 1

    if BEACON_APP_ID:
        operator = algorand.account.from_environment("DEPLOYER")
        drawn_entrants = [operator] * DRAWN_ENTRANTS
        caller = operator
    else:
        dispenser = algorand.account.localnet_dispenser()
        operator = algorand.account.random()
        caller = algorand.account.random()
        fund_account(algorand, dispenser, operator, amount=200 * MICRO_UNITS)
        fund_account(algorand, dispenser, caller, amount=10 * MICRO_UNITS)
        drawn_entrants = []
        for _ in range(DRAWN_ENTRANTS + ABANDONED_ENTRANTS):
            account = algorand.account.random()
            fund_account(algorand, dispenser, account, amount=10 * MICRO_UNITS)
            drawn_entrants.append(account)

    try:
        beacon, stub = resolve_beacon(algorand, operator)
        run_drawn_lottery(
            algorand, operator, drawn_entrants[:DRAWN_ENTRANTS], caller,
            beacon, stub,
        )
    except RuntimeError as exc:
        print(exc)
        return 1

    if stub is None:
        print(
            "Abandoned lottery: skipped. A beacon somebody else operates "
            "cannot be asked to go silent, and the draw window is "
            f"{DRAW_WINDOW_ROUNDS} real rounds long."
        )
        return 0
    try:
        run_abandoned_lottery(
            algorand, operator, drawn_entrants[DRAWN_ENTRANTS:], caller, beacon
        )
    except RuntimeError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
