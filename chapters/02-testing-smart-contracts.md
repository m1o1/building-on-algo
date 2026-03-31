\newpage

# Testing Smart Contracts

On a blockchain, deployed code is immutable. A bug in a web application means a hotfix and an apology. A bug in a smart contract means funds locked or stolen --- permanently. There is no rollback, no patch, no "we'll fix it in the next release." A single missing validation check can drain millions before anyone reacts --- and once deployed, the contract cannot be fixed.

Testing is not optional. It is the most important skill in this book after the mental model itself.

In Chapter 1 you built the mental model --- how accounts work, how transactions execute atomically, how contracts validate rather than run continuously. You deployed a HelloAlgorand contract and called it from a script. That was the development loop: edit, compile, deploy, interact. Now we add the critical fourth leg: **test**.

This chapter follows a deliberate arc. First, we build a simplified vesting contract --- small enough to read in one sitting but complex enough to need real tests. Then we write comprehensive tests against it: *positive tests* that verify correct behavior, *negative tests* that verify security checks, and simulate-based tests that construct attacks without submitting them. Most unusually, we will also write tests that deliberately fail --- those failing tests reveal exactly what the simplified contract cannot handle, and those gaps become the specification for the production contract in Chapter 3.

An important distinction before we begin: smart contract testing has two layers. **Contract logic testing** verifies that the on-chain code behaves correctly --- the right assertions fire, the math is accurate, state transitions are safe. **Client code testing** verifies that your off-chain scripts compose transactions correctly, encode ABI arguments properly, and handle errors gracefully. This chapter focuses on contract logic testing, which is the blockchain-specific skill. Client code testing is standard Python testing (pytest, mocking, assertions) and does not require special tooling. The *integration tests* we write here test *both layers simultaneously* --- when one fails, the bug could be in the contract or in the client code that calls it. The *unit tests* test *contract logic only*.

By the end of this chapter, you will have a working test suite and the testing patterns you will use for every contract in this book.


## The Simplified Vesting Contract

We need a contract to test. Rather than testing HelloAlgorand (too trivial to teach anything transferable), we will build a simplified version of the token vesting contract that Chapter 3 covers in full. This version strips away everything that is not essential to the core idea: one beneficiary, linear vesting with a cliff, admin deposits tokens, beneficiary claims.

Here is what "simplified" means in practice. The production contract in Chapter 3 uses box storage for unlimited beneficiaries, wide arithmetic for overflow safety, a separate `revoke` method, schedule cleanup with MBR refunds, and read-only query methods. Our simplified version uses global state (one beneficiary only), plain `UInt64` arithmetic, no revocation, and a combined initialize-and-deposit method. It is roughly 90 lines of PuyaPy compared to Chapter 3's 200+.

Here is the complete contract. It has five methods: `create` stores the deployer as admin, `opt_in_to_asset` prepares the contract to hold tokens, `initialize` accepts a token deposit and records the vesting schedule, `claim` releases tokens proportional to elapsed time, and `get_claimable` lets anyone check how many tokens are currently available. A sixth bare method, `reject_lifecycle`, makes the contract immutable by rejecting update and delete calls. Read the contract through, then we will discuss the key points:

```python
from algopy import (
    ARC4Contract,
    Asset,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
)


class SimpleVesting(ARC4Contract):
    """A simplified vesting contract for one beneficiary.
    Tokens vest linearly from start to vesting_end,
    with nothing claimable before cliff_end."""

    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.asset_id = GlobalState(UInt64(0))
        self.beneficiary = GlobalState(Bytes())
        self.total_amount = GlobalState(UInt64(0))
        self.claimed_amount = GlobalState(UInt64(0))
        self.start_time = GlobalState(UInt64(0))
        self.cliff_end = GlobalState(UInt64(0))
        self.vesting_end = GlobalState(UInt64(0))

    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Record who deployed this contract."""
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(
        allow_actions=[
            "UpdateApplication",
            "DeleteApplication",
        ]
    )
    def reject_lifecycle(self) -> None:
        """Make the contract immutable."""
        assert False, "Contract is immutable"

    @arc4.abimethod
    def opt_in_to_asset(self, asset: UInt64) -> None:
        """Opt the contract into an ASA.
        Must be called before the deposit group."""
        assert Txn.sender.bytes == self.admin.value, \
            "Only admin"
        itxn.AssetTransfer(
            xfer_asset=Asset(asset),
            asset_receiver=(
                Global.current_application_address
            ),
            asset_amount=0,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def initialize(
        self,
        asset: UInt64,
        beneficiary: arc4.Address,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        deposit_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        """Set up the vesting schedule and accept the
        token deposit in one atomic group."""
        assert Txn.sender.bytes == self.admin.value, \
            "Only admin"
        assert self.asset_id.value == UInt64(0), \
            "Already initialized"
        assert vesting_duration > cliff_duration, \
            "Vesting must exceed cliff"
        assert total_amount > UInt64(0), \
            "Amount must be positive"

        # Verify the grouped deposit
        assert deposit_txn.xfer_asset == Asset(asset)
        assert deposit_txn.asset_receiver \
            == Global.current_application_address
        assert deposit_txn.asset_amount == total_amount

        self.asset_id.value = asset
        self.beneficiary.value = beneficiary.bytes
        self.total_amount.value = total_amount
        now = Global.latest_timestamp
        self.start_time.value = now
        self.cliff_end.value = now + cliff_duration
        self.vesting_end.value = now + vesting_duration

    @arc4.abimethod
    def claim(self) -> UInt64:
        """Beneficiary claims vested tokens."""
        assert Txn.sender.bytes \
            == self.beneficiary.value, "Only beneficiary"

        now = Global.latest_timestamp
        if now < self.cliff_end.value:
            return UInt64(0)

        if now >= self.vesting_end.value:
            vested = self.total_amount.value
        else:
            elapsed = now - self.start_time.value
            duration = (
                self.vesting_end.value
                - self.start_time.value
            )
            vested = (
                self.total_amount.value
                * elapsed
                // duration
            )

        claimable = vested - self.claimed_amount.value
        if claimable == UInt64(0):
            return UInt64(0)

        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        self.claimed_amount.value = (
            self.claimed_amount.value + claimable
        )
        return claimable

    @arc4.abimethod(readonly=True)
    def get_claimable(self) -> UInt64:
        """How many tokens can the beneficiary
        claim right now?"""
        now = Global.latest_timestamp
        if now < self.cliff_end.value:
            return UInt64(0)

        if now >= self.vesting_end.value:
            vested = self.total_amount.value
        else:
            elapsed = now - self.start_time.value
            duration = (
                self.vesting_end.value
                - self.start_time.value
            )
            vested = (
                self.total_amount.value
                * elapsed
                // duration
            )

        return vested - self.claimed_amount.value

    @arc4.abimethod(readonly=True)
    def get_admin(self) -> arc4.Address:
        """Return the admin address."""
        return arc4.Address.from_bytes(
            self.admin.value
        )
```

