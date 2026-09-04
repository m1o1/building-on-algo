"""LocalNet tests for the beacon lottery.

Two of these are the happy paths -- the draw that happens and the draw that
never does. Everything else is a refusal, because the lottery holds other
people's money and what protects it is the set of transactions the network
will not accept. Each refusal below removes exactly one guard's worth of
honesty from an otherwise valid call and asserts on the message that comes
back, not merely on the call failing.
"""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from algokit_utils import (
    AlgoAmount,
    AppClientMethodCallParams,
    AppDeleteParams,
    AppUpdateParams,
    PaymentParams,
    SendParams,
)
from algosdk.transaction import OnComplete
from algosdk.atomic_transaction_composer import TransactionWithSigner

from scripts.localnet_helpers import (
    DEMO_BEACON_VALUE,
    DRAW_WINDOW_ROUNDS,
    ENTRY_BOX_COST,
    ENTRY_WINDOW_ROUNDS,
    LOTTERY_APP_BASE_MBR,
    LOTTERY_SPEC,
    MAX_LEAD_ROUNDS,
    MAX_TICKET_PRICE,
    MICRO_UNITS,
    MIN_LEAD_ROUNDS,
    advance_to,
    algo_balance,
    assert_app_sits_at_its_floor,
    assert_creator_holds_the_schema,
    commit,
    current_round,
    deploy_beacon_stub,
    deploy_lottery,
    draw,
    draw_call,
    enter,
    entry_box_reference,
    fund_account,
    min_balance,
    publish,
    read_entry,
    read_state,
    refuses,
    require_artifacts,
    settle,
    won_event,
)

pytestmark = pytest.mark.localnet

TICKET_PRICE = 2 * MICRO_UNITS
QUIET = SendParams(suppress_log=True)


def winner_index(value: bytes, entries: int) -> int:
    """The contract's arithmetic, restated off chain.

    `draw` hashes the beacon value with sha512_256, reads the last eight
    bytes as a big-endian integer and takes it modulo the entry count. Every
    input is public the moment the beacon publishes, which is exactly why the
    target round has to be named before the value exists.
    """
    digest = hashlib.new("sha512_256", value).digest()
    return int.from_bytes(digest[24:32], "big") % entries


class System:
    """One beacon stub, one lottery, and the accounts around them."""

    def __init__(self, algorand, *, entrants: int = 5, initialise: bool = True):
        require_artifacts()
        self.algorand = algorand
        dispenser = algorand.account.localnet_dispenser()
        self.operator = algorand.account.random()
        self.stranger = algorand.account.random()
        fund_account(algorand, dispenser, self.operator, amount=100 * MICRO_UNITS)
        fund_account(algorand, dispenser, self.stranger, amount=20 * MICRO_UNITS)
        self.entrants = []
        for _ in range(entrants):
            account = algorand.account.random()
            fund_account(algorand, dispenser, account, amount=20 * MICRO_UNITS)
            self.entrants.append(account)

        self.beacon = deploy_beacon_stub(algorand, self.operator)
        self.operator_floor = min_balance(algorand, self.operator.address)
        self.lottery = deploy_lottery(
            algorand,
            self.operator,
            beacon_app_id=self.beacon.app_id,
            ticket_price=TICKET_PRICE,
            initialise=initialise,
        )

    # -- convenience ----------------------------------------------------- #

    def enter_all(self) -> None:
        for entrant in self.entrants:
            enter(
                self.algorand, self.lottery, entrant, ticket_price=TICKET_PRICE
            )

    def commit(self, lead: int = MIN_LEAD_ROUNDS) -> int:
        return commit(self.algorand, self.lottery, self.operator, lead=lead)

    def reach(self, target_round: int) -> int:
        return advance_to(self.algorand, self.operator, target_round)

    def publish(self, rnd: int, value: bytes = DEMO_BEACON_VALUE) -> None:
        publish(self.beacon, self.operator, rnd=rnd, value=value)

    def draw_call(self, *, caller=None, fee: int | None = None,
                  quiet: bool = False):
        kwargs = {"beacon_app_id": self.beacon.app_id, "quiet": quiet}
        if fee is not None:
            kwargs["fee"] = fee
        return draw_call(self.lottery, caller or self.stranger, **kwargs)

    def draw(self, *, caller=None, fee: int | None = None, quiet: bool = False):
        kwargs = {"beacon_app_id": self.beacon.app_id, "quiet": quiet}
        if fee is not None:
            kwargs["fee"] = fee
        return draw(self.lottery, caller or self.stranger, **kwargs)

    def settle(self, method: str, index: int, *, quiet: bool = False) -> int:
        return settle(
            self.lottery, self.stranger, method=method, index=index, quiet=quiet
        )

    def state(self) -> dict:
        return read_state(self.algorand, self.lottery.app_id)

    def run_to_the_draw(self) -> int:
        """Enter, commit, wait, publish. Returns the target round."""
        self.enter_all()
        target = self.commit()
        self.reach(target)
        self.publish(target)
        return target


