from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AppClientMethodCallParams,
    PaymentParams,
    SendParams,
)
from algosdk import encoding
from algosdk.atomic_transaction_composer import TransactionWithSigner

MICRO_UNITS = 10**6

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "smart_contracts" / "artifacts"
LOTTERY_SPEC = ARTIFACTS / "lottery" / "Lottery.arc56.json"
BEACON_SPEC = ARTIFACTS / "beacon_stub" / "BeaconStub.arc56.json"

# --------------------------------------------------------------------------
# THE ONE LINE THAT CHOOSES A CHAIN.
#
# 0 means "deploy the stub in smart_contracts/beacon_stub/ and use that".
# 600011887 is the ARC-21 beacon on TestNet; 1615566206 is the MainNet one.
# The lottery contract does not change either way -- it stores whatever
# application id `initialize` was handed and calls `get` on it.
# --------------------------------------------------------------------------
BEACON_APP_ID = 0

TESTNET_BEACON_APP_ID = 600011887
MAINNET_BEACON_APP_ID = 1615566206

# Mirrors of the constants in `smart_contracts/lottery/contract.py`. They are
# restated rather than imported because that module is Algorand Python:
# importing it into a client process pulls in the testing shim, and a client
# that needs six integers should not need a compiler.
BEACON_ROUND_MODULUS = 8
MIN_LEAD_ROUNDS = 16
MAX_LEAD_ROUNDS = 1_000
ENTRY_WINDOW_ROUNDS = 1_000
DRAW_WINDOW_ROUNDS = 300
MAX_ENTRANTS = 10_000
MAX_TICKET_PRICE = 1_000_000_000

BOX_PREFIX = b"e_"
ENTRY_KEY_SIZE = len(BOX_PREFIX) + 8
ENTRY_DATA_SIZE = 32
ENTRY_BOX_COST = 2_500 + 400 * (ENTRY_KEY_SIZE + ENTRY_DATA_SIZE)

# The two minimum balances a deployed lottery moves, and they are held by two
# different accounts.
#
# The APPLICATION account owes the plain account base and nothing else until
# a box exists. Global state is not its bill.
#
# The CREATOR owes the app itself plus that app's whole global schema: seven
# uint64 slots at 28,500 and one byte-slice slot at 50,000. That money is
# locked in the operator's own account for as long as the app exists, and no
# payment to the application address touches it.
#
# `assert_app_sits_at_its_floor` checks both numbers against the ledger's own
# `min-balance` rather than trusting this arithmetic.
ACCOUNT_BASE_MBR = 100_000
GLOBAL_UINT_MBR = 28_500
GLOBAL_BYTES_MBR = 50_000
LOTTERY_GLOBAL_UINTS = 7
LOTTERY_GLOBAL_BYTES = 1
LOTTERY_APP_BASE_MBR = ACCOUNT_BASE_MBR
CREATOR_APP_MBR = (
    ACCOUNT_BASE_MBR
    + LOTTERY_GLOBAL_UINTS * GLOBAL_UINT_MBR
    + LOTTERY_GLOBAL_BYTES * GLOBAL_BYTES_MBR
)

# Fees, counted as transactions rather than guessed. Every inner transaction
# is `fee=UInt64(0)`, so the outer call pays for the whole tree.
FEE_ENTER = 1_000  # the app call; the payment beside it pays its own
FEE_DRAW = 3_000  # app call + inner beacon call + inner payment
FEE_SETTLE = 2_000  # app call + inner payment

# A beacon value fixed so that the winner is the same on every run and the
# workflow's output can be compared line by line against the book. Chosen so
# the winner is neither the first entrant nor the last, which is the only
# thing about it that is not arbitrary: with five entrants this value picks
# index 3, and with three it picks index 1.
DEMO_BEACON_VALUE = bytes.fromhex(
    "96831c40ade5005c1bf2f775ebe32eacbede7d3aeaf755e9f9a64444eb481b90"
)

# Several calls below are meant to fail, and algokit-utils logs a whole signed
# transaction dump for each one.
QUIET = SendParams(suppress_log=True)


def get_localnet_algorand() -> AlgorandClient:
    algorand = AlgorandClient.default_localnet()
    try:
        algorand.client.algod.status()
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "LocalNet is not running. Start it with `algokit localnet start`."
        ) from exc
    algorand.set_suggested_params_cache_timeout(0)
    return algorand