Let us walk through the design decisions.

**Global state for everything.** The vesting parameters --- `total_amount`, `start_time`, `cliff_end`, `vesting_end`, `claimed_amount` --- are all global state fields. This limits us to a single beneficiary (one set of parameters), but it avoids the complexity of box storage, box references, and MBR management. That is 2 byte-slice slots (`admin` and `beneficiary`, stored as raw address bytes) and 6 uint slots --- well within the 64-slot limit.

**Separate opt-in, then initialize-and-deposit.** The contract needs to opt into the ASA before it can receive the deposit. On Algorand, an asset transfer to an account that has not opted in will fail. So we call `opt_in_to_asset` first, then send a grouped transaction: an asset transfer (the deposit) followed by the `initialize` app call. The contract verifies the deposit matches the declared amount and asset. This is simpler than Chapter 3's approach but less flexible --- you cannot add more tokens after initialization.

**No wide arithmetic.** The vesting calculation `total_amount * elapsed // duration` uses plain `UInt64` arithmetic. If `total_amount * elapsed` exceeds `UInt64` max (~1.8 x 10^19), the AVM panics. With small test amounts this is fine. With production amounts (100M tokens at 6 decimals = 10^14 base units times months of elapsed time), it overflows. We will test this gap explicitly.

**`claim` returns zero instead of asserting.** If nothing is claimable (before cliff, or everything already claimed), the method returns 0 rather than failing. This is a design choice --- the Chapter 3 version asserts because a zero-claim is likely a user error and should fail loudly. Here we return zero for simplicity.

**`fee=UInt64(0)` on every inner transaction.** This makes the fee pooling intent explicit --- the outer transaction overpays to cover inner fees. In PuyaPy, the default inner transaction fee is already 0, but writing it explicitly ensures anyone reading the code immediately sees the intent. If a non-zero fee were set (or if a lower-level language left the field defaulting to the minimum fee), that amount would be deducted from the contract's Algo balance. An attacker could then call your contract repeatedly, draining its balance through accumulated fees.

Save this contract as `smart_contracts/simple_vesting/contract.py`. If you are using a project from `algokit init`, rename the template's `hello_world/` directory to `simple_vesting/` first. Compile it:

```bash
algokit project run build
```

You should see `SimpleVesting.approval.teal`, `SimpleVesting.clear.teal`, and `SimpleVesting.arc56.json` in `smart_contracts/artifacts/simple_vesting/`.


## Setting Up pytest

The project template from `algokit init` includes pytest in its dependencies, but you need a `tests/` directory with proper fixtures. Create `tests/conftest.py` in your project root (next to `pyproject.toml`):

```python
# tests/conftest.py
import os
import time
import pytest
import algokit_utils


@pytest.fixture(scope="session")
def algorand() -> algokit_utils.AlgorandClient:
    """AlgorandClient connected to LocalNet.
    Session-scoped: one client for all tests."""
    return (
        algokit_utils.AlgorandClient.default_localnet()
    )


@pytest.fixture(scope="session")
def admin(algorand: algokit_utils.AlgorandClient):
    """The LocalNet dispenser account. Pre-funded
    with millions of Algo."""
    return algorand.account.localnet_dispenser()


def fund_account(
    algorand: algokit_utils.AlgorandClient,
    sender,
    receiver_address: str,
    amount: int = 500_000,
) -> None:
    """Send Algo to an account so it meets MBR."""
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=sender.address,
            receiver=receiver_address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(amount)
            ),
            note=os.urandom(8),
        )
    )


def create_test_asa(
    algorand: algokit_utils.AlgorandClient,
    creator,
    total: int = 10_000_000_000,
    decimals: int = 6,
) -> int:
    """Create a test ASA and return its ID."""
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=creator.address,
            total=total,
            decimals=decimals,
            default_frozen=False,
            asset_name="TestToken",
            unit_name="TST",
            note=os.urandom(8),
        )
    )
    return result.asset_id


def advance_time(
    algorand: algokit_utils.AlgorandClient,
    seconds: int,
) -> None:
    """Advance the LocalNet block timestamp.

    On LocalNet, blocks are produced on demand --- only
    when a transaction is submitted. time.sleep() alone
    does NOT advance the block timestamp. This helper
    sleeps for the requested duration (so the system
    clock advances), then sends a dummy self-payment
    (so a new block is produced with the updated
    timestamp).
    """
    time.sleep(seconds)
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=dispenser.address,
            receiver=dispenser.address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(0)
            ),
            note=os.urandom(8),
        )
    )
```