# ============================ the two endings ============================= #


def test_the_pot_goes_to_the_account_the_beacon_picks(algorand) -> None:
    system = System(algorand)
    system.run_to_the_draw()
    pot = system.state()["pot"]
    assert pot == len(system.entrants) * TICKET_PRICE

    before = [algo_balance(algorand, one.address) for one in system.entrants]
    result = system.draw_call()
    index = int(result.abi_return)

    assert index == winner_index(DEMO_BEACON_VALUE, len(system.entrants))
    assert system.state()["winner"] == system.entrants[index].address
    after = [algo_balance(algorand, one.address) for one in system.entrants]
    for position, (was, now) in enumerate(zip(before, after)):
        assert now - was == (pot if position == index else 0), position
    assert system.state()["pot"] == 0

    # State answers whoever asks; the event reaches whoever is listening. The
    # same two facts, in the same transaction, for two different readers.
    assert won_event(result) == (system.entrants[index].address, pot)


def test_a_silent_beacon_gives_every_entrant_their_money_back(algorand) -> None:
    system = System(algorand, entrants=3)
    system.enter_all()
    target = system.commit()
    stake = TICKET_PRICE + ENTRY_BOX_COST

    # Nothing is ever published for `target`. The draw window opens, closes,
    # and the entrants are the only people who can be made whole.
    system.reach(target + DRAW_WINDOW_ROUNDS)
    before = [algo_balance(algorand, one.address) for one in system.entrants]
    for index in range(len(system.entrants)):
        assert system.settle("refund", index) == stake
    after = [algo_balance(algorand, one.address) for one in system.entrants]
    assert [now - was for was, now in zip(before, after)] == [stake] * 3
    assert system.state()["pot"] == 0
    assert_app_sits_at_its_floor(algorand, system.lottery, entries=0)


# ========================= minimum balance ================================ #


def test_the_creator_holds_the_schema_and_the_app_holds_the_boxes(
    algorand,
) -> None:
    system = System(algorand, entrants=2)
    # 100,000 for the app plus seven uint slots at 28,500 and one byte-slice
    # slot at 50,000, all of it locked in the operator's own account.
    assert_creator_holds_the_schema(
        algorand, system.operator, before=system.operator_floor, apps=1
    )
    assert (
        min_balance(algorand, system.lottery.app_address)
        == LOTTERY_APP_BASE_MBR
    )

    system.enter_all()
    assert min_balance(algorand, system.lottery.app_address) == (
        LOTTERY_APP_BASE_MBR + 2 * ENTRY_BOX_COST
    )
    # Two entries in, the account holds its floor plus exactly the pot.
    assert algo_balance(algorand, system.lottery.app_address) == (
        LOTTERY_APP_BASE_MBR + 2 * ENTRY_BOX_COST + 2 * TICKET_PRICE
    )


def test_the_pot_leaves_the_account_sitting_on_its_floor(algorand) -> None:
    system = System(algorand, entrants=3)
    system.run_to_the_draw()
    system.draw()
    assert_app_sits_at_its_floor(algorand, system.lottery, entries=3)

    for index in range(3):
        assert system.settle("sweep", index) == ENTRY_BOX_COST
    floor = assert_app_sits_at_its_floor(algorand, system.lottery, entries=0)
    assert floor == LOTTERY_APP_BASE_MBR