def require_artifacts() -> None:
    """Fail with the build command rather than with a FileNotFoundError."""
    missing = [p for p in (LOTTERY_SPEC, BEACON_SPEC) if not p.exists()]
    if missing:
        names = ", ".join(str(p.relative_to(ROOT)) for p in missing)
        raise RuntimeError(
            f"Missing build artifacts ({names}). "
            "Run `algokit project run build` first."
        )


# ------------------------------ chain reading ---------------------------- #


def current_round(algorand: AlgorandClient) -> int:
    return algorand.client.algod.status()["last-round"]


def algo_balance(algorand: AlgorandClient, address: str) -> int:
    return algorand.account.get_information(address).amount.micro_algo


def min_balance(algorand: AlgorandClient, address: str) -> int:
    """What the ledger itself says this account may not go below."""
    return algorand.account.get_information(address).min_balance.micro_algo


def fund_account(algorand: AlgorandClient, dispenser, account, *, amount: int):
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            signer=dispenser.signer,
            receiver=account.address,
            amount=AlgoAmount.from_micro_algo(amount),
        ),
        send_params=QUIET,
    )


def advance_to(algorand: AlgorandClient, funder, target_round: int) -> int:
    """Move the chain past `target_round`.

    LocalNet in developer mode produces one block per submitted transaction
    and does not tick on its own, so waiting for a round means causing it.
    Each padding payment needs a distinct `note`: without one the second is
    byte-identical to the first and comes back `transaction already in
    ledger`.
    """
    sent = 0
    while current_round(algorand) <= target_round:
        # The note carries a counter rather than the round, because two
        # payments can be built while `last-round` still reads the same
        # number and two identical notes make two identical transactions.
        algorand.send.payment(
            PaymentParams(
                sender=funder.address,
                signer=funder.signer,
                receiver=funder.address,
                amount=AlgoAmount.from_micro_algo(0),
                note=f"pad-{sent}-{current_round(algorand)}".encode(),
            ),
            send_params=QUIET,
        )
        sent += 1
    return current_round(algorand)


STATE_KEYS = (
    "beacon",
    "ticket",
    "entries",
    "pot",
    "target",
    "refund",
    "drawn",
    "winner",
)


def read_state(algorand: AlgorandClient, app_id: int) -> dict:
    """Every global key the lottery declares, decoded."""
    info = algorand.client.algod.application_info(app_id)
    out: dict[str, object] = {}
    for entry in info["params"].get("global-state", []):
        key = base64.b64decode(entry["key"]).decode()
        value = entry["value"]
        if value["type"] == 1:
            raw = base64.b64decode(value["bytes"])
            out[key] = encoding.encode_address(raw) if len(raw) == 32 else raw
        else:
            out[key] = value["uint"]
    for key in STATE_KEYS:
        out.setdefault(key, 0)
    return out


def entry_box_reference(index: int) -> bytes:
    return BOX_PREFIX + index.to_bytes(8, "big")


def read_entry(algorand: AlgorandClient, app_id: int, index: int) -> str:
    box = algorand.client.algod.application_box_by_name(
        app_id, entry_box_reference(index)
    )
    return encoding.encode_address(base64.b64decode(box["value"]))


def box_names(algorand: AlgorandClient, app_id: int) -> list[bytes]:
    boxes = algorand.client.algod.application_boxes(app_id)["boxes"]
    return [base64.b64decode(box["name"]) for box in boxes]


# ------------------------------- deployment ------------------------------ #


def deploy_beacon_stub(algorand: AlgorandClient, publisher):
    """Deploy the LocalNet stand-in and return its AppClient."""
    require_artifacts()
    factory = algorand.client.get_app_factory(
        app_spec=BEACON_SPEC.read_text(),
        default_sender=publisher.address,
        default_signer=publisher.signer,
    )
    client, _ = factory.send.bare.create()
    # Global-state only, no boxes and no inner transactions: the stub's own
    # account never has to pay for anything, so it needs no float.
    return client