Also create an empty `tests/__init__.py` so pytest treats the directory as a package.

There are several important things to understand about this setup.

**`localnet_dispenser()` vs `account.random()`.** The dispenser is a pre-funded account that comes with LocalNet --- it has millions of Algo and can pay for anything. `account.random()` creates a brand-new account with zero balance. Every random account needs explicit funding before it can do anything (even a simple payment requires 0.1 Algo MBR plus fee headroom). Use the dispenser as your admin/deployer and `account.random()` for beneficiaries and other secondary accounts.

**`note=os.urandom(8)` on every transaction.** LocalNet produces blocks on demand, and identical transactions submitted in rapid succession can produce identical transaction IDs, causing "transaction already in ledger" errors. Adding 8 random bytes to the note field guarantees uniqueness. This costs nothing and prevents intermittent test failures that are maddening to debug. Add it to every `PaymentParams`, `AssetTransferParams`, `AssetCreateParams`, and `AppClientMethodCallParams` in your test code.

*Here is a puzzle: if you call `time.sleep(10)` in your test and then check the block timestamp, it has not changed. Why?*

> **Note:** The `advance_time` helper is the single most confusing aspect of LocalNet testing for newcomers. On a live network, block timestamps advance with wall-clock time because blocks are produced continuously. On LocalNet, blocks are only produced when you submit a transaction. If you `time.sleep(10)` but do not submit a transaction, the block timestamp stays where it was. You need both the sleep (to advance wall-clock time) and the dummy transaction (to produce a block reflecting that time).

**Session-scoped fixtures.** The `algorand` and `admin` fixtures use `scope="session"` so they are created once and reused across all tests. Each test deploys its own fresh contract instance, so tests do not interfere with each other despite sharing the same LocalNet connection.

> **Note:** For testing, use short durations --- seconds instead of months. Set a cliff of 5 seconds and total vesting of 20 seconds instead of 90 days and 365 days. This keeps your test suite fast while still exercising the time-dependent logic faithfully.


## Writing Tests That Pass

Create `tests/test_simple_vesting.py`. Every test follows the same rhythm: **deploy** the contract, **set up** the required state, **act** (call the method under test), and **assert** on the result.

We start with two helper functions that eliminate repetition:

```python
# tests/test_simple_vesting.py
import os
from pathlib import Path
import pytest
import algokit_utils

from tests.conftest import (
    advance_time,
    create_test_asa,
    fund_account,
)

APP_SPEC = Path(
    "smart_contracts/artifacts/simple_vesting/"
    "SimpleVesting.arc56.json"
).read_text()


def deploy(algorand, admin):
    """Deploy a fresh SimpleVesting contract."""
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC,
        default_sender=admin.address,
    )
    app_client, _ = factory.deploy()
    return app_client


def setup_initialized_contract(
    algorand, admin, cliff, vesting, total
):
    """Deploy, fund, initialize, and return
    (app_client, token_id, beneficiary)."""

    # Step 1: Deploy a fresh contract
    app_client = deploy(algorand, admin)

    # Step 2: Create a test ASA with enough supply
    token_id = create_test_asa(
        algorand, admin, total=max(total, 10_000_000_000)
    )

    # Step 3: Create and fund beneficiary account
    beneficiary = algorand.account.random()
    fund_account(algorand, admin, beneficiary.address)

    # Step 4: Beneficiary opts into the ASA
    # (required before they can receive tokens)
    algorand.send.asset_transfer(
        algokit_utils.AssetTransferParams(
            sender=beneficiary.address,
            receiver=beneficiary.address,
            asset_id=token_id,
            amount=0,
            note=os.urandom(8),
        )
    )

    # Step 5: Fund the contract for MBR.
    # 300,000 microAlgo covers base MBR (100,000)
    # plus ASA opt-in (100,000), with headroom for
    # inner transaction fees. See Chapter 1 for
    # MBR details.
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=admin.address,
            receiver=app_client.app_address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(300_000)
            ),
            note=os.urandom(8),
        )
    )

    # Step 6: Contract opts into the ASA
    # (must happen BEFORE the deposit transfer)
    app_client.send.call(
        algokit_utils.AppClientMethodCallParams(
            method="opt_in_to_asset",
            args=[token_id],
            static_fee=(
                algokit_utils.AlgoAmount
                .from_micro_algo(2000)
            ),
            note=os.urandom(8),
        )
    )

    # Step 7: Group the deposit + initialize call
    composer = algorand.new_group()
    composer.add_asset_transfer(
        algokit_utils.AssetTransferParams(
            sender=admin.address,
            receiver=app_client.app_address,
            asset_id=token_id,
            amount=total,
            note=os.urandom(8),
        )
    )
    composer.add_app_call_method_call(
        app_client.params.call(
            algokit_utils.AppClientMethodCallParams(
                method="initialize",
                args=[
                    token_id,
                    beneficiary.address,
                    total,
                    cliff,
                    vesting,
                ],
                note=os.urandom(8),
            )
        )
    )
    composer.send()

    return app_client, token_id, beneficiary
```