def test_the_caller_pays_for_both_inner_transactions(algorand) -> None:
    """`draw` is three transactions, so 2,000 microAlgo is one short."""
    system = System(algorand, entrants=3)
    system.run_to_the_draw()
    refuses(
        lambda: system.draw(fee=2_000, quiet=True),
        "group fee 0.0A too small (needs 1mA more)",
    )
    system.draw(fee=3_000)
    assert system.state()["drawn"] == 1


# ============================== authorization ============================= #


def test_only_the_creator_can_initialize(algorand) -> None:
    system = System(algorand, entrants=1, initialise=False)
    refuses(
        lambda: system.lottery.send.call(
            AppClientMethodCallParams(
                method="initialize",
                args=[system.beacon.app_id, TICKET_PRICE],
                sender=system.stranger.address,
                signer=system.stranger.signer,
            ),
            send_params=QUIET,
        ),
        "operator only",
    )


def test_initialize_is_once_only(algorand) -> None:
    system = System(algorand, entrants=1)
    refuses(
        lambda: system.lottery.send.call(
            AppClientMethodCallParams(
                method="initialize",
                args=[system.beacon.app_id, TICKET_PRICE],
            ),
            send_params=QUIET,
        ),
        "already initialised",
    )


def test_initialize_rejects_a_missing_beacon_or_a_silly_price(algorand) -> None:
    system = System(algorand, entrants=1, initialise=False)

    def initialise(beacon: int, price: int):
        return system.lottery.send.call(
            AppClientMethodCallParams(
                method="initialize", args=[beacon, price]
            ),
            send_params=QUIET,
        )

    refuses(
        lambda: initialise(0, TICKET_PRICE),
        "a beacon application id is required",
    )
    refuses(
        lambda: initialise(system.beacon.app_id, 0),
        "a ticket must cost something",
    )
    refuses(
        lambda: initialise(system.beacon.app_id, MAX_TICKET_PRICE + 1),
        "ticket too dear",
    )
    # None of the three refusals left anything behind.
    initialise(system.beacon.app_id, TICKET_PRICE)
    assert system.state()["ticket"] == TICKET_PRICE


def test_entering_before_initialization_is_refused(algorand) -> None:
    system = System(algorand, entrants=1, initialise=False)
    refuses(
        lambda: enter(
            algorand,
            system.lottery,
            system.entrants[0],
            ticket_price=TICKET_PRICE,
            quiet=True,
        ),
        "not initialised",
    )


def test_only_the_operator_can_commit(algorand) -> None:
    system = System(algorand, entrants=1)
    system.enter_all()
    refuses(
        lambda: commit(
            algorand,
            system.lottery,
            system.stranger,
            lead=MIN_LEAD_ROUNDS,
            quiet=True,
        ),
        "operator only",
    )


def test_commit_is_once_only(algorand) -> None:
    system = System(algorand, entrants=1)
    system.enter_all()
    system.commit()
    refuses(
        lambda: commit(
            algorand,
            system.lottery,
            system.operator,
            lead=MIN_LEAD_ROUNDS,
            quiet=True,
        ),
        "already committed",
    )


def test_anyone_may_draw(algorand) -> None:
    """The beacon decides the winner, so gatekeeping the draw buys nothing."""
    system = System(algorand, entrants=3)
    system.run_to_the_draw()
    index = system.draw(caller=system.stranger)
    assert system.state()["winner"] == system.entrants[index].address
    assert system.state()["winner"] != system.stranger.address


# ============================== the entry gate ============================ #


def test_underpaying_the_box_minimum_balance_is_refused(algorand) -> None:
    system = System(algorand, entrants=1)
    refuses(
        lambda: enter(
            algorand,
            system.lottery,
            system.entrants[0],
            ticket_price=TICKET_PRICE,
            amount=TICKET_PRICE + ENTRY_BOX_COST - 1,
            quiet=True,
        ),
        "pay the ticket price plus the box",
    )