def deploy_lottery(
    algorand: AlgorandClient,
    operator,
    *,
    beacon_app_id: int,
    ticket_price: int,
    initialise: bool = True,
):
    """Deploy, seed to exactly the minimum balance, and initialise."""
    require_artifacts()
    factory = algorand.client.get_app_factory(
        app_spec=LOTTERY_SPEC.read_text(),
        default_sender=operator.address,
        default_signer=operator.signer,
    )
    client, _ = factory.send.bare.create()
    # Exactly the floor, not a round number above it. Every later Algo the
    # application account holds arrives with an entry that owes it, which is
    # what makes the balance readable as an accounting statement. The global
    # schema is NOT part of this payment: that bill went to the creator when
    # the app was created and stays there.
    algorand.send.payment(
        PaymentParams(
            sender=operator.address,
            signer=operator.signer,
            receiver=client.app_address,
            amount=AlgoAmount.from_micro_algo(LOTTERY_APP_BASE_MBR),
        ),
        send_params=QUIET,
    )
    if initialise:
        client.send.call(
            AppClientMethodCallParams(
                method="initialize", args=[beacon_app_id, ticket_price]
            )
        )
    return client


def resolve_beacon(algorand: AlgorandClient, publisher) -> tuple[int, object]:
    """Return `(app_id, stub_client_or_None)` for the configured beacon.

    `BEACON_APP_ID = 0` means "there is no beacon on this chain, deploy the
    stub". Any other value is a beacon somebody else operates, which is the
    TestNet and MainNet case and the one the contract was written for.
    """
    if BEACON_APP_ID:
        return BEACON_APP_ID, None
    stub = deploy_beacon_stub(algorand, publisher)
    return stub.app_id, stub


# --------------------------------- calls --------------------------------- #


def enter(
    algorand: AlgorandClient,
    lottery,
    entrant,
    *,
    ticket_price: int,
    amount: int | None = None,
    quiet: bool = False,
):
    """One entry: a payment for ticket + box, and the app call beside it."""
    index = read_state(algorand, lottery.app_id)["entries"]
    payment = algorand.create_transaction.payment(
        PaymentParams(
            sender=entrant.address,
            receiver=lottery.app_address,
            amount=AlgoAmount.from_micro_algo(
                ticket_price + ENTRY_BOX_COST if amount is None else amount
            ),
        )
    )
    result = lottery.send.call(
        AppClientMethodCallParams(
            method="enter",
            args=[TransactionWithSigner(payment, entrant.signer)],
            sender=entrant.address,
            signer=entrant.signer,
            static_fee=AlgoAmount.from_micro_algo(FEE_ENTER),
            box_references=[entry_box_reference(int(index))],
        ),
        send_params=QUIET if quiet else None,
    )
    return int(result.abi_return)


def commit(
    algorand: AlgorandClient, lottery, operator, *, lead: int,
    quiet: bool = False,
) -> int:
    """Close entries. Returns the target round the contract chose."""
    return commit_with_round(
        algorand, lottery, operator, lead=lead, quiet=quiet
    )[0]


def commit_with_round(
    algorand: AlgorandClient, lottery, operator, *, lead: int,
    quiet: bool = False,
) -> tuple[int, int]:
    """Returns `(target_round, the round the commit was confirmed in)`.

    The confirmed round has to come out of the confirmation rather than out
    of a `status()` read afterwards. `commit` computes its target from
    `Global.round` at evaluation time; by the time a client asks the node
    what the last round is, one more block may have been made, and the lead
    computed from that reads one short of the sixteen the contract enforced.
    """
    result = lottery.send.call(
        AppClientMethodCallParams(
            method="commit",
            args=[lead],
            sender=operator.address,
            signer=operator.signer,
        ),
        send_params=QUIET if quiet else None,
    )
    return int(result.abi_return), int(result.confirmation["confirmed-round"])


def publish(beacon_client, publisher, *, rnd: int, value: bytes) -> None:
    beacon_client.send.call(
        AppClientMethodCallParams(
            method="publish",
            args=[rnd, value],
            sender=publisher.address,
            signer=publisher.signer,
        )
    )