The `setup_initialized_contract` helper follows a 7-step sequence. Each step has a specific purpose:

1. **Deploy** creates a fresh contract instance (so tests do not interfere).
2. **Create ASA** makes a test token with sufficient supply.
3. **Fund beneficiary** gives the new account enough Algo for MBR and fees.
4. **Beneficiary opts into ASA** --- required before they can receive tokens via `claim`.
5. **Fund contract** covers the contract's MBR (base account + ASA opt-in).
6. **Contract opts into ASA** --- must happen *before* the deposit. On Algorand, an asset transfer to an account that has not opted in fails immediately.
7. **Grouped deposit + initialize** sends the tokens and configures the vesting schedule atomically.

*Before reading the following tests, pause and list three behaviors you would want to test in this contract. What is the most important security check?*

Each test targets one specific behavior. We test time-dependent logic with invariants (greater than zero, less than total) rather than exact values because LocalNet timestamps are precise only to the second. We write separate tests for each security assertion so a failure tells us exactly which check broke. Now the seven tests --- each one tells a story.

```python
class TestSimpleVesting:

    def test_create_sets_admin(
        self, algorand, admin
    ):
        """Deployer should be recorded as admin."""
        app_client = deploy(algorand, admin)
        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="get_admin",
                note=os.urandom(8),
            )
        )
        assert result.abi_return == admin.address
```

*Before reading the next test, try predicting what `test_initialize_opts_into_asset` needs to do. What setup steps are required before you can verify that the contract holds tokens?*

```python
    def test_initialize_opts_into_asset(
        self, algorand, admin
    ):
        """After initialize, the contract should hold
        the deposited tokens."""
        total = 1_000_000
        app_client, token_id, _ = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=total,
            )
        )

        # Verify via algod API
        info = algorand.client.algod.account_asset_info(
            app_client.app_address, token_id
        )
        balance = info["asset-holding"]["amount"]
        assert balance == total

    def test_claim_before_cliff_returns_zero(
        self, algorand, admin
    ):
        """Claiming before the cliff should return 0
        and transfer nothing."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=8, vesting=30, total=1_000_000,
            )
        )

        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        assert result.abi_return == 0

    def test_claim_after_cliff_returns_proportional(
        self, algorand, admin
    ):
        """After the cliff, vested tokens should be
        claimable proportionally."""
        total = 1_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=total,
            )
        )

        advance_time(algorand, 7)  # Past 5s cliff

        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        claimed = result.abi_return
        assert claimed > 0
        assert claimed < total

        # Verify on-chain balance
        info = algorand.client.algod.account_asset_info(
            beneficiary.address, token_id
        )
        assert info["asset-holding"]["amount"] == claimed

    def test_claim_after_full_vesting_returns_total(
        self, algorand, admin
    ):
        """After vesting_end, all tokens are claimable."""
        total = 1_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=10, total=total,
            )
        )

        advance_time(algorand, 12)  # Past vesting_end

        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        assert result.abi_return == total
```

The first five tests verified correct behavior --- the contract does what it should. The next two verify security --- the contract rejects what it should reject.

```python
    def test_only_admin_can_initialize(
        self, algorand, admin
    ):
        """A non-admin caller should be rejected."""
        app_client = deploy(algorand, admin)
        token_id = create_test_asa(algorand, admin)
        imposter = algorand.account.random()
        fund_account(
            algorand, admin, imposter.address
        )

        # Imposter opts into the ASA so they can
        # hold tokens for the deposit
        algorand.send.asset_transfer(
            algokit_utils.AssetTransferParams(
                sender=imposter.address,
                receiver=imposter.address,
                asset_id=token_id,
                amount=0,
                note=os.urandom(8),
            )
        )
        # Transfer tokens to imposter so they can
        # deposit
        algorand.send.asset_transfer(
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=imposter.address,
                asset_id=token_id,
                amount=1_000_000,
                note=os.urandom(8),
            )
        )

        # Fund the contract for MBR
        # (base + ASA opt-in)
        algorand.send.payment(
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=app_client.app_address,
                amount=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(300_000)
                ),
                note=os.urandom(8),
            )
        )

        # Admin opts the contract into the ASA so
        # the deposit transfer does not fail before
        # the initialize app call
        app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="opt_in_to_asset",
                args=[token_id],
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )

        with pytest.raises(Exception):
            composer = algorand.new_group()
            composer.add_asset_transfer(
                algokit_utils.AssetTransferParams(
                    sender=imposter.address,
                    receiver=app_client.app_address,
                    asset_id=token_id,
                    amount=1_000_000,
                    note=os.urandom(8),
                )
            )
            composer.add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="initialize",
                        args=[
                            token_id,
                            imposter.address,
                            1_000_000, 5, 20,
                        ],
                        sender=imposter.address,
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            composer.send()

    def test_only_beneficiary_can_claim(
        self, algorand, admin
    ):
        """A non-beneficiary should be rejected."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=15, total=1_000_000,
            )
        )

        advance_time(algorand, 5)

        attacker = algorand.account.random()
        fund_account(
            algorand, admin, attacker.address
        )

        with pytest.raises(Exception):
            app_client.send.call(
                algokit_utils
                .AppClientMethodCallParams(
                    method="claim",
                    sender=attacker.address,
                    static_fee=(
                        algokit_utils.AlgoAmount
                        .from_micro_algo(2000)
                    ),
                    note=os.urandom(8),
                )
            )
```