def test_overpaying_is_refused_too(algorand) -> None:
    """Exactly, not at least: a pot that is not `n x ticket` cannot be split."""
    system = System(algorand, entrants=1)
    refuses(
        lambda: enter(
            algorand,
            system.lottery,
            system.entrants[0],
            ticket_price=TICKET_PRICE,
            amount=TICKET_PRICE + ENTRY_BOX_COST + 1,
            quiet=True,
        ),
        "pay the ticket price plus the box",
    )


def test_paying_a_different_account_is_refused(algorand) -> None:
    system = System(algorand, entrants=1)
    entrant = system.entrants[0]
    payment = algorand.create_transaction.payment(
        PaymentParams(
            sender=entrant.address,
            receiver=system.stranger.address,
            amount=AlgoAmount.from_micro_algo(TICKET_PRICE + ENTRY_BOX_COST),
        )
    )
    refuses(
        lambda: system.lottery.send.call(
            AppClientMethodCallParams(
                method="enter",
                args=[TransactionWithSigner(payment, entrant.signer)],
                sender=entrant.address,
                signer=entrant.signer,
                box_references=[entry_box_reference(0)],
            ),
            send_params=QUIET,
        ),
        "pay the lottery, not someone else",
    )


def test_entering_on_somebody_elses_payment_is_refused(algorand) -> None:
    """Otherwise a bystander's payment buys the caller an entry."""
    system = System(algorand, entrants=1)
    entrant = system.entrants[0]
    payment = algorand.create_transaction.payment(
        PaymentParams(
            sender=entrant.address,
            receiver=system.lottery.app_address,
            amount=AlgoAmount.from_micro_algo(TICKET_PRICE + ENTRY_BOX_COST),
        )
    )
    refuses(
        lambda: system.lottery.send.call(
            AppClientMethodCallParams(
                method="enter",
                args=[TransactionWithSigner(payment, entrant.signer)],
                sender=system.stranger.address,
                signer=system.stranger.signer,
                box_references=[entry_box_reference(0)],
            ),
            send_params=QUIET,
        ),
        "pay for your own ticket",
    )


def test_an_extra_transaction_in_the_group_is_refused(algorand) -> None:
    system = System(algorand, entrants=1)
    entrant = system.entrants[0]
    payment = algorand.create_transaction.payment(
        PaymentParams(
            sender=entrant.address,
            receiver=system.lottery.app_address,
            amount=AlgoAmount.from_micro_algo(TICKET_PRICE + ENTRY_BOX_COST),
        )
    )
    call = system.lottery.params.call(
        AppClientMethodCallParams(
            method="enter",
            args=[TransactionWithSigner(payment, entrant.signer)],
            sender=entrant.address,
            signer=entrant.signer,
            box_references=[entry_box_reference(0)],
        )
    )
    group = algorand.new_group().add_app_call_method_call(call)
    group.add_payment(
        PaymentParams(
            sender=entrant.address,
            signer=entrant.signer,
            receiver=entrant.address,
            amount=AlgoAmount.from_micro_algo(0),
        )
    )
    refuses(lambda: group.send(QUIET), "expected payment + app call")


def test_entry_closes_at_the_commit(algorand) -> None:
    system = System(algorand, entrants=2)
    system.enter_all()
    system.commit()
    refuses(
        lambda: enter(
            algorand,
            system.lottery,
            system.entrants[0],
            ticket_price=TICKET_PRICE,
            quiet=True,
        ),
        "entries are closed",
    )


def test_a_commit_with_nobody_in_it_is_refused(algorand) -> None:
    system = System(algorand, entrants=1)
    refuses(lambda: system.commit(), "nobody entered")


def test_the_lead_has_a_floor_and_a_ceiling(algorand) -> None:
    system = System(algorand, entrants=1)
    system.enter_all()
    refuses(
        lambda: commit(
            algorand, system.lottery, system.operator,
            lead=MIN_LEAD_ROUNDS - 1, quiet=True,
        ),
        "too close to predict",
    )
    refuses(
        lambda: commit(
            algorand, system.lottery, system.operator,
            lead=MAX_LEAD_ROUNDS + 1, quiet=True,
        ),
        "lead is too long",
    )


