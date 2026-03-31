\newpage


# NFTs --- Extending the Vesting Contract with Transferability

You have a working token vesting contract. It creates schedules, tracks claims, handles revocation, and manages MBR lifecycle. But it has a limitation you may have already noticed: vesting schedules are permanently bound to the beneficiary's address. If a team member wants to sell their future token allocation, transfer it to a different wallet, or use it as collateral in a lending protocol, they cannot. The schedule is locked to whoever the admin specified at creation time.

In this chapter we solve that by minting an *NFT* (Non-Fungible Token) for each vesting schedule. Whoever holds the NFT can claim the vested tokens --- and transferring the NFT is just a standard asset transfer that works with any Algorand wallet or marketplace. This single architectural change makes vesting positions composable: they can be traded, used as collateral, or transferred between wallets, all without modifying the contract.

We will rebuild the vesting contract from Chapter 3 with these changes. Along the way, you will learn how NFTs work on Algorand (they are just ASAs with `total=1`), how to mint assets from within a contract via inner transactions, the ARC-3 metadata standard, the ownership-by-asset verification pattern, and the clawback mechanism for revocation. Every concept from Chapter 3 carries forward --- this chapter extends your knowledge rather than replacing it.

## What Is an NFT on Algorand?

On some blockchains, NFTs require a dedicated token standard with special smart contract logic (ERC-721 on Ethereum, for example). On Algorand, NFTs are simply [Algorand Standard Assets](https://dev.algorand.co/concepts/assets/overview/) (ASAs) with specific parameters:

- **total = 1** --- exactly one unit exists
- **decimals = 0** --- the unit is indivisible

That is it. There is no separate NFT contract, no special opcode, no distinct token type. The same `AssetTransfer` transaction that moves fungible tokens also moves NFTs. The same opt-in mechanism applies. The same `AssetConfig` transaction creates them. The entire Algorand NFT ecosystem --- marketplaces, wallets, explorers --- is built on this convention.

This means everything you learned about ASAs in Chapter 3 (opt-in, transfers, inner transactions) applies directly to NFTs. The only new concept is *metadata* --- how an NFT communicates what it represents.

## ARC-3: The NFT Metadata Standard

When you create an ASA, the on-chain fields are limited: a name (max 32 bytes), a unit name (max 8 bytes), a URL (max 96 bytes), and a 32-byte metadata hash. These fields alone cannot describe a vesting schedule's terms, display an image in a wallet, or provide the structured data that marketplaces need.

[ARC-3](https://dev.algorand.co/arc-standards/arc-0003/) solves this by defining a convention: the ASA's `url` field points to a JSON metadata file (typically hosted on IPFS), and the `metadata_hash` field contains the SHA-256 hash of that JSON for integrity verification. The URL must end with `#arc3` to signal that the asset follows this standard.

An ARC-3 metadata file for a vesting NFT might look like:

```json
{
  "name": "Vesting Schedule #1",
  "description": "1,000,000 TVT vesting over 12 months with 3-month cliff",
  "properties": {
    "total_amount": 1000000,
    "cliff_months": 3,
    "vesting_months": 12,
    "vesting_asset_id": 12345,
    "contract_app_id": 67890
  }
}
```

The `properties` object is freeform --- you can put any domain-specific attributes there. Wallets and explorers that support ARC-3 will display the name and description; specialized UIs can read the properties to show vesting details.

For our contract, the admin prepares the metadata JSON and uploads it to IPFS *before* calling `create_schedule`. The resulting IPFS URL and metadata hash are passed as arguments, and the contract embeds them in the minted NFT. This keeps the contract simple --- it does not need to construct JSON or interact with IPFS.

> **Note:** An alternative standard, *ARC-19*, allows mutable metadata by encoding an IPFS content identifier in the ASA's reserve address. This is useful when metadata changes over time (e.g., updating a "percent vested" field). For this chapter, ARC-3's immutable approach is sufficient --- the vesting terms are fixed at creation.

## Project Setup

We will build the NFT vesting contract as a fresh project, reusing the structure from Chapter 3. If you still have your `token-vesting` project, you can duplicate it. Otherwise, scaffold a new one:

```bash
algokit init -t python --name nft-vesting
cd nft-vesting/projects/nft-vesting
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/nft_vesting
```

Delete the template-generated `deploy_config.py` inside the renamed directory. Your contract code goes in `smart_contracts/nft_vesting/contract.py`.

## The Modified Data Model

In Chapter 3, vesting schedules were stored in a `BoxMap` keyed by the beneficiary's address. When the beneficiary called `claim`, the contract looked up `self.schedules[Txn.sender]`. This coupling between identity and ownership is what we are breaking.

The new design keys schedules by *NFT asset ID*. When a user calls `claim`, they pass the NFT's asset ID as an argument, and the contract verifies they hold the NFT before releasing tokens. The schedule does not care *who* holds the NFT --- only *that* the caller holds it.

Add the following to `smart_contracts/nft_vesting/contract.py`:

```python
from algopy import arc4

class VestingSchedule(arc4.Struct):
    total_amount: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_end: arc4.UInt64
    vesting_end: arc4.UInt64
    is_revoked: arc4.Bool
```

The struct is unchanged from Chapter 3 --- 41 bytes. We do not need to store the NFT asset ID inside the struct because it *is* the box key. We also do not store a beneficiary address because ownership is determined by who holds the NFT, not by a stored address.

The key difference is in the `BoxMap` declaration. (See [Algorand Python storage guide](https://dev.algorand.co/algokit/languages/python/lg-storage/) for BoxMap type parameters.) Add the contract class below the struct:

```python
from algopy import (
    ARC4Contract, Account, Asset, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, itxn, op, subroutine, BoxMap,
)

class NftVesting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.asset_id = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.schedule_count = GlobalState(UInt64(0))
        # Schedules keyed by NFT asset ID (8 bytes) instead of address (32 bytes)
        self.schedules = BoxMap(arc4.UInt64, VestingSchedule, key_prefix=b"v_")
```

Compare with Chapter 3's `BoxMap(Account, VestingSchedule, key_prefix=b"v_")`. The key type changed from `Account` (32 bytes) to `arc4.UInt64` (8 bytes). This means box names are shorter: `b"v_"` prefix (2 bytes) + 8-byte key = 10 bytes total, compared to 34 bytes previously. The MBR per box drops accordingly: 2,500 + 400 × (10 + 41) = **22,900 microAlgos** per schedule box (down from 32,500).

However, each schedule now also requires an NFT, and creating an ASA from the contract adds **100,000 microAlgos** to the contract's MBR. So the total per-schedule cost is 122,900 microAlgos --- higher than before, but we gain transferability.

## Creation, Immutability, and Initialization

These methods are nearly identical to Chapter 3. The only change is in `initialize`, where we no longer need to worry about the contract opting into created NFTs (the creator automatically holds the full supply of assets it creates). (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/) for the creation and OnCompletion actions.)

```python
    @arc4.baremethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "This contract is immutable"

    @arc4.abimethod
    def initialize(self, vesting_asset: Asset) -> None:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(0), "Already initialized"
        self.asset_id.value = vesting_asset.id
        self.is_initialized.value = UInt64(1)
        # Opt the contract into the vesting token
        itxn.AssetTransfer(
            xfer_asset=vesting_asset,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
```

These are the same patterns from Chapter 3: bare methods for lifecycle control, admin authorization via `Txn.sender.bytes == self.admin.value`, and an inner transaction with `fee=UInt64(0)` for the ASA opt-in. If any of this is unfamiliar, revisit the corresponding sections in Chapter 3 before continuing.

## Depositing Tokens

The deposit method is unchanged from Chapter 3 --- the admin transfers vesting tokens to the contract in an [atomic group](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/):

```python
    @arc4.abimethod
    def deposit_tokens(self, deposit_txn: gtxn.AssetTransferTransaction) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert deposit_txn.asset_receiver == Global.current_application_address
        assert deposit_txn.xfer_asset == Asset(self.asset_id.value)
        assert deposit_txn.asset_amount > UInt64(0)
        return deposit_txn.asset_amount
```

## Minting the Vesting NFT

This is where the contract diverges from Chapter 3. Instead of simply writing a schedule to box storage, `create_schedule` now mints an NFT that represents ownership of the vesting position. The NFT stays with the contract until the beneficiary opts in and the admin delivers it --- a two-step pattern we will explore shortly.

*Inner transactions* are the mechanism. You used them in Chapter 3 for ASA opt-ins and token transfers. Now we use `itxn.AssetConfig` to *create* an asset from within the contract. (See [Asset Operations](https://dev.algorand.co/concepts/assets/asset-operations/) for ASA creation fields.)

```python
    @arc4.abimethod
    def create_schedule(
        self,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        nft_url: Bytes,
        metadata_hash: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert total_amount > UInt64(0), "Amount must be positive"
        assert vesting_duration > cliff_duration, "Vesting must exceed cliff"

        # Validate the MBR payment
        # Box MBR: 2,500 + 400 * (10 + 41) = 22,900
        # NFT ASA MBR: 100,000
        # Total: 122,900 microAlgos
        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(41))
        nft_mbr = UInt64(100_000)
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.amount >= box_mbr + nft_mbr

        now = Global.latest_timestamp

        # Mint the vesting NFT (contract keeps it until deliver_nft)
        nft_txn = itxn.AssetConfig(
            total=1,
            decimals=0,
            asset_name=b"Vesting NFT",
            unit_name=b"VEST",
            url=nft_url,
            metadata_hash=metadata_hash,
            default_frozen=False,
            manager=Global.current_application_address,
            clawback=Global.current_application_address,
            reserve=Global.zero_address,
            freeze=Global.zero_address,
            fee=UInt64(0),
        ).submit()

        nft_id = nft_txn.created_asset.id

        # Store the schedule keyed by NFT asset ID
        schedule = VestingSchedule(
            total_amount=arc4.UInt64(total_amount),
            claimed_amount=arc4.UInt64(0),
            start_time=arc4.UInt64(now),
            cliff_end=arc4.UInt64(now + cliff_duration),
            vesting_end=arc4.UInt64(now + vesting_duration),
            is_revoked=arc4.Bool(False),
        )
        self.schedules[arc4.UInt64(nft_id)] = schedule.copy()
        self.schedule_count.value += 1

        return nft_id

    @arc4.abimethod
    def deliver_nft(self, nft_asset: Asset, beneficiary: Account) -> None:
        """Transfer a minted NFT to the beneficiary after they opt in."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        schedule_key = arc4.UInt64(nft_asset.id)
        assert schedule_key in self.schedules, "No schedule for this NFT"

        # Verify the contract still holds the NFT
        assert nft_asset.balance(
            Global.current_application_address
        ) == 1, "Contract does not hold this NFT"

        itxn.AssetTransfer(
            xfer_asset=nft_asset,
            asset_receiver=beneficiary,
            asset_amount=1,
            fee=UInt64(0),
        ).submit()
```

There is a lot happening here. Let us unpack the new pieces.

### The NFT Role Addresses

When creating an ASA, four special addresses control what can be done with it after creation:

- **manager** --- can reconfigure or destroy the asset. We set this to the contract address so the contract can destroy the NFT during cleanup.
- **clawback** --- can transfer the asset out of any account without that account's permission. We set this to the contract address so revocation works. *This is the critical field for our design.*
- **reserve** --- informational only, no protocol authority. We set it to zero.
- **freeze** --- can freeze/unfreeze individual holdings. We set this to zero so the NFT is always freely transferable. Setting it to zero is permanent --- once zero, it can never be changed back.

> **Warning:** Setting `clawback` to the contract address means the contract can take the NFT from anyone at any time. This is necessary for revocation, but it means the NFT is not fully "sovereign" --- holders should understand that the vesting contract retains authority over it. This is visible on-chain and should be communicated clearly in your application's UI.

### The Opt-In Problem and the Two-Step Pattern

On Algorand, a recipient must opt into an ASA before they can receive it. But the NFT does not exist until the contract mints it, so the beneficiary cannot know the asset ID in advance. This is a fundamental coordination problem when minting NFTs from contracts.

*Before reading on: how would you handle this? Consider that the NFT's asset ID is only known after `create_schedule` executes.*

We solve it by splitting the process into two steps. `create_schedule` mints the NFT and stores the schedule, but the contract *keeps* the NFT. The method returns the NFT's asset ID. The admin reads this ID from the transaction result, tells the beneficiary to opt in, and then calls `deliver_nft` to transfer the NFT to the beneficiary's account.

This two-step pattern is common whenever a contract mints an ASA for a specific recipient:

1. **Mint** --- create the asset, contract holds it
2. **Coordinate** --- recipient learns the asset ID and opts in
3. **Deliver** --- contract transfers the asset to the now-opted-in recipient

The `deliver_nft` method is admin-only and verifies that the contract still holds the NFT and that a schedule exists for it. The beneficiary must be opted in before `deliver_nft` is called, or the inner asset transfer will fail.

> **Note:** An alternative approach is to call `create_schedule` using `simulate` first to predict the NFT asset ID, have the beneficiary opt in, then submit the real transaction. This works on LocalNet (where no other transactions intervene) but is fragile on TestNet or MainNet where concurrent asset creations can shift asset IDs. The two-step pattern is more robust and is what production systems use.

### MBR Accounting

Each `create_schedule` call requires the caller to send a payment covering two MBR costs:

1. **Box MBR**: 2,500 + 400 × (10 + 41) = 22,900 microAlgos for the schedule box
2. **NFT ASA MBR**: 100,000 microAlgos because creating an ASA from the contract increases the contract's minimum balance

The total is 122,900 microAlgos per schedule. The `mbr_payment` grouped transaction must cover at least this amount. Compare with Chapter 3's 32,500 microAlgos per schedule --- the NFT adds significant cost, but transferability is the tradeoff.

### Inner Transaction Fees

The `create_schedule` method executes one inner transaction (asset creation), plus the outer application call and the MBR payment. The minimum group fee is:

- 1,000 (MBR payment) + 1,000 (app call) + 1,000 (inner AssetConfig) = 3,000 microAlgos total

The `deliver_nft` call adds one more inner transaction (asset transfer), needing 1,000 (app call) + 1,000 (inner AssetTransfer) = 2,000 microAlgos. With fee pooling, a single transaction in each group can overpay to cover the inner fees.

## Claiming with NFT Ownership Verification

In Chapter 3, `claim()` took no arguments --- it identified the caller by `Txn.sender` and looked up `self.schedules[Txn.sender]`. Now the caller passes the NFT asset ID, and the contract verifies ownership:

```python
    @arc4.abimethod
    def claim(self, nft_asset: Asset) -> UInt64:
        # Verify the caller holds this NFT
        assert nft_asset.balance(Txn.sender) == 1, "Caller does not hold this NFT"

        schedule_key = arc4.UInt64(nft_asset.id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()

        assert not schedule.is_revoked.native, "Schedule revoked"

        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        already_claimed = schedule.claimed_amount.as_uint64()
        claimable = vested - already_claimed
        assert claimable > UInt64(0), "Nothing to claim"

        # Cap to the contract's actual token balance.
        # If the admin over-committed schedules, this prevents a hard failure
        # and lets the holder claim whatever remains.
        vesting_asset = Asset(self.asset_id.value)
        contract_balance = vesting_asset.balance(Global.current_application_address)
        if claimable > contract_balance:
            claimable = contract_balance

        # Send tokens to the holder
        itxn.AssetTransfer(
            xfer_asset=vesting_asset,
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        # Record the claim
        schedule.claimed_amount = arc4.UInt64(already_claimed + claimable)
        self.schedules[schedule_key] = schedule.copy()

        return claimable
```

The core claim logic follows Chapter 3 --- `calculate_vested` computes how much has vested, subtracts what was already claimed, and transfers the difference. One important addition is the balance cap: if the admin created more schedules than the deposited token supply can cover, the `claimable` amount is capped to whatever the contract actually holds. This prevents a hard protocol-level failure and lets the holder claim whatever remains gracefully. The key architectural change is in the first two lines:

1. `nft_asset.balance(Txn.sender) == 1` --- this checks that the caller's account holds exactly one unit of the NFT. If the caller transferred the NFT to someone else, this check fails. If someone else transferred it *to* the caller, it succeeds. Ownership is determined by asset balance, not by a stored address.

2. `arc4.UInt64(nft_asset.id)` --- the NFT's asset ID is used directly as the box key to look up the schedule.

This is the *ownership-by-asset* pattern: instead of binding rights to an address, you bind them to a token. Anyone who holds the token can exercise the right. The token is transferable using standard ASA operations, so the right becomes transferable without any special logic in the contract. (See [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/) for how asset balance reads consume foreign references.)

> **Note:** The caller must be opted into both the NFT *and* the vesting token. A secondary market buyer who purchases the NFT must also opt into the vesting token before calling `claim`, or the inner asset transfer will fail. Your application's UI should guide users through both opt-ins.

> **Design decision: why pass the NFT as an argument?** The contract could instead iterate over the caller's assets to find a matching vesting NFT, but the AVM has no iteration primitives for account holdings. The caller must tell the contract which NFT to check. This is a common pattern on Algorand --- the caller provides hints that the contract validates.

## The Vesting Calculation

The same `calculate_vested` subroutine from Chapter 3, unchanged. It uses [wide arithmetic](https://dev.algorand.co/reference/algorand-teal/opcodes/) (`mulw`/`divmodw`) to avoid overflow when multiplying large token amounts by time durations:

```python
@subroutine
def calculate_vested(
    total: UInt64, start: UInt64, cliff_end: UInt64,
    vesting_end: UInt64, now: UInt64,
) -> UInt64:
    if now < cliff_end:
        return UInt64(0)
    if now >= vesting_end:
        return total
    elapsed = now - start
    duration = vesting_end - start
    # Wide multiply: total * elapsed → 128-bit result (high, low)
    high, low = op.mulw(total, elapsed)
    # Wide divide: (high, low) / duration → (quotient_hi, quotient_lo, remainder_hi, remainder_lo)
    q_hi, vested, r_hi, r_lo = op.divmodw(high, low, UInt64(0), duration)
    assert q_hi == 0, "Overflow in vesting calculation"
    return vested
```

Place this function outside the class, between the `VestingSchedule` struct and the `NftVesting` class. Recall from Chapter 3 that `@subroutine` functions are compiled inline by PuyaPy --- they are not ABI methods and cannot be called externally. Extracting this logic into a subroutine saves program bytes because it is called in three places: `claim`, `revoke`, and `get_claimable`.

## Revocation with Clawback

When the admin revokes a schedule, the contract must handle the NFT. We use Algorand's [clawback](https://dev.algorand.co/concepts/assets/asset-operations/) mechanism: because the contract is the NFT's designated clawback address, it can transfer the NFT out of any account without that account's permission.

There is one complication: revocation *destroys the NFT*, so the holder can no longer call `claim` afterward. To handle this cleanly, the contract settles everything in one transaction --- it transfers any vested-but-unclaimed tokens to the holder, claws back and destroys the NFT, and returns the unvested tokens to the admin.

The complete revocation flow:

1. Calculate how much has vested
2. Settle vested-but-unclaimed tokens with the current holder
3. Cap the schedule and mark it as revoked
4. Clawback the NFT from whoever currently holds it
5. Destroy the NFT (since the contract now holds the total supply)
6. Return unvested tokens to the admin

```python
    @arc4.abimethod
    def revoke(self, nft_asset: Asset, current_holder: Account) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"

        schedule_key = arc4.UInt64(nft_asset.id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert not schedule.is_revoked.native, "Already revoked"

        # Verify the holder actually has the NFT
        assert nft_asset.balance(current_holder) == 1, "Holder does not have NFT"

        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        already_claimed = schedule.claimed_amount.as_uint64()
        unvested = schedule.total_amount.as_uint64() - vested
        claimable = vested - already_claimed

        # Settle: transfer any vested-but-unclaimed tokens to the holder
        if claimable > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=current_holder,
                asset_amount=claimable,
                fee=UInt64(0),
            ).submit()

        # Clawback the NFT from the current holder
        itxn.AssetTransfer(
            xfer_asset=nft_asset,
            asset_sender=current_holder,
            asset_receiver=Global.current_application_address,
            asset_amount=1,
            fee=UInt64(0),
        ).submit()

        # Destroy the NFT (contract holds total supply, so destruction is allowed)
        itxn.AssetConfig(
            config_asset=nft_asset,
            fee=UInt64(0),
        ).submit()

        # Return unvested tokens to admin
        if unvested > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=Txn.sender,
                asset_amount=unvested,
                fee=UInt64(0),
            ).submit()

        # Record the revocation
        schedule.total_amount = arc4.UInt64(vested)
        schedule.claimed_amount = arc4.UInt64(vested)  # All vested tokens are now settled
        schedule.is_revoked = arc4.Bool(True)
        self.schedules[schedule_key] = schedule.copy()

        return unvested
```

### How Clawback Works

The `asset_sender` field in `itxn.AssetTransfer` is what triggers a clawback. When present, the AVM treats the transaction as a clawback operation: the *sending contract* must be the asset's designated clawback address, and `asset_sender` specifies the account being clawed from. The NFT moves from `current_holder` to the contract without the holder's permission.

This is a protocol-level capability --- it does not require any special logic in the holder's account. It works because we set `clawback=Global.current_application_address` when minting the NFT.

### Why the Admin Must Pass `current_holder`

The contract needs to know who currently holds the NFT so it can clawback from that specific account. But the AVM cannot enumerate who holds an asset --- there is no "find holder of asset X" opcode. The admin must provide this information, and the contract validates it: `nft_asset.balance(current_holder) == 1`. If the admin provides the wrong address, the assertion fails.

The `current_holder` must also be included in the transaction's `accounts` foreign array on the client side. This is the same resource reference pattern you saw with box references in Chapter 3.

> **Warning --- Known Limitation:** The settlement step sends vesting tokens to `current_holder`. If the NFT was transferred to someone who has not opted into the vesting token, the inner asset transfer will fail and the entire revocation transaction reverts. This means a holder who refuses to opt into the vesting token can effectively block revocation. In production, you would address this by checking the holder's opt-in status before attempting settlement: if they are not opted in, skip the vested token transfer and instead store the unclaimed amount for later retrieval via a separate `withdraw_settled` method. We omit this for clarity, but Exercise 5 asks you to design the solution.

### Destroying the NFT

After clawback, the contract holds the NFT's entire supply (1 unit). An `AssetConfig` inner transaction with *only* the `config_asset` field set and no other fields destroys the asset. Destruction is only possible when the creator holds the entire supply. Since the contract both created and now holds the NFT, destruction succeeds.

Destroying the NFT frees 100,000 microAlgos of MBR from the contract's account. This is one reason we prefer destruction over leaving the NFT as a worthless token --- it recovers the cost.

> **Note:** Revocation executes up to four inner transactions (vested token settlement + clawback + destroy + unvested token return). The outer transaction must have enough fee pooling to cover the worst case: 1,000 (app call) + 4 × 1,000 (inner txns) = 5,000 microAlgos. If either `claimable` or `unvested` is zero, fewer inner transactions execute, but overpaying fees is harmless.

## Cleanup

After a beneficiary has fully claimed their tokens (or after revocation has settled everything), the schedule [box](https://dev.algorand.co/concepts/smart-contracts/storage/box/) can be deleted to free its MBR. Unlike Chapter 3, we do not need to worry about the NFT during cleanup for revoked schedules --- it was already destroyed during revocation. For fully-claimed schedules, the NFT still exists but is functionally complete.

```python
    @arc4.abimethod
    def cleanup_schedule(self, nft_asset_id: UInt64) -> None:
        schedule_key = arc4.UInt64(nft_asset_id)
        assert schedule_key in self.schedules, "No schedule"
        schedule = self.schedules[schedule_key].copy()

        # Either fully claimed or revoked and settled
        assert schedule.claimed_amount.as_uint64() >= schedule.total_amount.as_uint64(), \
            "Not fully claimed"

        del self.schedules[schedule_key]
        self.schedule_count.value -= 1

        # Refund freed box MBR to admin
        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(41))
        itxn.Payment(
            receiver=Account(self.admin.value),
            amount=box_mbr,
            fee=UInt64(0),
        ).submit()
```

> **Note:** For revoked schedules, the NFT was already destroyed during `revoke`, freeing 100,000 microAlgos of MBR. However, `cleanup_schedule` only refunds the *box* MBR (22,900 microAlgos) to the admin. The freed NFT MBR remains in the contract's general balance. In a production contract, you would add a separate `withdraw_surplus` admin method to recover these funds.

> **Design decision: what about the NFT for fully-claimed schedules?** When a schedule is fully claimed but not revoked, the NFT still exists. The holder might want to keep it as a receipt or proof of participation. The contract does not force destruction. If the holder wants to recover the NFT's MBR (100,000 microAlgos on the contract), they can send the NFT back to the contract (via a standard asset transfer using `asset_close_to`), and a separate method could handle the destruction. For simplicity, we leave this as an exercise.

## Read-Only Queries

These methods let clients query vesting status without submitting a transaction via [simulate](https://dev.algorand.co/algokit/utils/python/app-client/). They are nearly identical to Chapter 3, but take an NFT asset ID instead of a beneficiary address:

```python
    @arc4.abimethod(readonly=True)
    def get_vesting_info(self, nft_asset_id: UInt64) -> VestingSchedule:
        schedule_key = arc4.UInt64(nft_asset_id)
        assert schedule_key in self.schedules, "No schedule"
        return self.schedules[schedule_key].copy()

    @arc4.abimethod(readonly=True)
    def get_claimable(self, nft_asset_id: UInt64) -> UInt64:
        schedule_key = arc4.UInt64(nft_asset_id)
        assert schedule_key in self.schedules, "No schedule"
        schedule = self.schedules[schedule_key].copy()
        if schedule.is_revoked.native:
            # Revoked schedules are fully settled; remaining is zero
            return UInt64(0)
        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        return vested - schedule.claimed_amount.as_uint64()
```

These methods use `readonly=True`, so clients can call them via `simulate` without paying fees --- instant, free queries. Note that `get_claimable` returns zero for revoked schedules because all vested tokens were settled during revocation.

## Consolidated Imports

Here is the complete import block for the contract file:

```python
from algopy import (
    ARC4Contract, Account, Asset, BoxMap, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, itxn, op, subroutine,
)
```

## Compiling and Testing

Compile the contract:

```bash
algokit project run build
```

If compilation succeeds, check `smart_contracts/artifacts/nft_vesting/` for the generated files: `NftVesting.approval.teal`, `NftVesting.clear.teal`, `NftVesting.arc56.json`, and `nft_vesting_client.py`.

Now create a deployment and interaction script. Save the following as `deploy_nft_vesting.py` in your project root. This script deploys the contract, creates a test token, deposits tokens, and creates a vesting schedule with an NFT:

```python
from pathlib import Path
import os
import struct
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Create a beneficiary and a third account (to demonstrate NFT transfer)
beneficiary = algorand.account.random()
new_holder = algorand.account.random()
for acct in [beneficiary, new_holder]:
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=admin.address, receiver=acct.address,
            amount=algokit_utils.AlgoAmount.from_algo(10),
            note=os.urandom(8),
        )
    )

# Step 1: Create a test vesting token
result = algorand.send.asset_create(
    algokit_utils.AssetCreateParams(
        sender=admin.address,
        total=10_000_000_000,
        decimals=6,
        asset_name="Vesting Token",
        unit_name="TVT",
    )
)
token_id = result.asset_id
print(f"Created vesting token: ASA ID {token_id}")

# Step 2: Deploy the NFT vesting contract
app_spec = Path("smart_contracts/artifacts/nft_vesting/NftVesting.arc56.json").read_text()
factory = algorand.client.get_app_factory(
    app_spec=app_spec,
    default_sender=admin.address,
)
app_client, deploy_result = factory.deploy()
print(f"Deployed contract: App ID {app_client.app_id}")
print(f"Contract address: {app_client.app_address}")

# Step 3: Fund the contract and initialize
composer = algorand.new_group()
composer.add_payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=app_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(300_000),
        note=os.urandom(8),
    )
)
composer.add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="initialize",
            args=[token_id],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        )
    )
)
composer.send()
print("Contract initialized")

# Step 4: Deposit tokens
# The asset transfer is passed as a method argument --- the SDK composes the group
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="deposit_tokens",
        args=[
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_id,
                amount=1_000_000_000,
                note=os.urandom(8),
            )
        ],
        note=os.urandom(8),
    )
)
print("Deposited 1,000 tokens (with 6 decimals)")

# Step 5: Create a vesting schedule (mint → opt-in → deliver)
nft_url = b"ipfs://QmExample#arc3"
metadata_hash = b"\x00" * 32  # Placeholder hash for testing

# Phase A: Create the schedule (contract mints and keeps the NFT)
# The box key depends on the NFT asset ID, which is unknown until the inner
# transaction executes. AlgoKit Utils handles this automatically: it simulates
# the transaction first to discover which resources are needed, then rebuilds
# it with the correct box references before submitting.
create_result = algorand.new_group().add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="create_schedule",
            args=[
                1_000_000_000,   # 1000 tokens (6 decimals)
                0,               # 0 cliff (for easy testing)
                31_536_000,      # 365 days vesting
                nft_url,
                metadata_hash,
                algokit_utils.PaymentParams(
                    sender=admin.address,
                    receiver=app_client.app_address,
                    amount=algokit_utils.AlgoAmount.from_micro_algo(122_900),
                    note=os.urandom(8),
                ),
            ],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(3000),
            box_references=[
                algokit_utils.BoxReference(
                    app_id=app_client.app_id, name=placeholder_box_key,
                ),
            ],
            note=os.urandom(8),
        )
    )
).send()
nft_id = create_result.returns[-1].value
print(f"Created vesting schedule with NFT ID: {nft_id}")

# Phase B: Beneficiary opts into the NFT and the vesting token
for asset_id in [nft_id, token_id]:
    algorand.send.asset_opt_in(
        algokit_utils.AssetOptInParams(
            sender=beneficiary.address, asset_id=asset_id,
            note=os.urandom(8),
        )
    )
print(f"Beneficiary opted into NFT {nft_id} and vesting token {token_id}")

# Phase C: Deliver the NFT to the beneficiary
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="deliver_nft",
        args=[nft_id, beneficiary.address],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        note=os.urandom(8),
    )
)
print(f"Delivered NFT {nft_id} to beneficiary")

# Step 6: Claim vested tokens as the beneficiary
box_key = b"v_" + struct.pack(">Q", nft_id)
beneficiary_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec,
    app_id=app_client.app_id,
    default_sender=beneficiary.address,
)
claim_result = beneficiary_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="claim",
        args=[nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        box_references=[algokit_utils.BoxReference(app_id=app_client.app_id, name=box_key)],
        note=os.urandom(8),
    )
)
print(f"Beneficiary claimed {claim_result.abi_return} tokens")

# Step 7: Demonstrate transferability --- transfer the NFT to a new holder
# New holder opts into the NFT and vesting token
for asset_id in [nft_id, token_id]:
    algorand.send.asset_opt_in(
        algokit_utils.AssetOptInParams(
            sender=new_holder.address, asset_id=asset_id,
            note=os.urandom(8),
        )
    )

# Beneficiary transfers the NFT --- a standard asset transfer, no contract involved
algorand.send.asset_transfer(
    algokit_utils.AssetTransferParams(
        sender=beneficiary.address,
        receiver=new_holder.address,
        asset_id=nft_id,
        amount=1,
        note=os.urandom(8),
    )
)
print(f"NFT transferred from beneficiary to new holder")

# New holder claims --- the contract only checks who holds the NFT
new_holder_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec,
    app_id=app_client.app_id,
    default_sender=new_holder.address,
)
claim_result = new_holder_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="claim",
        args=[nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        box_references=[algokit_utils.BoxReference(app_id=app_client.app_id, name=box_key)],
        note=os.urandom(8),
    )
)
print(f"New holder claimed {claim_result.abi_return} tokens")
```

> **Tip:** The mint-then-deliver flow is the key coordination pattern for minting NFTs from contracts. The admin creates the schedule (which mints the NFT and returns its ID), the beneficiary opts in, and then the admin calls `deliver_nft`. This avoids the fragile simulate-then-submit approach where predicted asset IDs can shift on a live network.

Run the script:

```bash
poetry run python deploy_nft_vesting.py
```

If everything works, you will see the app ID, contract address, token ID, NFT ID, and claimed amounts for both the original beneficiary and the new holder. If you get a "box read/write budget exceeded" error, make sure you are passing the correct box reference in the `box_references` parameter. If you get "balance below minimum," increase the initial funding amount.

## Testing the NFT Vesting Contract

> **Note:** Before writing tests, ensure `pytest` and `algokit-utils` are in your project's dependencies. If they are not, add them to `pyproject.toml` and run `poetry install`. See the Chapter 2 testing section for full setup details and [Testing](https://dev.algorand.co/algokit/utils/python/testing/) for AlgoKit patterns.

> **Reminder (from Chapter 2):** On LocalNet, block timestamps only advance when new blocks are produced. Use short durations (seconds, not months) for cliff and vesting periods in tests. Add `note=os.urandom(8)` to every test transaction to prevent deduplication errors.

Save the following as `tests/test_nft_vesting.py`. These tests cover the security-critical paths --- especially that only the NFT holder can claim, and that transferring the NFT transfers claim rights:

```python
import os
import struct
from pathlib import Path
import time
import pytest
import algokit_utils

APP_SPEC = Path("smart_contracts/artifacts/nft_vesting/NftVesting.arc56.json").read_text()


# --- Helpers ---

def fund(algorand, sender, receiver, micro_algo):
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=sender.address, receiver=receiver.address,
            amount=algokit_utils.AlgoAmount.from_micro_algo(micro_algo),
            note=os.urandom(8),
        )
    )

def deploy(algorand, admin):
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC, default_sender=admin.address,
    )
    return factory.deploy()[0]  # app_client

def initialize(algorand, admin, app_client, token_id):
    composer = algorand.new_group()
    composer.add_payment(algokit_utils.PaymentParams(
        sender=admin.address, receiver=app_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(300_000),
        note=os.urandom(8),
    ))
    composer.add_app_call_method_call(app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="initialize", args=[token_id],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        )
    ))
    composer.send()

def deposit(algorand, admin, app_client, token_id, amount):
    app_client.send.call(
        algokit_utils.AppClientMethodCallParams(
            method="deposit_tokens",
            args=[
                algokit_utils.AssetTransferParams(
                    sender=admin.address, receiver=app_client.app_address,
                    asset_id=token_id, amount=amount, note=os.urandom(8),
                )
            ],
            note=os.urandom(8),
        )
    )

def box_key(nft_id):
    return b"v_" + struct.pack(">Q", nft_id)

def create_schedule(algorand, admin, app_client, beneficiary, total,
                    cliff, vest, token_id):
    """Mint → opt-in → deliver. Returns the NFT asset ID."""
    url = b"ipfs://QmTest#arc3"
    meta = b"\x00" * 32

    # Step 1: Create the schedule (contract keeps the NFT)
    result = algorand.new_group().add_app_call_method_call(
        app_client.params.call(
            algokit_utils.AppClientMethodCallParams(
                method="create_schedule",
                args=[
                    total, cliff, vest, url, meta,
                    algokit_utils.PaymentParams(
                        sender=admin.address,
                        receiver=app_client.app_address,
                        amount=algokit_utils.AlgoAmount.from_micro_algo(122_900),
                        note=os.urandom(8),
                    ),
                ],
                static_fee=algokit_utils.AlgoAmount.from_micro_algo(3000),
                box_references=[
                    algokit_utils.BoxReference(
                        app_id=app_client.app_id, name=box_key(0),
                    ),
                ],
                note=os.urandom(8),
            )
        )
    ).send()
    nft_id = result.returns[-1].value

    # Step 2: Beneficiary opts in
    for asset_id in [nft_id, token_id]:
        algorand.send.asset_opt_in(algokit_utils.AssetOptInParams(
            sender=beneficiary.address, asset_id=asset_id,
            note=os.urandom(8),
        ))

    # Step 3: Deliver the NFT
    app_client.send.call(algokit_utils.AppClientMethodCallParams(
        method="deliver_nft", args=[nft_id, beneficiary.address],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        note=os.urandom(8),
    ))
    return nft_id

def client_for(algorand, app_client, account):
    return algorand.client.get_app_client_by_id(
        app_spec=APP_SPEC, app_id=app_client.app_id,
        default_sender=account.address,
    )

def claim(client, app_client, nft_id):
    return client.send.call(algokit_utils.AppClientMethodCallParams(
        method="claim", args=[nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        box_references=[algokit_utils.BoxReference(app_id=app_client.app_id, name=box_key(nft_id))],
        note=os.urandom(8),
    ))

def advance_time(algorand, seconds):
    """Sleep and submit a dummy transaction to advance LocalNet timestamp."""
    time.sleep(seconds)
    algorand.send.payment(algokit_utils.PaymentParams(
        sender=algorand.account.localnet_dispenser().address,
        receiver=algorand.account.localnet_dispenser().address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        note=os.urandom(8),
    ))


# --- Tests ---

class TestNftVesting:
    @pytest.fixture()
    def algorand(self):
        return algokit_utils.AlgorandClient.default_localnet()

    def test_full_lifecycle(self, algorand):
        """Deploy, create schedule, claim partially, claim fully, cleanup."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=0, vest=10, token_id=token_id)

        advance_time(algorand, 5)
        ben_client = client_for(algorand, app, ben)
        r = claim(ben_client, app, nft_id)
        assert r.abi_return > 0

        advance_time(algorand, 10)
        r = claim(ben_client, app, nft_id)
        assert r.abi_return > 0

    def test_nft_ownership_required(self, algorand):
        """An account without the NFT cannot claim."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        attacker = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        fund(algorand, admin, attacker, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=0, vest=30, token_id=token_id)

        advance_time(algorand, 5)

        # Attacker opts into vesting token but does NOT hold the NFT
        algorand.send.asset_opt_in(algokit_utils.AssetOptInParams(
            sender=attacker.address, asset_id=token_id, note=os.urandom(8),
        ))
        attacker_client = client_for(algorand, app, attacker)
        with pytest.raises(Exception):
            claim(attacker_client, app, nft_id)

    def test_transfer_transfers_claim_rights(self, algorand):
        """After NFT transfer, only the new holder can claim."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        buyer = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        fund(algorand, admin, buyer, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=0, vest=30, token_id=token_id)

        advance_time(algorand, 5)

        # Buyer opts in and receives the NFT
        for aid in [nft_id, token_id]:
            algorand.send.asset_opt_in(algokit_utils.AssetOptInParams(
                sender=buyer.address, asset_id=aid, note=os.urandom(8),
            ))
        algorand.send.asset_transfer(algokit_utils.AssetTransferParams(
            sender=ben.address, receiver=buyer.address,
            asset_id=nft_id, amount=1, note=os.urandom(8),
        ))

        # Original holder cannot claim
        ben_client = client_for(algorand, app, ben)
        with pytest.raises(Exception):
            claim(ben_client, app, nft_id)

        # New holder can claim
        buyer_client = client_for(algorand, app, buyer)
        r = claim(buyer_client, app, nft_id)
        assert r.abi_return > 0

    def test_admin_only_rejects_non_admin(self, algorand):
        """Non-admin callers are rejected."""
        admin = algorand.account.localnet_dispenser()
        attacker = algorand.account.random()
        fund(algorand, admin, attacker, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)

        attacker_client = client_for(algorand, app, attacker)
        with pytest.raises(Exception):
            attacker_client.send.call(algokit_utils.AppClientMethodCallParams(
                method="initialize", args=[token_id], note=os.urandom(8),
            ))

    def test_claim_before_cliff_fails(self, algorand):
        """Claiming before the cliff period ends fails."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=15, vest=30, token_id=token_id)

        # Only 2 seconds in, cliff is 15 seconds
        advance_time(algorand, 2)
        ben_client = client_for(algorand, app, ben)
        with pytest.raises(Exception):
            claim(ben_client, app, nft_id)
```

The two most important tests are `test_nft_ownership_required` and `test_transfer_transfers_claim_rights`. Together they prove the contract's core security property: only the current NFT holder can claim, and that right moves with the NFT.

## How Transferability Works in Practice

With the contract deployed, here is what transferability looks like from a user's perspective. (Standard [ASA transfers](https://dev.algorand.co/concepts/assets/asset-operations/) handle the NFT movement --- no custom transfer logic needed.)

1. **Admin creates a schedule.** An NFT is minted and transferred to the beneficiary. The NFT appears in the beneficiary's wallet alongside their other assets.

2. **Beneficiary claims periodically.** They call `claim` with their NFT's asset ID. The contract verifies they hold the NFT and releases vested tokens.

3. **Beneficiary transfers the NFT.** They send it to another address using a standard asset transfer --- the same transaction type used for sending any Algorand token. No contract interaction is needed.

4. **New holder claims.** The new holder calls `claim` with the same NFT asset ID. The contract checks their balance, sees they hold the NFT, and releases tokens to them. The contract does not know or care that ownership changed.

5. **NFT on a marketplace.** The vesting NFT can be listed on any Algorand NFT marketplace. A buyer purchases it and receives the right to future token claims. The marketplace does not need special integration with the vesting contract --- it just facilitates an ASA transfer.

This composability is the power of the ownership-by-asset pattern. The vesting contract does not need to know about wallets, marketplaces, lending protocols, or any other system. It only checks one thing: does the caller hold the NFT?

## Summary

In this chapter you learned to:

- Explain what makes an ASA an NFT on Algorand (total=1, decimals=0) and why no special contract is needed
- Use the ARC-3 standard to attach metadata to NFTs via URL and metadata hash
- Mint an ASA from within a smart contract using `itxn.AssetConfig`
- Apply the ownership-by-asset pattern to decouple rights from addresses
- Use clawback to reclaim NFTs during revocation and destroy them to recover MBR
- Calculate MBR implications when a contract creates ASAs (100,000 microAlgos per asset)
- Coordinate opt-in timing using the mint-then-deliver pattern for contract-minted ASAs

| Step | Feature | Concepts Introduced |
|------|---------|---------------------|
| 1 | NFT minting | `itxn.AssetConfig` for ASA creation, role addresses (manager, clawback, freeze, reserve), inner transaction fee budgeting |
| 2 | ARC-3 metadata | Off-chain metadata via URL + hash, IPFS hosting pattern, `#arc3` convention |
| 3 | Ownership-by-asset | `Asset.balance()` for ownership verification, decoupling rights from addresses |
| 4 | Transferability | Standard ASA transfers for right transfer, composability with wallets and marketplaces |
| 5 | Clawback on revoke | `asset_sender` field for clawback, NFT destruction via empty `AssetConfig`, MBR recovery |
| 6 | Settle on revoke | Vested-but-unclaimed token transfer before NFT destruction, claimed_amount bookkeeping |
| 7 | Balance-capped claims | Defensive `Asset.balance()` check prevents hard failure if contract is under-funded |
| 8 | Box key design | Keying by asset ID instead of address, MBR tradeoffs |

In the next chapter, we build a constant product AMM (Chapter 5) where multi-token accounting, price curves, and LP token mechanics introduce a new level of complexity. The inner transaction and ASA creation patterns from this chapter will reappear --- the AMM mints its own LP token using the same `itxn.AssetConfig` approach.

## Exercises

1. **(Apply)** The `cleanup_schedule` method does not destroy the NFT for fully-claimed (non-revoked) schedules. Add a `close_nft` method where the NFT holder can voluntarily return the NFT to the contract for destruction, recovering the 100,000 microAlgo MBR. What should happen to the recovered MBR --- should it go to the holder, the admin, or be split?

2. **(Analyze)** A secondary market buyer purchases a vesting NFT from a team member. The buyer pays 500 Algo for a schedule with 10,000 tokens remaining. The next day, the admin calls `revoke`. The buyer loses their 500 Algo investment and receives only whatever had vested in that single day. Is this a bug or a feature? How would you modify the contract to protect secondary market buyers while still allowing revocation?

3. **(Analyze)** The contract sets `freeze=Global.zero_address` so NFTs are always transferable. What would happen if you set `freeze=Global.current_application_address` instead? Design a `freeze_schedule` method that freezes an NFT when the beneficiary is under investigation. What are the legal and trust implications?

4. **(Create)** Design an extension where vesting schedules can be *split*: a holder can divide their NFT into two new NFTs, each representing a portion of the remaining allocation. What new method is needed? How do you handle the box storage (one box becomes two)? What happens to the original NFT?

5. **(Create)** The Known Limitation in the Revocation section describes how a holder who has not opted into the vesting token can block revocation. Design a solution: add opt-in status checking to `revoke` so that when the holder is not opted in, vested-but-unclaimed tokens are stored in a `pending_settlements` BoxMap instead of being transferred immediately. Add a `withdraw_settlement` method the holder can call after opting in. What are the MBR implications of the extra box?

## Further Reading

- [Algorand Standard Assets](https://dev.algorand.co/concepts/assets/overview/) --- ASA architecture, role addresses (manager, clawback, freeze, reserve)
- [Asset Operations](https://dev.algorand.co/concepts/assets/asset-operations/) --- creation, transfer, opt-in, clawback, destruction
- [ARC-3: NFT Metadata](https://dev.algorand.co/arc-standards/arc-0003/) --- URL convention, metadata hash, JSON schema
- [ARC-19: Mutable Metadata](https://dev.algorand.co/arc-standards/arc-0019/) --- template-based URLs using the reserve address
- [ARC-56: Application Specification](https://dev.algorand.co/arc-standards/arc-0056/) --- the app spec format used by typed clients and tooling
- [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/) --- foreign references, group-level sharing, box references

## Before You Continue

Before starting the AMM chapter, you should be able to:

- [ ] Explain what makes an ASA an NFT on Algorand (total=1, decimals=0)
- [ ] Use `itxn.AssetConfig` to mint an ASA from within a contract
- [ ] Apply the ownership-by-asset pattern to decouple rights from addresses
- [ ] Use clawback to reclaim NFTs and destroy them to recover MBR
- [ ] Pass grouped transactions (payment, asset transfer) as ABI method arguments
- [ ] Use the mint-then-deliver pattern to coordinate opt-in for contract-minted ASAs
- [ ] Calculate MBR implications when a contract creates ASAs

If any of these are unclear, revisit the relevant section before proceeding.