Run the tests:

```bash
pytest tests/test_simple_vesting.py -v
```

You should see all seven pass. The total runtime will be 30--50 seconds, dominated by the `advance_time` calls. If any test fails, check these common issues: LocalNet not running (`algokit localnet start`), contract not compiled (`algokit project run build`), or the ARC-56 spec path not matching your directory layout.

*Self-check: can you trace each test back to a specific contract method and explain what behavior it validates? If a test fails, can you predict which `assert` in the contract was triggered?*


## Using Simulate for Negative Tests

The preceding tests use `pytest.raises(Exception)` to verify that unauthorized calls fail. This works, but it is a blunt instrument --- you know the call failed, but not *why*. Maybe it failed for the wrong reason (insufficient funds, a missing ASA opt-in, a different assertion). You want to verify that the *specific security check* caught the attack.

Algorand's *simulate* endpoint solves this. Simulate executes the full transaction logic --- including all contract assertions --- without committing state changes or charging fees. The response includes the failure reason if the transaction would have been rejected. This lets you construct an attack, simulate it, and verify the *exact* assertion that stopped it.

```python
    def test_simulate_unauthorized_claim(
        self, algorand, admin
    ):
        """Use simulate to verify the specific
        rejection reason for unauthorized claims."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=15, total=1_000_000,
            )
        )
        advance_time(algorand, 5)

        attacker = algorand.account.random()
        fund_account(
            algorand, admin, attacker.address
        )

        # Build the attack, simulate instead of sending
        result = (
            algorand.new_group()
            .add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="claim",
                        sender=attacker.address,
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            .simulate()
        )

        # The simulate response tells us WHY it failed
        txn_result = (
            result.simulate_response[
                "txn-groups"
            ][0]
        )
        assert "failure-message" in txn_result
        assert "Only beneficiary" in (
            txn_result["failure-message"]
        )
```

The key difference is `.simulate()` instead of `.send()`. The transaction is constructed identically --- same method, same arguments, same sender --- but simulate executes it in a sandbox. The `simulate_response` dictionary contains detailed information about what happened, including the exact failure message from the contract's `assert` statement.

This is far more precise than `pytest.raises(Exception)`. You are not just testing that the call fails --- you are testing that it fails *because of the authorization check*, not because of insufficient funds, a missing box reference, or some other unrelated error.

> **Tip:** For every security assertion in your contract, write a test that constructs the specific attack and simulates it. Verify the failure message matches the assertion you intended. This builds a library of negative tests that proves each security check works for the right reason.

Here is the same pattern applied to the admin-only `initialize` check:

```python
    def test_simulate_non_admin_initialize(
        self, algorand, admin
    ):
        """Verify initialize rejects non-admin callers
        with the correct error message."""
        app_client = deploy(algorand, admin)
        token_id = create_test_asa(algorand, admin)
        imposter = algorand.account.random()
        fund_account(
            algorand, admin, imposter.address
        )

        # Fund contract for MBR (base + ASA opt-in)
        algorand.send.payment(
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=app_client.app_address,
                amount=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(300_000)
                ),
                note=os.urandom(8),
            )
        )

        # Admin opts the contract into the ASA so
        # the deposit transfer does not fail before
        # the initialize app call
        app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="opt_in_to_asset",
                args=[token_id],
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )

        result = (
            algorand.new_group()
            .add_asset_transfer(
                algokit_utils.AssetTransferParams(
                    sender=admin.address,
                    receiver=app_client.app_address,
                    asset_id=token_id,
                    amount=1_000_000,
                    note=os.urandom(8),
                )
            )
            .add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="initialize",
                        args=[
                            token_id,
                            imposter.address,
                            1_000_000, 5, 20,
                        ],
                        sender=imposter.address,
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            .simulate()
        )

        txn_result = (
            result.simulate_response[
                "txn-groups"
            ][0]
        )
        assert "Only admin" in (
            txn_result["failure-message"]
        )
```

The simulate approach is especially valuable during development. When a test fails unexpectedly, simulating the same transaction gives you the exact failure reason and program counter, which you can map back to your source code using the ARC-56 source map.


## Tests That Fail --- Revealing the Gaps

The preceding tests prove the simplified contract works correctly within its design scope. But that scope is deliberately narrow. The following tests expose limitations that would matter in production --- and each one motivates a specific feature in Chapter 3's full implementation.

### Gap 1: Arithmetic Overflow with Large Amounts

The simplified contract computes `total_amount * elapsed // duration` using plain `UInt64` arithmetic. What happens with production-scale amounts?