def test_the_target_round_is_a_multiple_of_the_beacon_period(algorand) -> None:
    system = System(algorand, entrants=1)
    system.enter_all()
    target = system.commit()
    state = system.state()
    assert target % 8 == 0
    assert state["target"] == target
    assert state["refund"] == target + DRAW_WINDOW_ROUNDS


# ================================ the draw ================================ #


def test_the_draw_refuses_before_a_commit(algorand) -> None:
    system = System(algorand, entrants=1)
    system.enter_all()
    refuses(lambda: system.draw(quiet=True), "nothing committed yet")


def test_the_draw_refuses_before_the_target_round(algorand) -> None:
    system = System(algorand, entrants=2)
    system.enter_all()
    system.commit()
    refuses(lambda: system.draw(quiet=True), "target round is future")


def test_the_draw_refuses_a_silent_beacon(algorand) -> None:
    """The value's absence comes back as an empty slice, not an error.

    This is why the contract calls ARC-21's `get` and not `must_get`. A
    callee's assert message does not survive an inner application call, so
    `must_get` would hand the reader a program counter from somebody else's
    program instead of this sentence.
    """
    system = System(algorand, entrants=2)
    system.enter_all()
    target = system.commit()
    system.reach(target)
    refuses(lambda: system.draw(quiet=True), "beacon published nothing")

    # Publishing for a neighbouring round does not help: the committed round
    # is the only one the contract will ask about.
    system.publish(target + 8)
    refuses(lambda: system.draw(quiet=True), "beacon published nothing")


def test_the_draw_refuses_after_the_window_closes(algorand) -> None:
    system = System(algorand, entrants=2)
    system.enter_all()
    target = system.commit()
    system.reach(target)
    system.publish(target)
    system.reach(target + DRAW_WINDOW_ROUNDS)
    refuses(lambda: system.draw(quiet=True), "draw window closed")


def test_the_draw_refuses_a_second_call(algorand) -> None:
    system = System(algorand, entrants=3)
    system.run_to_the_draw()
    system.draw()
    refuses(lambda: system.draw(quiet=True), "already drawn")


# ============================== settling up =============================== #


def test_sweep_refuses_before_a_draw(algorand) -> None:
    system = System(algorand, entrants=2)
    system.enter_all()
    refuses(lambda: system.settle("sweep", 0, quiet=True), "no draw yet")


def test_sweeping_the_same_entry_twice_is_refused(algorand) -> None:
    system = System(algorand, entrants=2)
    system.run_to_the_draw()
    system.draw()
    assert system.settle("sweep", 0) == ENTRY_BOX_COST
    refuses(lambda: system.settle("sweep", 0, quiet=True), "no such entry")


def test_refund_refuses_while_the_draw_is_still_possible(algorand) -> None:
    system = System(algorand, entrants=2)
    system.enter_all()
    target = system.commit()
    refuses(
        lambda: system.settle("refund", 0, quiet=True), "draw still possible"
    )
    system.reach(target)
    refuses(
        lambda: system.settle("refund", 0, quiet=True), "draw still possible"
    )


def test_refund_refuses_after_a_draw(algorand) -> None:
    """The two exits are exclusive, and the flag is what makes them so."""
    system = System(algorand, entrants=2)
    system.enter_all()
    target = system.commit()
    system.reach(target)
    system.publish(target)
    system.draw()
    system.reach(target + DRAW_WINDOW_ROUNDS)
    refuses(
        lambda: system.settle("refund", 0, quiet=True),
        "the draw already happened",
    )


def test_refunding_the_same_entry_twice_is_refused(algorand) -> None:
    system = System(algorand, entrants=2)
    system.enter_all()
    target = system.commit()
    system.reach(target + DRAW_WINDOW_ROUNDS)
    assert system.settle("refund", 0) == TICKET_PRICE + ENTRY_BOX_COST
    refuses(lambda: system.settle("refund", 0, quiet=True), "no such entry")