def draw_call(
    lottery, caller, *, beacon_app_id: int, fee: int = FEE_DRAW,
    quiet: bool = False,
):
    """Anyone may call this; the beacon decides the answer, not the caller.

    `app_references` names the beacon because the contract calls it. The
    winner's box is NOT declared: which box `draw` reads depends on a value
    that does not exist yet when the group is built, so the client discovers
    it by simulating first, which is what `populate_app_call_resources` does
    on every call algokit-utils sends.

    Returns the whole result, because the draw says the same thing twice: an
    ABI return for whoever called it, and a `Won` log for whoever is
    listening.
    """
    return lottery.send.call(
        AppClientMethodCallParams(
            method="draw",
            args=[],
            sender=caller.address,
            signer=caller.signer,
            static_fee=AlgoAmount.from_micro_algo(fee),
            app_references=[beacon_app_id],
        ),
        send_params=QUIET if quiet else None,
    )


def draw(
    lottery, caller, *, beacon_app_id: int, fee: int = FEE_DRAW,
    quiet: bool = False,
) -> int:
    """The winning index, for callers that do not care about the log."""
    result = draw_call(
        lottery, caller, beacon_app_id=beacon_app_id, fee=fee, quiet=quiet
    )
    return int(result.abi_return)


# The ARC-28 event `draw` emits, found by the first four bytes of the hash of
# its signature. A listener needs the signature and nothing else -- not this
# application's source, and not a poll of its state.
WON_EVENT_SIGNATURE = b"Won(address,uint64)"
WON_EVENT_PREFIX = hashlib.new("sha512_256", WON_EVENT_SIGNATURE).digest()[:4]


def won_event(result) -> tuple[str, int]:
    """The winner and the prize, read back out of the draw's own logs.

    `confirmation["logs"]` arrives base64-encoded over the REST API. After
    the four-byte prefix the body is the event's ARC-4 encoding: a 32-byte
    address and a big-endian uint64, neither of them length-prefixed because
    both are fixed size.
    """
    logs = [
        entry if isinstance(entry, bytes) else base64.b64decode(entry)
        for entry in result.confirmation.get("logs", [])
    ]
    emitted = [entry for entry in logs if entry[:4] == WON_EVENT_PREFIX]
    assert len(emitted) == 1, f"expected one Won event, got {len(emitted)}"
    body = emitted[0][4:]
    return encoding.encode_address(body[:32]), int.from_bytes(body[32:40], "big")


def settle(
    lottery, caller, *, method: str, index: int, quiet: bool = False
) -> int:
    """`sweep` after a draw, `refund` after the draw window closes."""
    result = lottery.send.call(
        AppClientMethodCallParams(
            method=method,
            args=[index],
            sender=caller.address,
            signer=caller.signer,
            static_fee=AlgoAmount.from_micro_algo(FEE_SETTLE),
            box_references=[entry_box_reference(index)],
        ),
        send_params=QUIET if quiet else None,
    )
    return int(result.abi_return)


# ------------------------------- assertions ------------------------------ #


def assert_app_sits_at_its_floor(
    algorand: AlgorandClient, lottery, *, entries: int
) -> int:
    """The application account owns nothing it does not owe.

    Two claims, checked against two independent sources. The ledger's own
    `min-balance` must equal the account base plus one box's worth per entry,
    which is the arithmetic in this file; and the account's balance must
    equal that minimum exactly, which says the pot has been paid out and no
    Algo is stranded.
    """
    expected = LOTTERY_APP_BASE_MBR + entries * ENTRY_BOX_COST
    floor = min_balance(algorand, lottery.app_address)
    assert floor == expected, f"min-balance {floor}, expected {expected}"
    held = algo_balance(algorand, lottery.app_address)
    assert held == floor, f"balance {held} is not the minimum {floor}"
    return floor


def assert_creator_holds_the_schema(
    algorand: AlgorandClient, operator, *, before: int, apps: int
) -> int:
    """Creating an app raises the CREATOR's minimum balance, not the app's.

    `before` is the operator's `min-balance` before any deployment. Each
    lottery deployed adds the app itself plus its global schema, and no
    payment to the application address reduces it.
    """
    expected = before + apps * CREATOR_APP_MBR
    floor = min_balance(algorand, operator.address)
    assert floor == expected, f"creator min-balance {floor}, want {expected}"
    return floor


def refuses(call, expected: str) -> None:
    """Run `call` and require it to fail naming `expected`."""
    try:
        call()
    except Exception as error:  # noqa: BLE001
        text = f"{getattr(error, 'message', '')}\n{error}"
        assert expected in text, (
            f"failed, but not for {expected!r}: {text[:300]}"
        )
        return
    raise AssertionError(f"expected a failure naming {expected!r}, got none")