```python
class TestSimpleVestingGaps:

    def test_overflow_with_production_amounts(
        self, algorand, admin
    ):
        """100M tokens at 6 decimals produces an
        intermediate product that overflows UInt64 when
        combined with production-length time durations.

        With short test durations, the math works.
        With real durations (months), it would overflow.
        This test documents the vulnerability."""
        # 10^14 base units (100M tokens, 6 decimals)
        total = 100_000_000_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=20, total=total,
            )
        )

        # With 20-second vesting, 10^14 * 10 = 10^15
        # fits in UInt64. This claim succeeds.
        advance_time(algorand, 10)
        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        assert result.abi_return > 0

        # But if vesting_duration were 31,536,000
        # (one year in seconds), the product
        # 10^14 * 31,536,000 = 3.15 * 10^21 would
        # exceed UInt64 max of ~1.8 * 10^19.
        # The AVM would panic with an overflow error.
```

The comment explains what *would* happen with production parameters. We cannot easily test the overflow with integration tests (we would need to sleep for a year), but we can document it as a known limitation.

*Chapter 3 solves this with wide arithmetic: `op.mulw(total, elapsed)` produces a 128-bit intermediate product as two `UInt64` values, and `op.divmodw` divides it back to `UInt64`. The intermediate product never overflows.*

### Gap 2: Only One Beneficiary

```python
    def test_cannot_add_second_beneficiary(
        self, algorand, admin
    ):
        """The contract supports exactly one
        beneficiary. Calling initialize again fails
        because asset_id is already set."""
        app_client, token_id, first_ben = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=500_000,
            )
        )

        second_ben = algorand.account.random()
        fund_account(
            algorand, admin, second_ben.address
        )

        # Attempt to initialize again
        with pytest.raises(Exception):
            composer = algorand.new_group()
            composer.add_asset_transfer(
                algokit_utils.AssetTransferParams(
                    sender=admin.address,
                    receiver=app_client.app_address,
                    asset_id=token_id,
                    amount=500_000,
                    note=os.urandom(8),
                )
            )
            composer.add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="initialize",
                        args=[
                            token_id,
                            second_ben.address,
                            500_000, 5, 20,
                        ],
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            composer.send()
```

The "Already initialized" assertion fires because `self.asset_id.value` is no longer zero. A real vesting contract serving a startup team needs to support dozens or hundreds of beneficiaries, each with independent schedules.

*Chapter 3 introduces `BoxMap(Account, VestingSchedule, key_prefix=b"v_")` for per-beneficiary storage. Each schedule gets its own box, independently created and deleted. The `initialize` method sets up the contract and token; a separate `create_schedule` method adds individual beneficiaries.*

### Gap 3: No Revocation

```python
    def test_no_revocation_mechanism(
        self, algorand, admin
    ):
        """There is no way for the admin to reclaim
        unvested tokens if a team member leaves."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=1_000_000,
            )
        )

        advance_time(algorand, 10)

        # The contract has no revoke method. The only
        # methods are initialize, claim, get_claimable,
        # and get_admin. Once tokens are deposited,
        # only the beneficiary can claim them.
        # Admin tries to claim (fails: admin != beneficiary)
        result = (
            algorand.new_group()
            .add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="claim",
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            .simulate()
        )
        # Admin can call claim, but the contract
        # rejects because admin != beneficiary
        txn_result = (
            result.simulate_response[
                "txn-groups"
            ][0]
        )
        assert "Only beneficiary" in (
            txn_result["failure-message"]
        )
```

Even the admin cannot retrieve unvested tokens. Once deposited, tokens are fully committed to the beneficiary's vesting schedule, regardless of whether they leave the team on day two.

*Chapter 3 adds a `revoke` method: it calculates how many tokens are vested at revocation time, caps the beneficiary's `total_amount` at the vested amount, and returns the unvested remainder to the admin via an inner transaction.*

### Gap 4: Rounding Behavior Across Multiple Claims

```python
    def test_multiple_claims_sum_to_total(
        self, algorand, admin
    ):
        """Intermediate claims use floor division.
        Do they sum to exactly the total?"""
        total = 1_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=2, vesting=8, total=total,
            )
        )

        # First claim mid-vesting
        advance_time(algorand, 4)
        r1 = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        first = r1.abi_return

        # Second claim after full vesting
        advance_time(algorand, 6)
        r2 = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        second = r2.abi_return

        # Should sum to exactly total
        assert first + second == total
```

This test should pass because the final claim uses the `now >= vesting_end` branch, which bypasses division entirely and returns the full remaining amount (`total - claimed`). Floor division during intermediate claims means the beneficiary gets slightly less than their exact entitlement, and the final claim resolves the dust. This is correct behavior --- but it only works because the simplified contract's arithmetic does not overflow. With production-scale amounts, the overflow from Gap 1 would make the rounding behavior moot --- the program panics before it can round at all.

*Chapter 3 extracts the vesting math into a `calculate_vested` subroutine using `op.mulw`/`op.divmodw`. Floor division consistently favors the contract: the beneficiary never receives more than their total allocation, and the dust resolves on the final claim when the full `total - claimed` remainder is released.*

These four gaps --- overflow, single-beneficiary limitation, missing revocation, and overflow-dependent rounding --- form the specification for Chapter 3. You now know exactly *what* the production contract must solve and *why*. When Chapter 3 introduces `BoxMap` or `op.mulw`, you will understand the motivation instead of taking it on faith.