def test_the_entry_box_holds_the_account_that_paid(algorand) -> None:
    system = System(algorand, entrants=3)
    system.enter_all()
    for index, entrant in enumerate(system.entrants):
        assert read_entry(algorand, system.lottery.app_id, index) == (
            entrant.address
        )


# ============================== the lifecycle ============================= #


def test_update_and_delete_are_refused(algorand) -> None:
    system = System(algorand, entrants=1)
    spec = json.loads(LOTTERY_SPEC.read_text(encoding="utf-8"))
    refuses(
        lambda: algorand.send.app_update(
            AppUpdateParams(
                app_id=system.lottery.app_id,
                sender=system.operator.address,
                signer=system.operator.signer,
                on_complete=OnComplete.UpdateApplicationOC,
                approval_program=base64.b64decode(
                    spec["byteCode"]["approval"]
                ),
                clear_state_program=base64.b64decode(
                    spec["byteCode"]["clear"]
                ),
            ),
            send_params=QUIET,
        ),
        "the lottery is immutable",
    )
    refuses(
        lambda: algorand.send.app_delete(
            AppDeleteParams(
                app_id=system.lottery.app_id,
                sender=system.operator.address,
                signer=system.operator.signer,
            ),
            send_params=QUIET,
        ),
        "the lottery is immutable",
    )


# ============================ the opcode budget =========================== #


def test_the_draw_fits_the_default_opcode_budget(algorand) -> None:
    """A cross-application read is cheap, and the numbers say how cheap.

    `draw` hashes 32 bytes, calls another application and sends a payment.
    The real pool is 1,400: 700 for the outer call and 700 for the inner
    application call. An inner payment adds nothing to it.

    `app-budget-added` below says 2,100, and that field is not the pool.
    `ledger/simulation/tracer.go` adds 700 per inner transaction *group*
    whatever the group holds, while `data/transactions/logic/eval.go` tops
    the pool up only for an inner `ApplicationCallTx`; `draw` issues two
    separate submits, so the report counts 700 twice where the pool counts it
    once. It is asserted here because it is what the API returns, not because
    it is the budget. Consumption is the honest field, and 231 leaves room
    against either number, so there is no `ensure_budget` anywhere.

    Eight of those 231 units are the `Won` event: two stack ops to keep the
    winner and the prize alive past the payment, then `itob`, `concat`,
    `pushbytes`, `swap`, `concat`, `log`. An event is a log write inside the
    call that emitted it, so it costs opcodes and neither a fee nor a
    transaction.
    """
    system = System(algorand, entrants=3)
    system.run_to_the_draw()
    group = algorand.new_group().add_app_call_method_call(
        system.lottery.params.call(
            AppClientMethodCallParams(
                method="draw",
                args=[],
                sender=system.stranger.address,
                signer=system.stranger.signer,
                static_fee=AlgoAmount.from_micro_algo(3_000),
                app_references=[system.beacon.app_id],
            )
        )
    )
    result = group.simulate(allow_unnamed_resources=True)
    outcome = result.simulate_response["txn-groups"][0]
    assert outcome.get("failure-message") is None, outcome
    # The simulate report's figure, not the pool. See the docstring.
    assert outcome["app-budget-added"] == 2_100, outcome["app-budget-added"]
    assert outcome["app-budget-consumed"] == 231, outcome
    assert len(outcome["txn-results"][0]["txn-result"]["inner-txns"]) == 2


def test_refunds_stop_exactly_at_zero(algorand) -> None:
    """The pot cannot be driven below what the contract took in.

    Each refund removes one ticket from the pot and one box from the map, and
    there are exactly as many boxes as entries, so the pot lands on zero and
    every further call -- for an index already refunded or for one that never
    existed -- is refused before any arithmetic happens.
    """
    system = System(algorand, entrants=3)
    system.enter_all()
    target = system.commit()
    system.reach(target + DRAW_WINDOW_ROUNDS)

    expected = 3 * TICKET_PRICE
    for index in range(3):
        system.settle("refund", index)
        expected -= TICKET_PRICE
        assert system.state()["pot"] == expected
    assert system.state()["pot"] == 0

    for index in (0, 1, 2, 3, 99):
        refuses(
            lambda i=index: system.settle("refund", i, quiet=True),
            "no such entry",
        )
    assert_app_sits_at_its_floor(algorand, system.lottery, entries=0)