## Unit Testing with algorand-python-testing

You have now written a complete integration test suite. The remainder of this chapter introduces a faster, lighter alternative for testing business logic during development.

Every test so far is an *integration test*: it deploys a real contract to LocalNet, submits real transactions, and verifies real on-chain state. Integration tests are the gold standard for smart contracts because they test the actual compiled TEAL, the ABI encoding, the opcode budget, and the network interaction. But they are slow --- the `advance_time` sleeps alone add up to 30+ seconds per run.

The `algorand-python-testing` library provides a complementary approach: *unit testing* that executes your PuyaPy contract as a regular Python object, without compilation or deployment. You instantiate the contract class, set state directly, and call methods --- all in milliseconds.

Install the testing library if it is not already in your dependencies:

```bash
pip install algorand-python-testing
```

Then place a copy of your contract in `tests/contracts/simple_vesting.py` (create `tests/contracts/__init__.py` as well so Python treats the directory as a package) and import from there:

```python
# tests/test_simple_vesting_unit.py
import pytest
from algopy_testing import algopy_testing_context
from algopy import UInt64, OnCompleteAction

from tests.contracts.simple_vesting import (
    SimpleVesting,
)


class TestVestingMath:
    """Unit tests for the vesting calculation logic."""

    def test_before_cliff_returns_zero(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(100)
            contract.cliff_end.value = UInt64(200)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=150
            )
            result = contract.get_claimable()
            assert result == 0

    def test_midway_vesting(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(0)
            contract.cliff_end.value = UInt64(0)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=500
            )
            result = contract.get_claimable()
            # 1_000_000 * 500 / 1000 = 500_000
            assert result == 500_000

    def test_after_end_returns_total(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(100)
            contract.cliff_end.value = UInt64(200)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=2000
            )
            result = contract.get_claimable()
            assert result == 1_000_000

    def test_floor_division_rounds_down(self):
        """Integer division should favor the contract
        (beneficiary gets slightly less)."""
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(0)
            contract.cliff_end.value = UInt64(0)
            contract.vesting_end.value = UInt64(3)

            ctx.ledger.patch_global_fields(
                latest_timestamp=1
            )
            result = contract.get_claimable()
            # 1_000_000 / 3 = 333_333.33... -> 333_333
            assert result == 333_333

    def test_immutability_rejects_update(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction
                        .UpdateApplication
                    )
                }
            ):
                with pytest.raises(
                    AssertionError,
                    match="immutable",
                ):
                    contract.reject_lifecycle()
```

Notice the key differences from integration tests:

- **No deployment.** `SimpleVesting()` is a regular Python object.
- **No transactions.** State is set by assigning directly to `GlobalState` properties.
- **No sleeps.** Timestamps are set instantly via `ctx.ledger.patch_global_fields(latest_timestamp=...)`.
- **No network.** No LocalNet, no algod, no Docker.
- **Milliseconds per test** instead of seconds.

The `algopy_testing_context()` context manager provides a mock AVM environment. `ctx.txn.create_group()` sets up the transaction context needed for methods that read `Txn.sender` or check `OnCompletion`. `ctx.ledger.patch_global_fields()` controls `Global.latest_timestamp`, `Global.round`, and other protocol-level values.

**When to use each approach:**

| Aspect | Integration Tests | Unit Tests |
|--------|---|---|
| **Speed** | Slow (seconds) | Fast (milliseconds) |
| **Fidelity** | Tests compiled TEAL on real AVM | Tests Python source |
| **What it tests** | Contract logic + client code + ABI encoding | Contract logic only |
| **Catches** | Opcode budget, ABI encoding, real network behavior | Business logic bugs, math errors |
| **When a test fails** | Bug could be in the contract OR the client code | Bug is in the contract logic |
| **Requires** | LocalNet + Docker | None |
| **Best for** | Final validation, security | Rapid logic iteration |

In practice, start with unit tests for math and business logic --- the parts where a wrong number means lost funds --- then write integration tests for the full lifecycle: deploy, initialize, interact, and verify on-chain state. When a unit test passes but an integration test fails, the bug is in ABI encoding, opcode budget, or a deployment detail that only surfaces on-chain.

> **Note:** In production applications, you will also have client-side code that deserves its own tests --- SDK wrappers, frontend transaction composers, error handling, retry logic. That is standard Python (or TypeScript) testing with no blockchain-specific tooling. This chapter covers the blockchain-specific skill: testing the smart contract itself.


## Test Organization

As your project grows to multiple contracts, a consistent structure keeps things manageable:

```text
tests/
    __init__.py
    conftest.py                  # Shared fixtures
    contracts/                   # Contract copies for unit tests
        __init__.py
        simple_vesting.py
    test_simple_vesting.py       # Integration tests
    test_simple_vesting_unit.py  # Unit tests
```

**One test file per contract.** `test_simple_vesting.py`, `test_vesting.py`, `test_amm.py`, `test_farming.py`. Run tests for a single contract with `pytest tests/test_simple_vesting.py -v`.

**Group related tests in classes.** `TestSimpleVesting` for the happy path, `TestSimpleVestingGaps` for the limitation tests. This is organizational --- pytest discovers methods in classes the same way it discovers standalone functions.

**Name tests descriptively.** Follow the pattern `test_<feature>_<expected_behavior>`. Names like `test_claim_before_cliff_returns_zero` and `test_only_admin_can_initialize` make test output readable without inspecting the code.

**Fixtures for setup, helpers for operations.** Fixtures (`@pytest.fixture`) manage session-scoped resources like the `algorand` client and `admin` account. Helper functions (`deploy`, `setup_initialized_contract`, `create_test_asa`) are regular functions you call with different parameters in different tests.

**Every security assertion gets a negative test.** If your contract has `assert Txn.sender.bytes == self.admin.value`, write a test where a non-admin calls that method. If it has `assert total_amount > UInt64(0)`, write a test that passes zero. One negative test per assertion. This is the single most effective practice for preventing security bugs.

> **Note:** The `conftest.py` fixtures and helper functions from this chapter are reused throughout the book. When you reach Chapter 3, you will add contract-specific helpers (`create_schedule`, `deposit_tokens`) but the foundational `fund_account`, `create_test_asa`, and `advance_time` helpers remain unchanged.


## Summary

In this chapter you learned to:

- Write integration tests that deploy a contract to LocalNet, submit real transactions, and verify on-chain state
- Use `advance_time` (sleep + dummy transaction) to test time-dependent contract logic on LocalNet
- Write negative tests using `pytest.raises` and verify exact rejection reasons with the simulate endpoint
- Write unit tests with `algorand-python-testing` for rapid iteration on business logic
- Distinguish integration tests from unit tests and choose which to write first
- Structure a test suite with fixtures, helpers, and descriptive naming conventions
- Write tests that deliberately fail to expose a simplified contract's limitations and define a production specification

| Concept | Key Takeaway |
|---------|-------------|
| Integration tests | Deploy to LocalNet, submit real transactions, verify on-chain state. High fidelity but slow. |
| Unit tests | Instantiate contracts as Python objects, mock state, no network. Fast but does not test compiled TEAL. |
| `advance_time` | Sleep + dummy transaction to advance LocalNet block timestamp. Neither alone is sufficient. |
| Transaction dedup | `note=os.urandom(8)` on every test transaction prevents "already in ledger" errors. |
| `localnet_dispenser()` | Pre-funded account for admin/deployer. `account.random()` starts with zero balance. |
| Simulate | Execute transactions without committing. Returns failure reasons for precise negative tests. |
| Negative tests | For every `assert` in the contract, write a test that triggers the failure path. |
| Failing tests as specs | Tests exposing simplified contract limitations define what the production version must solve. |


## Exercises

1. **(Recall)** Explain why `time.sleep(10)` alone does not advance the LocalNet block timestamp. What additional step is required, and why?

2. **(Understand)** The simplified contract uses `fee=UInt64(0)` on every inner transaction. Explain what would happen if a non-zero fee were set and how an attacker could exploit it.

3. **(Apply)** Write a `@pytest.fixture` named `deployed_contract` that deploys the SimpleVesting contract, initializes it with a test ASA and beneficiary, and returns a tuple of `(app_client, token_id, beneficiary)`. Use it to simplify at least two of the existing tests.

4. **(Apply)** Write a test that verifies the contract rejects `DeleteApplication`. Use the simulate endpoint and check that the failure message contains "immutable."

5. **(Analyze)** The simplified contract does not check `Global.group_size` in the `initialize` method. Write a test that submits an `initialize` call with an extra payment transaction appended to the group. Does the contract reject it? If not, explain what an attacker could do with the extra transaction, and add a group size check to the contract.

6. **(Evaluate)** Review the four gaps identified in "Tests That Fail." Classify each as a **security issue** (could lead to loss of funds) or a **feature gap** (limits functionality but does not create a vulnerability). Justify each classification.

7. **(Create)** Add a `revoke` method to the simplified contract that lets the admin reclaim unvested tokens. Write both a positive test (admin revokes mid-vesting, receives unvested tokens) and a negative test via simulate (non-admin cannot revoke, failure message is "Only admin"). Hint: the method needs an inner `AssetTransfer` to send tokens back to the admin, and it should update `total_amount` to cap at the vested amount.


## Further Reading

- [AlgoKit Testing Patterns](https://dev.algorand.co/algokit/utils/python/testing/) --- Testing smart contracts with AlgoKit Utils
- [algorand-python-testing](https://dev.algorand.co/algokit/unit-testing/python/overview) --- Unit testing library for PuyaPy contracts
- [pytest documentation](https://docs.pytest.org/) --- Fixtures, parametrize, markers, and configuration
- [Simulate endpoint](https://dev.algorand.co/reference/rest-api/algod/) --- algod REST API reference including simulate
- [AlgoKit Utils Python](https://dev.algorand.co/algokit/utils/python/overview/) --- Client library used in all test scripts


## Before You Continue

Before starting Chapter 3, you should be able to:

- [ ] Write a pytest test that deploys a contract to LocalNet and calls a method
- [ ] Use `advance_time` to test time-dependent contract logic
- [ ] Write a negative test using `simulate` that verifies a specific security assertion
- [ ] Explain the difference between integration tests and unit tests for smart contracts
- [ ] Identify the four limitations of the simplified vesting contract that Chapter 3 addresses

If any of these are unclear, revisit the relevant section before proceeding. Chapter 3 assumes you are comfortable writing and running tests --- every feature we build there will be tested using the patterns established here.