def test_an_operator_who_never_commits_cannot_strand_the_money(algorand) -> None:
    """The exit does not depend on the operator turning up.

    `initialize` writes a refund round before the operator has done anything
    else, so an operator who takes the tickets and then goes quiet is on the
    same footing as a beacon that does. Once that deadline passes, entries
    are refused and every entrant can take their stake back -- with no
    `commit` ever having run, and so no target round, no beacon read and no
    draw in the contract's history.
    """
    system = System(algorand, entrants=3)
    system.enter_all()
    deadline = system.state()["refund"]
    assert deadline > 0, "initialize must set the refund round"
    assert system.state()["target"] == 0

    refuses(
        lambda: system.settle("refund", 0, quiet=True), "draw still possible"
    )
    system.reach(deadline)

    refuses(
        lambda: enter(
            algorand, system.lottery, system.entrants[0],
            ticket_price=TICKET_PRICE, quiet=True,
        ),
        "entry window closed",
    )
    refuses(lambda: system.draw(quiet=True), "nothing committed yet")

    stake = TICKET_PRICE + ENTRY_BOX_COST
    before = [algo_balance(algorand, one.address) for one in system.entrants]
    for index in range(3):
        assert system.settle("refund", index) == stake
    after = [algo_balance(algorand, one.address) for one in system.entrants]
    assert [now - was for was, now in zip(before, after)] == [stake] * 3
    assert system.state()["pot"] == 0
    assert_app_sits_at_its_floor(algorand, system.lottery, entries=0)


def test_the_entry_window_is_set_at_initialization(algorand) -> None:
    """And `commit` replaces it with the end of the draw window."""
    system = System(algorand, entrants=1)
    opened = system.state()["refund"]
    assert 0 < opened <= current_round(algorand) + ENTRY_WINDOW_ROUNDS
    system.enter_all()
    target = system.commit()
    assert system.state()["refund"] == target + DRAW_WINDOW_ROUNDS


def test_a_commit_after_the_entry_window_is_refused(algorand) -> None:
    """A late commit would hand `draw` a modulus larger than its map.

    Once the entry deadline passes, entrants can refund and every refund
    deletes a box without lowering `entry_count`. A `commit` accepted after
    that point would set a target round whose draw indexes a map smaller than
    the count it divides by, so the commit has to be refused instead.
    """
    system = System(algorand, entrants=2)
    system.enter_all()
    system.reach(system.state()["refund"])
    refuses(
        lambda: commit(
            algorand, system.lottery, system.operator,
            lead=MIN_LEAD_ROUNDS, quiet=True,
        ),
        "entry window closed",
    )
    # The exit is still open, which is the point of refusing the commit.
    assert system.settle("refund", 0) == TICKET_PRICE + ENTRY_BOX_COST


def test_draw_needs_no_declared_references_at_all(algorand) -> None:
    """The chapter says you may delete `app_references`; this is why it may.

    algokit-utils simulates every call before it sends it, with unnamed
    resources allowed, and copies whatever the program reached into the real
    transaction. Both the beacon and the winner's box arrive that way. The
    beacon is declared in `scripts/localnet_helpers.py` anyway, because it is
    the only one of the two a caller who does not pre-simulate could name.
    """
    system = System(algorand, entrants=5)
    system.run_to_the_draw()
    result = system.lottery.send.call(
        AppClientMethodCallParams(
            method="draw",
            args=[],
            sender=system.stranger.address,
            signer=system.stranger.signer,
            static_fee=AlgoAmount.from_micro_algo(3_000),
        )
    )
    index = int(result.abi_return)
    assert index == winner_index(DEMO_BEACON_VALUE, 5)

    submitted = result.confirmations[0]["txn"]["txn"]
    assert submitted["apfa"] == [system.beacon.app_id], submitted.get("apfa")
    declared = [base64.b64decode(ref["n"]) for ref in submitted["apbx"]]
    assert declared == [entry_box_reference(index)], declared
