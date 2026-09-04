\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# NFTs: Extending the Vesting Contract with Transferability

`\chaptermark{NFTs: Transferable Vesting}`{=latex}


You have a working token vesting contract. It creates schedules, tracks claims, handles revocation, and manages MBR lifecycle. But it has a limitation you may have already noticed: vesting schedules are permanently bound to the beneficiary's address. If a team member wants to sell their future token allocation, transfer it to a different wallet, or use it as collateral in a lending protocol, they cannot. The schedule is locked to whoever the admin specified at creation time.

The fix is to mint an *NFT* (Non-Fungible Token) for each vesting schedule. Whoever holds the NFT can claim the vested tokens, and transferring the NFT is a standard asset transfer that works with any Algorand wallet or marketplace. This single architectural change makes vesting positions composable: they can be traded, used as collateral, or transferred between wallets, all without modifying the contract.

You will rebuild the vesting contract from Chapter 9 with these changes, and learn along the way how NFTs work on Algorand (they are just ASAs with `total=1`), how to mint assets from within a contract via inner transactions, the ARC-3 metadata standard, the ownership-by-asset verification pattern, and the clawback mechanism for revocation. Every concept from Chapter 9 carries forward.

**Key differences from the Chapter 9 vesting contract:**

- **Box key** changes from `Account` (keyed by beneficiary address) to `arc4.UInt64` (keyed by a caller-supplied *schedule ID*). The box key is known before the transaction is submitted.
- **`claim`** takes a schedule ID and an NFT asset ID, then verifies that the NFT matches the schedule and that the caller holds it. Anyone holding the NFT can claim.
- **`revoke`** adds clawback of the NFT, NFT destruction, and unvested token return: a multi-step inner transaction sequence not needed in Chapter 9.
- **`create_schedule`** mints an NFT via inner transaction, stores the returned NFT asset ID inside the schedule, and returns it to the caller.
- **`deliver_nft`** has no Chapter 9 counterpart at all. It is the second half of every mint: the contract keeps the NFT it just created until the beneficiary has opted into an asset ID that did not exist when the group was signed, and this method is what finally hands it over.
- **Kept from Chapter 9** --- the `Claimed` event from Example 8-16, emitted by `claim` after the schedule is written back. The struct is unchanged; what changed is who its `beneficiary` field names, which is now whoever held the NFT at claim time.

## Run It First

The finished project for this chapter is in `projects/nft-vesting/`.
Run it before reading the implementation so you can watch the full
transferability loop work: the contract mints an NFT that stands for a vesting
schedule, delivers it to the beneficiary, and then honors claims from whoever
holds that NFT, including a buyer who acquired it with an ordinary asset
transfer and never touched a contract-specific method. Before you run it,
predict why minting the NFT and delivering it to the beneficiary are two
separate steps rather than one, and what has to happen between them.

```bash
cd projects/nft-vesting
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_nft_vesting
algokit project run test
```

Table 12-1 lists the output checkpoints to compare against the
workflow output.

: Table 12-1. Output checkpoints for the NFT vesting workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| Vesting ASA ID | The workflow creates the token that will be vested, then deposits it into the app |
| Schedule box and NFT ID | `create_schedule` pays 26,100 microAlgos of box MBR plus 100,000 for the inner-created NFT, and returns the new asset ID |
| NFT minted before delivery | Nobody can opt into an asset ID that does not exist yet, so minting has to come first |
| Beneficiary's claim succeeds | Claim rights follow the NFT, and the beneficiary is holding it |
| NFT transferred to the buyer | Ownership moves with a plain asset transfer; the contract has no transfer method of its own |
| Beneficiary can no longer claim | The contract checks the *current* holder, not the original recipient |
| Buyer's claim succeeds | The buyer collects the remaining vested tokens with no migration step |
| Second schedule revoked | Revocation settles vested tokens, returns the unvested remainder to the admin, destroys the NFT, and leaves the box ready for cleanup |
| Test suite passes | The suite reruns each path against LocalNet |

Without Docker or Podman, `algokit project run test-static` still runs the
contract and checks the source for the properties this chapter teaches.


## What You Need First

Both concept chapters in Part II ended with a Handoff table
naming what this project would lean on. Table 12-2 is the
other side of those two tables, collected in one place. Use it now, to see what
the contract is made of before any of it is in front of you, and later, when a
line assumes something you would rather look up than reconstruct.

The two chapters divide the work the way the project does. Chapter 10
supplies the answer to *who may claim this*, and for a transferable position
that answer changes without a method being called. Chapter 11 supplies
what that costs, and this project is the first one that is billed under three of
the four at once: an asset it holds and a box per position, which are both
EXIST, and inner transactions on every path, which is SEND. The two that are
charged in money are the two it owes.

Answer the predict column before you follow the link.

: Table 12-2. What Part II built that this project assumes

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| Example 10-6 | `claim`, which reads authority out of the schedule box and the asset holding rather than out of global state | The vesting schedule's owner changes when the NFT moves. Where must the check read from, if the answer has to change without any method being called? |
| Example 10-5 | `create_schedule`, which mints exactly one NFT against one stream | The project mints one NFT against one vesting stream. What goes wrong if the mint is re-runnable, and who ends up holding a claim? |
| Example 10-16 | The guards on `claim`, and the ones that are deliberately absent | Claiming sends tokens out. The caller is proving they *hold* an asset, not that they sent one, so which of that chapter's four questions even applies, and is the honest answer "none of them"? |
| Example 10-9 | `claim` and the read-only queries, callable by a person or by another contract | Should a vesting claim be callable by another contract? Decide before you see the project's answer, and say what it costs either way. |
| Example 11-4 | `create_schedule`'s funding payment, and the MBR accounting that sizes it | Each position is a box. Who should pay for it: the minter, the holder, or the contract? And does your answer change when the position is sold? |
| Example 11-5 | `cleanup_schedule`, which refunds the box minimum balance to the admin, hard-wired, rather than to whoever paid it | That example stores the payer because the funder and the caller diverge. This project stores no payer and refunds a fixed address instead. Find the sentence that argues this is safe here, and say what would have to change about the project to make it unsafe. |
| Example 11-8 | Every inner transaction on the mint, claim and revoke paths | A claim sends an asset. Count the transactions the caller must cover, and say what happens if you count wrong in each direction. |
| Example 11-2 | `NftVesting.__init__`, whose five `GlobalState` slots are the whole schema; there is no `state_totals` line here to read it off | That example puts the bill on the class declaration. This project declares its state a different way. Predict which of its four bills is largest, then check, and say where a reader is meant to look to total the first one. |
| Chapter 10, Exercise 5 | `create_schedule`, which will not write a position until its exact storage bill is paid | You put authority beside every record and could not price the storage it needed. Here every position costs 126,100 microAlgos before it exists. Which two of Chapter 11's bills make up that figure? |
| Chapter 11, Exercise 5 | The floor division inside `calculate_vested`, and the final claim that pays the dust back | You decided when parked dust is worth a fee to move. Every partial claim here floors toward the contract. Find where the design hands the remainder back, and say what happens to it when a schedule is revoked instead. |

## An NFT Is an ASA With `total = 1`

A vesting position is worth money, and the commission is to make it sellable. What blocks the sale is not value but form: the position is a row in a contract's box storage, and no wallet can hold a row, no marketplace can list one. The fix is to give the position the one form every Algorand wallet and marketplace already handles --- an [Algorand Standard Asset](https://dev.algorand.co/concepts/assets/overview/). An ASA becomes a non-fungible token by parameter choice alone: `total = 1`, so exactly one unit exists, and `decimals = 0`, so that unit is indivisible. That is the entire answer. On some blockchains, NFTs require a dedicated token standard with special smart contract logic (ERC-721 on Ethereum, for example); on Algorand there is no separate NFT contract, no special opcode, no distinct token type.

The same `AssetTransfer` transaction that moves fungible tokens also moves NFTs, the same opt-in mechanism applies, and the same `AssetConfig` transaction creates them. The entire Algorand NFT ecosystem (marketplaces, wallets, explorers) is built on this convention, so everything Chapter 7 taught about ASAs --- opting in (Example 7-17), sending units out of an application account (Example 7-18), creating an asset from a contract (Example 7-16) --- applies directly, exactly as Chapter 9 applied it. The only new concept is *metadata*, how an NFT communicates what it represents, and it enters the chapter at the moment the mint needs it.

## Project Setup

You are already in `projects/nft-vesting/` from Run It First. If you would rather scaffold your own, Chapter 9's setup note applies unchanged, with `nft_vesting` in place of `token_vesting`.

Delete the template-generated `deploy_config.py` inside the renamed directory. Your contract code goes in `smart_contracts/nft_vesting/contract.py`.

## The Modified Data Model

In Chapter 9, vesting schedules were stored in a `BoxMap` keyed by the beneficiary's address. When the beneficiary called `claim`, the contract looked up `self.schedules[Txn.sender]`. This coupling between identity and ownership is the thing to break.

The new design keys schedules by a caller-supplied schedule ID, while storing the NFT asset ID inside the schedule. When a user calls `claim`, they pass both the schedule ID and the NFT asset ID. The contract verifies that the NFT matches the stored schedule and that the caller holds it before releasing tokens. The schedule still does not care *who* holds the NFT --- only *that* the caller holds it.

Table 12-3 summarizes the identifiers used by the NFT vesting design.

: Table 12-3. Identifier timing for NFT vesting schedules

| Identifier / reference | Known when? | Purpose |
|------------------------|-------------|---------|
| `schedule_id` | Before signing `create_schedule` | Stable box key and lookup coordinate |
| `nft_id` | After the inner asset-creation transaction executes | Transferable authority token |
| Box key/name | Before signing `create_schedule` | `b"v_" + schedule_id`, wrapped in a `BoxReference` by the client |

Why not use the NFT asset ID as the box key? The NFT is created by an inner transaction, and the actual asset ID is not known until the application call executes. A client-side simulation can sometimes predict the ID, but Algorand asset IDs are allocated from the block transaction counter plus transaction position (the [ledger's asset semantics](https://specs.algorand.co/ledger/ledger-txn-semantics-asset) specify the rule), so the prediction can shift when the real transaction lands in a different block position. A caller-supplied schedule ID makes the box reference deterministic before signing and works the same way on LocalNet, TestNet, and MainNet.

Add the following to `smart_contracts/nft_vesting/contract.py`:

```python
from algopy import arc4

class VestingSchedule(arc4.Struct):
    nft_asset_id: arc4.UInt64
    total_amount: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_end: arc4.UInt64
    vesting_end: arc4.UInt64
    is_revoked: arc4.Bool
```

The struct grows from 41 bytes to 49 bytes because it stores the NFT asset ID. The struct still has no beneficiary field, because ownership is determined by who holds the NFT, not by a stored address.

The key difference is in the `BoxMap` declaration. (See [Algorand Python storage guide](https://algorandfoundation.github.io/puya/language-guide/storage/) for BoxMap type parameters.) Add the contract class below the struct:

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
        self.available_tokens = GlobalState(UInt64(0))
        # Schedules keyed by caller-supplied schedule ID (8 bytes)
        self.schedules = BoxMap(arc4.UInt64, VestingSchedule, key_prefix=b"v_")
```

Compare with Chapter 9's `BoxMap(Account, VestingSchedule, key_prefix=b"v_")`. The
key type changed from `Account` (32 bytes) to `arc4.UInt64` (8 bytes). This means box
names are shorter: `b"v_"` prefix (2 bytes) + 8-byte key = 10 bytes total, compared to
34 bytes previously. The value is 49 bytes, so the MBR per box is
2,500 + 400 * (10 + 49) = **26,100 microAlgos**.

However, each schedule now also requires an NFT, and creating an ASA from the contract
adds **100,000 microAlgos** to the contract's MBR. So the total per-schedule cost is
126,100 microAlgos, higher than before; transferability is what the difference buys.

`available_tokens` tracks deposited tokens that have not yet been assigned to a schedule.
This is stricter than checking the contract's live ASA balance during `claim`: the admin
cannot overcommit the pool, and every created schedule is fully backed at creation time.

## Creation, Immutability, and Initialization

These methods are nearly identical to Chapter 9. The change is in `initialize`, which never has to opt the contract into the NFTs it will mint (the creator automatically holds the full supply of assets it creates). (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/) for the creation and OnCompletion actions.)

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
        assert vesting_asset.clawback == Global.zero_address, "Unsafe clawback"
        assert vesting_asset.freeze == Global.zero_address, "Unsafe freeze"
        assert not vesting_asset.default_frozen, "Unsafe default frozen"
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

These are the same patterns from Chapter 9: bare methods for lifecycle control, admin
authorization via `Txn.sender.bytes == self.admin.value`, and an inner transaction with
`fee=UInt64(0)` for the ASA opt-in. The initialization method also rejects vesting ASAs
with a clawback address, freeze address, or default-frozen holdings. Without those checks,
an external asset controller could claw back or freeze the contract's reserved token
balance after schedules are created, undermining the backing guarantee.

## Depositing Tokens

The deposit method still uses the Chapter 9 atomic-group pattern: the admin transfers
vesting tokens to the contract and passes that asset-transfer transaction into the app
call. This version also increments `available_tokens`, because schedule creation will
reserve deposited tokens before minting the NFT.

```python
    @arc4.abimethod
    def deposit_tokens(self, deposit_txn: gtxn.AssetTransferTransaction) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert (
            deposit_txn.asset_receiver == Global.current_application_address
        ), "Deposit must go to the contract"
        assert (
            deposit_txn.xfer_asset == Asset(self.asset_id.value)
        ), "Wrong deposit asset"
        assert deposit_txn.asset_amount > UInt64(0), "Zero deposit"
        self.available_tokens.value += deposit_txn.asset_amount
        return deposit_txn.asset_amount
```

Three of Chapter 7's four questions are here --- where it went, which asset, how
much --- and the fourth, whose it was, is left unasked for the reason Chapter 9
argued at its own `deposit_tokens`: nothing is credited to anybody by name, so a
deposit funded by a treasury or an exchange on the admin's instruction corrupts
no per-account bookkeeping. `create_schedule` on the next page does bind its
payment's sender, and the asymmetry is not an oversight: that payment is a box
deposit that `cleanup_schedule` refunds to a hard-wired address, so the account
that sends it and the account that gets it back must be the same one.

## Minting and Delivering the Vesting NFT

This is where the contract diverges from Chapter 9. `create_schedule` still writes a schedule into box storage, but now it also mints an NFT that represents ownership of the vesting position. The NFT stays with the contract until the beneficiary opts in and the admin delivers it; the delivery half of that arrangement comes later in this section.

*Inner transactions* are the mechanism --- Chapter 7 taught them, and Example 7-16 is this exact move, `itxn.AssetConfig` creating an asset from inside a contract; Chapter 9 applied them to opt-ins and token transfers. The `mbr_payment` parameter follows the fund-then-call pattern from Chapter 7: the caller sends a payment to cover the MBR in the same atomic group as the app call, and the contract validates the payment amount. (See [Asset Operations](https://dev.algorand.co/concepts/assets/asset-operations/) for ASA creation fields.)

```python
    @arc4.abimethod
    def create_schedule(
        self,
        schedule_id: UInt64,
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
        assert self.available_tokens.value >= total_amount, "Insufficient tokens"

        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key not in self.schedules, "Schedule ID already exists"

        # Validate the MBR payment
        # Box MBR: 2,500 + 400 * (10 + 49) = 26,100
        # NFT ASA MBR: 100,000
        # Total: 126,100 microAlgos
        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(49))
        nft_mbr = UInt64(100_000)
        schedule_mbr = box_mbr + nft_mbr
        assert (
            mbr_payment.receiver == Global.current_application_address
        ), "MBR must go to the contract"
        assert mbr_payment.sender == Txn.sender, "MBR sender mismatch"
        assert mbr_payment.amount == schedule_mbr, "Wrong MBR payment"

        now = Global.latest_timestamp

        # Mint the vesting NFT (contract keeps it until deliver_nft)
        nft_txn = itxn.AssetConfig(
            total=UInt64(1),
            decimals=UInt64(0),
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

        # Store the schedule under the caller-supplied schedule ID
        schedule = VestingSchedule(
            nft_asset_id=arc4.UInt64(nft_id),
            total_amount=arc4.UInt64(total_amount),
            claimed_amount=arc4.UInt64(0),
            start_time=arc4.UInt64(now),
            cliff_end=arc4.UInt64(now + cliff_duration),
            vesting_end=arc4.UInt64(now + vesting_duration),
            is_revoked=arc4.Bool(False),
        )
        self.schedules[schedule_key] = schedule.copy()
        self.available_tokens.value -= total_amount
        self.schedule_count.value += UInt64(1)

        return nft_id
```

The `schedule_id` is a caller-supplied identifier provided before calling `create_schedule`. It is not an authority check and it does not replace the NFT; it only gives the client a stable box key. The contract prevents collisions with `assert schedule_key not in self.schedules`, then records the actual NFT asset ID returned by the inner transaction inside the schedule.

The `available_tokens` check is the accounting guard. Deposits increase the reserve, and
each new schedule decreases it by `total_amount`. That means the NFT can always claim
against a fully backed allocation later; the contract fails early at schedule creation
instead of failing later during a user's claim.

Table 12-4 traces the accounting through the deposit, the schedule,
and the claim, for a 1,000,000-token schedule after the admin deposits 2,000,000 tokens.

: Table 12-4. How available_tokens tracks the schedule obligation

| Moment | `available_tokens` | Schedule obligation | Contract-held vesting tokens |
|---------------------------------------------|--------------|---------------|--------------------------|
| After deposit | 2,000,000 | none | 2,000,000 |
| After schedule creation | 1,000,000 | 1,000,000 reserved | 2,000,000 |
| After 200,000-token claim | 1,000,000 | 800,000 remaining | 1,800,000 |
| After NFT transfer | 1,000,000 | unchanged | 1,800,000 |
| After final claim | 1,000,000 | fully settled | 1,000,000 |
| After revoking another 500,000-token schedule at 40% vested | unchanged | settled and capped | unvested amount returned to admin |

Notice the reserve changes at schedule creation, not at claim time. Claims spend against
an obligation that was already backed.

### ARC-3 Metadata

Two of the mint's arguments, `nft_url` and `metadata_hash`, exist because an ASA's on-chain fields are too small to describe what it stands for: a name of at most 32 bytes, a unit name of 8, a URL of 96, and a 32-byte hash. Those cannot hold a vesting schedule's terms, display an image in a wallet, or provide the structured data that marketplaces need. [ARC-3](https://dev.algorand.co/arc-standards/arc-0003/) is the convention that stretches them: the `url` field points to a JSON metadata file (typically hosted on IPFS), the `metadata_hash` field contains the SHA-256 hash of that JSON for integrity verification, and the URL ends with `#arc3` to signal that the asset follows the standard. An ARC-3 metadata file for a vesting NFT might look like:

```json
{
  "name": "Vesting Schedule #1",
  "description": "1,000,000 TVT vesting over 12 months with 3-month cliff",
  "properties": {
    "schedule_id": 42,
    "total_amount": 1000000,
    "cliff_months": 3,
    "vesting_months": 12,
    "vesting_asset_id": 12345,
    "contract_app_id": 67890
  }
}
```

The `properties` object is freeform: you can put any domain-specific attributes there. Wallets and explorers that support ARC-3 will display the name and description; specialized UIs can read the properties to show vesting details.

The admin prepares the metadata JSON and uploads it to IPFS *before* calling `create_schedule` --- the `schedule_id` is known at that point, so include it in the metadata or in your app's indexed records --- and passes the resulting IPFS URL and hash as the two arguments the contract embeds in the minted NFT. This keeps the contract simple: it does not need to construct JSON or interact with IPFS.

::: {.note}
An alternative standard, [ARC-19](https://dev.algorand.co/arc-standards/arc-0019/), allows mutable metadata by encoding an IPFS content identifier in the ASA's reserve address. This is useful when metadata changes over time (e.g., updating a "percent vested" field). For this chapter, ARC-3's immutable approach is sufficient: the vesting terms are fixed at creation. A third convention, *ARC-69*, stores the metadata JSON in the note field of the most recent asset-config transaction, with no off-chain file to host, at the cost of indexer-based retrieval.
:::

### The NFT Role Addresses

When creating an ASA, four special addresses control what can be done with it after creation:

- **manager** --- can reconfigure or destroy the asset. Set to the contract address so the contract can destroy the NFT during revocation.
- **clawback** --- can transfer the asset out of any account without that account's permission. Set to the contract address so revocation works. *This is the critical field for this design.*
- **reserve** --- informational only, no protocol authority. Set to zero.
- **freeze** --- can freeze/unfreeze individual holdings. Set to zero so the NFT is always freely transferable. Setting it to zero is permanent: once zero, it can never be changed back.

::: {.gotcha #clawback-is-custody topic="ASAs" title="A contract-held clawback address is custody, and it is visible on-chain"}
Setting `clawback` to the contract address means the contract can take the NFT from anyone at any time. This is necessary for revocation, but it means the NFT is not fully "sovereign": holders should understand that the vesting contract retains authority over it. This is visible on-chain and should be communicated clearly in your application's UI.
:::

That authority solves revocation, but it does not solve the recipient opt-in problem by itself.

### The Opt-In Problem

`create_schedule` ends in a strange place: the contract is holding an NFT it minted for someone else. The obvious completion is one more inner transaction at the end of the method --- mint, then send, in one call.

*Before reading on: why would that final inner transfer always fail, no matter how the client is written?*

Because on Algorand, a recipient must opt into an ASA before they can receive it --- and the beneficiary cannot have opted into this NFT. It did not exist until the mint inside this very call executed. There is no asset ID to opt into before the transaction runs, and by the time there is one, every transaction in the group has already been signed. This is a fundamental coordination problem for contract-minted assets: delivery needs an opt-in, and the opt-in needs an asset ID that only the mint can produce.

So the contract splits minting and delivery into two calls. `create_schedule` mints the NFT, stores the schedule, and *keeps* the NFT --- that is why it returns the asset ID instead of transferring anything. The admin reads the ID from the transaction result and tells the beneficiary to opt in. Handing the NFT to the now-opted-in beneficiary is a second method, `deliver_nft`, whose only job is to finish what `create_schedule` cannot.

This two-step pattern is common whenever a contract mints an ASA for a specific recipient:

1. **Mint** --- create the asset, contract holds it
2. **Coordinate** --- recipient learns the asset ID and opts in
3. **Deliver** --- contract transfers the asset to the now-opted-in recipient

::: {.note}
An alternative approach is to call `create_schedule` using `simulate` first to predict the NFT asset ID, have the beneficiary opt in, then submit the real transaction. This can appear to work on LocalNet, but it is fragile on TestNet or MainNet because the real transaction can land at a different block position than the simulated transaction. The two-step pattern is more robust and is what production systems use.
:::

### Delivering the NFT

Before `deliver_nft` moves anything, it has three things to prove: the caller is the admin, the NFT the caller names is the one recorded in the schedule for `schedule_id`, and the contract still holds that NFT. The last check is what makes delivery one-shot --- once the NFT is out in the world, the contract's balance for it is zero and a repeat call fails.

```python
    @arc4.abimethod
    def deliver_nft(
        self,
        schedule_id: UInt64,
        nft_asset: Asset,
        beneficiary: Account,
    ) -> None:
        """Transfer a minted NFT to the beneficiary after they opt in."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert schedule.nft_asset_id.as_uint64() == nft_asset.id, "Wrong NFT"

        # Verify the contract still holds the NFT
        assert nft_asset.balance(
            Global.current_application_address
        ) == UInt64(1), "Contract does not hold this NFT"

        itxn.AssetTransfer(
            xfer_asset=nft_asset,
            asset_receiver=beneficiary,
            asset_amount=UInt64(1),
            fee=UInt64(0),
        ).submit()
```

The one condition this method cannot verify up front is on the receiving end. If the beneficiary has not opted in yet, the inner asset transfer fails and the whole call reverts --- safely: the NFT stays with the contract, and the admin calls `deliver_nft` again after the opt-in lands.

The two-step flow also has specific minimum-balance costs.

### MBR Accounting

Each `create_schedule` call requires the caller to send a payment covering two MBR costs:

1. **Box MBR**: 2,500 + 400 * (10 + 49) = 26,100 microAlgos for the schedule box
2. **NFT ASA MBR**: 100,000 microAlgos because creating an ASA from the contract increases the contract's minimum balance

The total is 126,100 microAlgos per schedule. The `mbr_payment` grouped transaction must
equal this amount and must be sent by the app-call sender. Requiring an exact payment
avoids accidentally trapping extra Algos in the app account. Compare with
Chapter 9's 32,500 microAlgos per schedule.

### Inner Transaction Fees

The `create_schedule` method executes one inner transaction (asset creation), plus the outer application call and the MBR payment. The minimum group fee is:

- 1,000 (MBR payment) + 1,000 (app call) + 1,000 (inner AssetConfig) = 3,000 microAlgos total

The `deliver_nft` call adds one more inner transaction (asset transfer), needing 1,000 (app call) + 1,000 (inner AssetTransfer) = 2,000 microAlgos. With fee pooling, a single transaction in each group can overpay to cover the inner fees.

## Claiming with NFT Ownership Verification

In Chapter 9, `claim()` took no arguments: it identified the caller by `Txn.sender` and looked up `self.schedules[Txn.sender]`. Now the caller passes a stable schedule ID plus the NFT asset ID, and the contract verifies ownership.

Chapter 9's event comes across unchanged. Add it at module level beside the `VestingSchedule` struct:

```python
class Claimed(arc4.Struct):
    """ARC-28 event: who was paid, and how much (Example 8-16's device)."""

    beneficiary: arc4.Address
    amount: arc4.UInt64
```

The struct is the same one; the address it carries is not. In Chapter 9 the `beneficiary` field could only ever name the account the admin wrote into the box. Here it names whoever held the NFT when the claim landed, which is the only record an indexer will have of a position changing hands between one claim and the next:

```python
    @arc4.abimethod
    def claim(self, schedule_id: UInt64, nft_asset: Asset) -> UInt64:
        # Verify the caller holds this NFT
        assert nft_asset.balance(Txn.sender) == UInt64(1), (
            "Caller does not hold this NFT"
        )

        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert schedule.nft_asset_id.as_uint64() == nft_asset.id, "Wrong NFT"

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

        vesting_asset = Asset(self.asset_id.value)

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

        arc4.emit(Claimed(arc4.Address(Txn.sender), arc4.UInt64(claimable)))
        return claimable
```

One decision in this method is easy to miss because it is made by *absence*: `claim` never asks whether `Txn.sender` is a person or a contract, which means another application whose account holds the NFT can claim --- Chapter 10's Example 10-9 taught you that a contract that has not considered inner calls is accepting them without having decided to. Here the acceptance is the decision, and it is defensible: the NFT *is* the authorization, custody is custody, and refusing contract holders would break exactly the composability a transferable position exists for (a lending protocol custodying the NFT as collateral must be able to claim). What it costs is equally nameable: any contract bug in a protocol that holds your position NFT is now a bug that can drain that position's vested tokens. The decision the absence makes is "the holder is the holder"; a stricter design would gate on `Global.caller_application_id == 0` and forfeit the composability.

The core claim logic follows Chapter 9: `calculate_vested` computes how much has
vested, subtracts what was already claimed, and transfers the difference. The contract
does not cap claims to the live app balance. Instead, `create_schedule` reserves
deposited tokens up front, so a schedule cannot be created unless its full allocation is
already backed. The architectural change is in the first two lines:

1. `nft_asset.balance(Txn.sender) == 1` checks that the caller's account holds exactly one unit of the NFT. If the caller transferred the NFT to someone else, this check fails. If someone else transferred it *to* the caller, it succeeds. Ownership is determined by asset balance, not by a stored address.

2. `schedule.nft_asset_id.as_uint64() == nft_asset.id` requires the NFT's asset ID to match the asset ID stored when the schedule was created.

This is the *ownership-by-asset* pattern: instead of binding rights to an address, you bind them to a token. Anyone who holds the token can exercise the right. The token is transferable using standard ASA operations, so the right becomes transferable without any special logic in the contract. (See [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/) for how asset balance reads consume foreign references.)

::: {.note}
The caller must be opted into both the NFT *and* the vesting token. A secondary market buyer who purchases the NFT must also opt into the vesting token before calling `claim`, or the inner asset transfer will fail. Your application's UI should guide users through both opt-ins.
:::

Why pass the NFT as an argument at all? The contract could instead iterate over the caller's assets to find a matching vesting NFT, but the AVM has no iteration primitives for account holdings. The caller must tell the contract which NFT to check. This is a common pattern on Algorand: the caller provides hints that the contract validates.

## The Vesting Calculation

The same `calculate_vested` subroutine from Chapter 9, unchanged. It uses the [wide arithmetic](https://dev.algorand.co/reference/algorand-teal/opcodes/) Chapter 6 taught (`mulw`/`divmodw`, Example 6-10) to avoid overflow when multiplying large token amounts by time durations; Chapter 9 carried the overflow argument for exactly this subroutine:

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
    # Wide multiply: total * elapsed -> 128-bit result (high, low)
    high, low = op.mulw(total, elapsed)
    # Wide divide: (high, low) / duration.
    # Returns quotient_hi, quotient_lo, remainder_hi, remainder_lo.
    q_hi, vested, r_hi, r_lo = op.divmodw(high, low, UInt64(0), duration)
    assert q_hi == 0, "Overflow in vesting calculation"
    return vested
```

Place this function outside the class, between the `VestingSchedule` struct and the `NftVesting` class. Recall from Chapter 9 that `@subroutine` functions compile to a single TEAL subroutine invoked via `callsub`/`retsub`; they are not ABI methods and cannot be called externally. That single shared body is why extracting this logic into a subroutine saves program bytes: it is called in three places (`claim`, `revoke`, and `get_claimable`) but compiled only once.

## Revocation with Clawback

*Before reading the implementation: when the admin revokes a vesting schedule, what happens to the NFT? What about the unvested tokens? And the vested-but-unclaimed tokens? Try to list the steps needed before reading on.*

When the admin revokes a schedule, the contract must handle the NFT. Algorand's [clawback](https://dev.algorand.co/concepts/assets/asset-operations/) mechanism handles it: because the contract is the NFT's designated clawback address, it can transfer the NFT out of any account without that account's permission.

There is one complication: revocation *destroys the NFT*, so the holder can no longer call `claim` afterward. To handle this cleanly, the contract settles everything in one transaction: it transfers any vested-but-unclaimed tokens to the holder, claws back and destroys the NFT, and returns the unvested tokens to the admin.

Table 12-5 walks through the complete revocation flow with a worked example: 1,000,000 total tokens, 300,000 already claimed, revoked at 50% vested.

: Table 12-5. Revocation flow with vested and unvested settlement

| Step | Action | State after |
|------|--------|-------------|
| Before | --- | Box: 1M total, 300K claimed. Contract holds 700K tokens. Holder has NFT + 300K tokens. |
| 1 | Calculate vested: 500K | vested=500K, claimable=200K (500K - 300K), unvested=500K |
| 2 | Send 200K tokens to holder | Contract holds 500K. Holder has 500K tokens. |
| 3 | Cap schedule, mark revoked | Box: total capped to 500K, is_revoked=True |
| 4 | Clawback NFT from holder | Contract holds NFT + 500K tokens |
| 5 | Destroy NFT | NFT gone. Contract holds 500K tokens. |
| 6 | Return 500K unvested to admin | Contract holds 0 tokens. Admin has 500K back. |

```python
    @arc4.abimethod
    def revoke(
        self,
        schedule_id: UInt64,
        nft_asset: Asset,
        current_holder: Account,
    ) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"

        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert schedule.nft_asset_id.as_uint64() == nft_asset.id, "Wrong NFT"
        assert not schedule.is_revoked.native, "Already revoked"

        # Verify the holder actually has the NFT
        assert nft_asset.balance(current_holder) == UInt64(1), (
            "Holder does not have NFT"
        )

        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
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
            asset_amount=UInt64(1),
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
                asset_receiver=Account(self.admin.value),
                asset_amount=unvested,
                fee=UInt64(0),
            ).submit()

        # Record the revocation
        schedule.total_amount = arc4.UInt64(vested)
        # All vested tokens are now settled
        schedule.claimed_amount = arc4.UInt64(vested)
        schedule.is_revoked = arc4.Bool(True)
        self.schedules[schedule_key] = schedule.copy()

        return unvested
```

### How Clawback Works

The `asset_sender` field in `itxn.AssetTransfer` is what triggers a clawback. When present, the AVM treats the transaction as a clawback operation: the *sending contract* must be the asset's designated clawback address, and `asset_sender` specifies the account being clawed from. The NFT moves from `current_holder` to the contract without the holder's permission.

This is a protocol-level capability; it does not require any special logic in the holder's account. It works because the mint set `clawback=Global.current_application_address`.

### Why the Admin Must Pass the Current Holder

The contract needs to know who currently holds the NFT so it can clawback from that specific account. But the AVM cannot enumerate who holds an asset: there is no "find holder of asset X" opcode. The admin must provide `current_holder`, and the contract validates it: `nft_asset.balance(current_holder) == 1`. If the admin provides the wrong address, the assertion fails.

The `current_holder` must also be included in the transaction's `accounts` foreign array on the client side. This is the resource-reference pattern Chapter 5 established for boxes (Example 5-11), which Chapter 9's scripts declared by hand.

::: {.gotcha #revocation-needs-holder-optin topic="ASAs" title="An inner transfer to a holder who never opted in reverts the whole call"}
The settlement step sends vesting tokens to `current_holder`, and a holder who has not opted into the vesting token makes that inner transfer fail --- which reverts the entire revocation, so a holder can block being revoked by refusing one opt-in. The production form checks the holder's opt-in status before attempting settlement: if they are not opted in, skip the transfer and store the unclaimed amount for later retrieval through a separate `withdraw_settled` method. A refusal you cannot prevent must never be able to veto an action you must be able to take.
:::

Exercise 8 asks you to design that solution. A related edge case: revoking while the contract itself still holds the NFT (before delivery) with `claimable > 0` would send the settlement from the contract to itself, stranding those tokens --- one more reason revocation should only happen after checking who the holder is, or before the cliff when nothing has vested. Once the holder and opt-in constraints are handled, revocation can destroy the NFT.

### Destroying the NFT

After clawback, the contract holds the NFT's entire supply (1 unit). An `AssetConfig` inner transaction with *only* the `config_asset` field set and no other fields destroys the asset. Destruction is only possible when the creator holds the entire supply. Since the contract both created and now holds the NFT, destruction succeeds.

Destroying the NFT frees 100,000 microAlgos of MBR from the contract's account. That recovery is one reason to prefer destruction over leaving the NFT as a worthless token.

::: {.note}
Revocation executes up to four inner transactions (vested token settlement + clawback + destroy + unvested token return). The outer transaction must have enough fee pooling to cover the worst case: 1,000 (app call) + 4 * 1,000 (inner txns) = 5,000 microAlgos. If either `claimable` or `unvested` is zero, fewer inner transactions execute, but overpaying fees is harmless.
:::

With the lifecycle methods in place, the last state-management task is cleanup.

## Cleanup

After a beneficiary has fully claimed their tokens (or after revocation has settled everything), the schedule [box](https://dev.algorand.co/concepts/smart-contracts/storage/box/) can be deleted to free its MBR. Unlike Chapter 9, cleanup of a revoked schedule has no NFT to worry about: it was already destroyed during revocation. For fully-claimed schedules, the NFT still exists but is functionally complete.

```python
    @arc4.abimethod
    def cleanup_schedule(self, schedule_id: UInt64) -> None:
        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule"
        schedule = self.schedules[schedule_key].copy()

        # Either fully claimed or revoked and settled
        assert (
            schedule.claimed_amount.as_uint64()
            >= schedule.total_amount.as_uint64()
        ), \
            "Not fully claimed"

        del self.schedules[schedule_key]
        self.schedule_count.value -= UInt64(1)

        # Refund freed box MBR to admin
        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(49))
        itxn.Payment(
            receiver=Account(self.admin.value),
            amount=box_mbr,
            fee=UInt64(0),
        ).submit()
```

As in Chapter 9, `cleanup_schedule` is intentionally permissionless: anyone may call it once a schedule is settled, and the MBR refund is hard-wired to the admin, so an arbitrary caller gains nothing.

::: {.note}
For revoked schedules, the NFT was already destroyed during `revoke`, freeing 100,000 microAlgos of MBR. However, `cleanup_schedule` only refunds the *box* MBR (26,100 microAlgos) to the admin. The freed NFT MBR remains in the contract's general balance. In a production contract, you would add a separate `withdraw_surplus` admin method to recover these funds.
:::

That leaves one lifecycle question for schedules that finish normally.

When a schedule is fully claimed but not revoked, the NFT still exists. The holder might want to keep it as a receipt or proof of participation. The contract does not force destruction. If the holder wants to recover the NFT's MBR (100,000 microAlgos on the contract), they can send the NFT back to the contract (via a standard asset transfer using `asset_close_to`), and a separate method could handle the destruction. Exercise 3 builds that method.

## Read-Only Queries

These methods let clients query vesting status without submitting a transaction via [simulate](https://dev.algorand.co/algokit/utils/python/app-client/). They are nearly identical to Chapter 9, but take a schedule ID instead of a beneficiary address:

```python
    @arc4.abimethod(readonly=True)
    def get_vesting_info(self, schedule_id: UInt64) -> VestingSchedule:
        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule"
        return self.schedules[schedule_key].copy()

    @arc4.abimethod(readonly=True)
    def get_claimable(self, schedule_id: UInt64) -> UInt64:
        schedule_key = arc4.UInt64(schedule_id)
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

These methods use `readonly=True`, so clients can call them via `simulate` without paying fees. `get_claimable` returns zero for revoked schedules because all vested tokens were settled during revocation.

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

Now create a deployment and interaction script. Save the following as
`deploy_nft_vesting.py` in your project root. It mirrors the finished project's
`scripts/run_nft_vesting.py`: it deploys the contract, creates a test token, deposits
tokens, and creates a vesting schedule with an NFT. The finished project drives
this flow through the generated typed client (`app_client.send.create_schedule(...)`,
generated from the contract's [ARC-56](https://dev.algorand.co/arc-standards/arc-0056/) app spec);
this script uses method-name calls such as `method="create_schedule"`. They are the
same ABI calls --- the typed wrappers just move each method's arguments into
generated argument classes.

One resource-reference detail governs the whole script: `schedule_box` is built before `create_schedule` and reused for `create_schedule`, `deliver_nft`, and `claim`. The box name comes from `schedule_id`, not from the inner-created NFT ID.

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
app_spec_path = Path(
    "smart_contracts/artifacts/nft_vesting/NftVesting.arc56.json"
)
app_spec = app_spec_path.read_text()
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
            asset_references=[token_id],
        )
    )
)
composer.send()
print("Contract initialized")

# Step 4: Deposit tokens
# The asset transfer is passed as a method argument -- the SDK composes the group
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

# Step 5: Create a vesting schedule (mint -> opt-in -> deliver)
nft_url = b"ipfs://QmLocalNetDummy#arc3"
metadata_hash = b"\x00" * 32  # LocalNet-only dummy hash for testing

# Phase A: Create the schedule (contract mints and keeps the NFT)
# The schedule ID is supplied before the call, so the box name is known before
# signing. This is safer than simulating to predict the inner-created NFT ID.
schedule_id = int.from_bytes(os.urandom(8), "big") or 1
schedule_box_key = b"v_" + struct.pack(">Q", schedule_id)
schedule_box = algokit_utils.BoxReference(
    app_id=app_client.app_id,
    name=schedule_box_key,
)
create_result = algorand.new_group().add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="create_schedule",
            args=[
                schedule_id,
                1_000_000_000,   # 1000 tokens (6 decimals)
                0,               # 0 cliff (for easy testing)
                31_536_000,      # 365 days vesting
                nft_url,
                metadata_hash,
                algokit_utils.PaymentParams(
                    sender=admin.address,
                    receiver=app_client.app_address,
                    amount=algokit_utils.AlgoAmount.from_micro_algo(126_100),
                    note=os.urandom(8),
                ),
            ],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
            box_references=[schedule_box],
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
        args=[schedule_id, nft_id, beneficiary.address],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        asset_references=[nft_id],
        account_references=[beneficiary.address],
        box_references=[schedule_box],
        note=os.urandom(8),
    )
)
print(f"Delivered NFT {nft_id} to beneficiary")

# Step 6: Claim vested tokens as the beneficiary
beneficiary_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec,
    app_id=app_client.app_id,
    default_sender=beneficiary.address,
)
claim_result = beneficiary_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="claim",
        args=[schedule_id, nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        asset_references=[token_id, nft_id],
        box_references=[schedule_box],
        note=os.urandom(8),
    )
)
print(f"Beneficiary claimed {claim_result.abi_return} tokens")

# Step 7: Demonstrate transferability -- transfer the NFT to a new holder
# New holder opts into the NFT and vesting token
for asset_id in [nft_id, token_id]:
    algorand.send.asset_opt_in(
        algokit_utils.AssetOptInParams(
            sender=new_holder.address, asset_id=asset_id,
            note=os.urandom(8),
        )
    )

# Beneficiary transfers the NFT -- a standard asset transfer, no contract involved
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

# New holder claims -- the contract only checks who holds the NFT
new_holder_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec,
    app_id=app_client.app_id,
    default_sender=new_holder.address,
)
claim_result = new_holder_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="claim",
        args=[schedule_id, nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        asset_references=[token_id, nft_id],
        box_references=[schedule_box],
        note=os.urandom(8),
    )
)
print(f"New holder claimed {claim_result.abi_return} tokens")
```

The script passes an explicit `BoxReference` built from `schedule_id`. AlgoKit Utils 4.x populates missing app-call resources automatically by default (an explicit `.send(params=algokit_utils.SendParams(populate_app_call_resources=True))` merely restates that default, per the [resource population](https://dev.algorand.co/algokit/utils/python/transaction-composer/#resource-population) documentation), but explicit references are clearer here. The schedule box name is known before the transaction is signed, so the same group works on LocalNet, TestNet, and MainNet without relying on a simulated inner-created asset ID staying stable.

The `claim` calls include the schedule box and both relevant assets: the vesting ASA for
the inner token transfer and the NFT for the holder-balance check. If you later add a
client call for `revoke`, include the schedule box, the current holder account, the NFT
asset argument, and the vesting ASA in `asset_references`.

::: {.tip}
The mint-then-deliver flow is the key coordination pattern for minting NFTs from contracts. The admin creates the schedule (which mints the NFT and returns its ID), the beneficiary opts in, and then the admin calls `deliver_nft`. This avoids the fragile simulate-then-submit approach where predicted asset IDs can shift on a live network.
:::

Run the script:

```bash
poetry run python deploy_nft_vesting.py
```

If everything works, you will see the app ID, contract address, token ID, NFT ID, and claimed amounts for both the original beneficiary and the new holder. If you get an `invalid Box reference 0x...` error, the box name in that message is the one you did not pass in the `box_references` parameter. If you get `account <address> balance <n> below min <m> (<k> assets)`, increase the initial funding amount.

## Testing the NFT Vesting Contract

The finished project ships two suites in `projects/nft-vesting/tests/`, split
the way Chapter 9's are. `test_contract_shape.py` is the fast half: no network,
eleven source-level assertions that the guards this chapter taught are present
--- the schedule-ID box map, the exact-MBR payment, the contract-held manager
and clawback on the minted NFT, the holder check on `claim`, the
clawback-then-destroy sequence in `revoke`, and the hard-wired refund address
in `cleanup_schedule`. `test_nft_vesting.py` is the slow half: a real contract,
a real NFT, and real accounts on LocalNet, driven through the generated typed
client. The listings below are that suite's actual code, not outlines.

`tests/conftest.py` is Chapter 9's fixture --- `algorand` returns a LocalNet
client or skips the file with the reason --- and the helpers imported below
live in `scripts/localnet_helpers.py` under the same rule as Chapter 9's: thin,
named wrappers over calls the deployment script already made. `advance_time` is
the one that grew a little. It is Chapter 9's sleep-then-force-a-block helper
with the clock read back afterwards: it sleeps only when the node is keeping
wall-clock time, and then produces blocks until `Global.latest_timestamp` has
actually moved the distance the test asked for, raising a named error if it
never does. The reason is that a LocalNet shared with other work may not be
keeping wall-clock time at all --- Chapter 17's farm sets a developer-mode
timestamp offset to cross 366 days, and on a node carrying an offset, sleeping
moves nothing and only new blocks move the clock. Schedules in these tests are
still measured in seconds rather than months either way.

One of those wrappers is worth printing, because it is this chapter's box-name
rule in two lines:

```python
# scripts/localnet_helpers.py
def schedule_box_key(schedule_id: int) -> bytes:
    return b"v_" + struct.pack(">Q", schedule_id)
```

The name comes from the caller's schedule ID, never from an NFT the call has
not minted yet, which is why every reference below can be built before anything
is signed.

```python
# tests/test_nft_vesting.py
from __future__ import annotations

import base64
import hashlib
import os

import pytest
from algokit_utils import (
    AlgoAmount,
    AssetTransferParams,
    CommonAppCallCreateParams,
    CommonAppCallParams,
    PaymentParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner
from algosdk.encoding import encode_address

from scripts.localnet_helpers import (
    SCHEDULE_MBR,
    advance_time,
    create_vesting_token,
    fund_account,
    fund_app_account,
    opt_account_into_asset,
    schedule_box_key,
    transfer_asset,
)
from smart_contracts.artifacts.nft_vesting.nft_vesting_client import (
    ClaimArgs,
    CleanupScheduleArgs,
    CreateScheduleArgs,
    DeliverNftArgs,
    DepositTokensArgs,
    GetClaimableArgs,
    InitializeArgs,
    NftVestingFactory,
    RevokeArgs,
)


pytestmark = pytest.mark.localnet

# ARC-28: an event is identified by the first four bytes of the sha512_256
# hash of its signature, exactly like an ARC-4 method selector.
CLAIMED_SIGNATURE = "Claimed(address,uint64)"
CLAIMED_PREFIX = hashlib.new("sha512_256", CLAIMED_SIGNATURE.encode()).digest()[:4]
```

Every test starts from a deployed, initialized, funded contract, and that setup
is Chapter 9's material rather than this chapter's: `deploy_initialized_app`
funds an admin, creates a test ASA, creates the app, funds the app account,
calls `initialize`, and deposits 2,000,000 tokens so the pool is backed before
any schedule promises out of it. It returns the four values the tests need ---
the admin, the vesting asset ID, the app client, and the create result whose
`app_address` every MBR payment is addressed to.

The two builders below are this chapter's, and they are the mint-then-deliver
split in executable form:

```python
def create_schedule(
    algorand,
    app_client,
    app_address,
    admin,
    *,
    schedule_id,
    amount,
    cliff,
    duration,
):
    mbr_txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=admin.address,
            receiver=app_address,
            amount=AlgoAmount.from_micro_algo(SCHEDULE_MBR),
        )
    )
    result = app_client.send.create_schedule(
        CreateScheduleArgs(
            schedule_id=schedule_id,
            total_amount=amount,
            cliff_duration=cliff,
            vesting_duration=duration,
            nft_url=b"ipfs://chapter12-test#arc3",
            metadata_hash=b"\0" * 32,
            mbr_payment=TransactionWithSigner(
                mbr_txn,
                algorand.account.get_signer(admin.address),
            ),
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    return result.abi_return


def deliver_nft(
    algorand,
    app_client,
    admin,
    holder,
    *,
    schedule_id,
    nft_id,
):
    opt_account_into_asset(algorand, holder, nft_id)
    app_client.send.deliver_nft(
        DeliverNftArgs(
            schedule_id=schedule_id,
            nft_asset=nft_id,
            beneficiary=holder.address,
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[nft_id],
            account_references=[holder.address],
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
```

Three arguments in `create_schedule` are decisions made earlier in this chapter,
now in their permanent home: `SCHEDULE_MBR` is the 126,100 microAlgos of box
plus NFT minimum balance, exact in both directions; the `static_fee` of 2,000
covers the app call and the inner `AssetConfig` it fires; and the box reference
names a box that does not exist yet, because the reference declares a name this
call may touch, creation included. `deliver_nft` opts the recipient in *before*
it calls, which is the opt-in problem's answer written as two lines instead of
two paragraphs --- and the schedule's box reference travels with it, because
`deliver_nft` reads the schedule to check the NFT it is about to hand over.

The claim builder is short, and its comment is the interesting part:

```python
def claim(algorand, app_client, holder, *, schedule_id, nft_id, asset_id):
    return app_client.send.claim(
        ClaimArgs(schedule_id=schedule_id, nft_asset=nft_id),
        params=CommonAppCallParams(
            sender=holder.address,
            signer=algorand.account.get_signer(holder.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id, nft_id],
            box_references=[schedule_box_key(schedule_id)],
            # Two claims by the same holder for the same schedule would
            # otherwise build byte-identical transactions inside the
            # suggested-params cache window and the second would be rejected
            # as already in the ledger, masking the refusal under test.
            note=os.urandom(8),
        ),
    )
```

AlgoKit Utils caches suggested parameters for the better part of an hour, so two
calls with the same sender, method, arguments and fee inside that window are the
same transaction, and the ledger rejects the second as a duplicate. In a test
that claims twice from the same account, that rejection arrives wearing the
costume of a contract refusal. The random note is what keeps the two calls
distinct, and it is why the failing claim below can be trusted to have failed
for the reason the test names.

The test that matters most is the chapter's thesis as an assertion --- claim
rights move with the NFT, and nobody calls a transfer method to make that happen:

```python
def test_transfer_transfers_claim_rights(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    buyer = algorand.account.random()
    fund_account(algorand, beneficiary)
    fund_account(algorand, buyer)
    opt_account_into_asset(algorand, beneficiary, asset_id)
    opt_account_into_asset(algorand, buyer, asset_id)

    schedule_id = 1
    nft_id = create_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        schedule_id=schedule_id,
        amount=1_000_000,
        cliff=1,
        duration=20,
    )
    deliver_nft(
        algorand,
        app_client,
        admin,
        beneficiary,
        schedule_id=schedule_id,
        nft_id=nft_id,
    )

    advance_time(algorand, 4)
    first_claim = claim(
        algorand,
        app_client,
        beneficiary,
        schedule_id=schedule_id,
        nft_id=nft_id,
        asset_id=asset_id,
    )
    assert 0 < first_claim.abi_return < 1_000_000

    opt_account_into_asset(algorand, buyer, nft_id)
    transfer_asset(algorand, beneficiary, buyer.address, nft_id, 1)

    with pytest.raises(Exception, match="Caller does not hold this NFT"):
        claim(
            algorand,
            app_client,
            beneficiary,
            schedule_id=schedule_id,
            nft_id=nft_id,
            asset_id=asset_id,
        )

    advance_time(algorand, 20)
    second_claim = claim(
        algorand,
        app_client,
        buyer,
        schedule_id=schedule_id,
        nft_id=nft_id,
        asset_id=asset_id,
    )
    assert first_claim.abi_return + second_claim.abi_return == 1_000_000

    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(schedule_id=schedule_id),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    with pytest.raises(Exception, match="No schedule"):
        app_client.send.get_claimable(
            GetClaimableArgs(schedule_id=schedule_id),
            params=CommonAppCallParams(
                box_references=[schedule_box_key(schedule_id)]
            ),
        )
```

The middle of that test is the only place in the project where the contract is
asked a question it can get wrong in the expensive direction: the beneficiary
who *sold* the position tries to claim from it. The last two blocks close the
lifecycle --- the two claims sum to the full grant, and the settled box is
deleted and provably gone.

The rest of the file follows the same shape:

- `test_claim_emits_arc28_claimed_event` --- a 750,000-token schedule vested to
  completion, claimed, and the confirmation's logs decoded: exactly one entry
  whose first four bytes are the `Claimed(address,uint64)` selector, then 32
  bytes of address and 8 bytes of amount. The address it asserts is the
  holder's, which is the field Chapter 9's version of this event could never
  have gotten wrong.
- `test_wrong_nft_for_schedule_fails` --- two schedules, two NFTs, both
  delivered to the same account, and a claim that pairs schedule 1 with
  schedule 2's NFT, refused with `Wrong NFT`. Delivering both first is what
  makes the refusal mean the pairing check rather than the holder check.
- `test_revoke_settles_holder_and_allows_cleanup` --- a mid-vesting `revoke`
  that returns a positive unvested remainder to the admin, leaves
  `get_claimable` at zero afterwards, and lets `cleanup_schedule` reclaim the
  box.
- `test_contract_shape.py` --- the source-property checks, runnable with no
  Docker at all via `algokit project run test-static`.

Every negative test asserts the refusal's message rather than merely that
something failed, which is Chapter 8's rule and the reason this chapter's
`deposit_tokens` and MBR assertions carry sentences at all. Run the whole thing
with `algokit project run test` from the project directory; without a reachable
LocalNet the integration file skips and reports why, which is the behavior Run
It First promised.

## How Transferability Works in Practice

With the contract deployed, here is what transferability looks like from a user's perspective. (Standard [ASA transfers](https://dev.algorand.co/concepts/assets/asset-operations/) handle the NFT movement; no custom transfer logic is needed.)

1. **Admin creates a schedule.** An NFT is minted --- and held by the contract, because a mint cannot transfer to an account that has not opted in. The beneficiary opts into the NFT's ID, the admin calls `deliver_nft`, and only then does it appear in their wallet: mint, coordinate, deliver.

   The schedule ID must travel with the NFT in your application layer. The simplest approach is to include it in the ARC-3 metadata properties. Production apps often also index `create_schedule` calls and expose the `(app_id, schedule_id, nft_id)` mapping through their UI or API.

2. **Beneficiary claims periodically.** They call `claim` with the schedule ID and their NFT's asset ID. The contract verifies the NFT matches the schedule, verifies they hold it, and releases vested tokens.

3. **Beneficiary transfers the NFT.** They send it to another address using a standard asset transfer, the same transaction type used for sending any Algorand token. No contract interaction is needed.

4. **New holder claims.** The new holder calls `claim` with the same schedule ID and NFT asset ID. The contract checks their balance, sees they hold the NFT, verifies it matches the schedule, and releases tokens to them. The contract does not know or care that ownership changed.

5. **NFT on a marketplace.** The vesting NFT can be listed on any Algorand NFT marketplace. A buyer purchases it and receives the right to future token claims. The marketplace only needs to facilitate the ASA transfer, but the buyer's wallet or vesting UI must be able to recover the schedule ID from metadata or an indexer before calling `claim`.

This composability is the power of the ownership-by-asset pattern. The vesting contract does not need to know about wallets, marketplaces, lending protocols, or any other system. It only checks one thing: does the caller hold the NFT?

## Exercises

1. **(Understand)** For each point in the mint-then-deliver workflow, write down who can
   successfully call `claim`: immediately after `create_schedule`, after `deliver_nft`,
   after the beneficiary transfers the NFT to a buyer, and after `revoke`. Which contract
   assertion enforces each answer?

2. **(Apply)** In the finished project, change the workflow helper to
   deposit fewer vesting tokens than the first schedule tries to reserve. What
   assertion fails, and why is this better than letting the schedule be created
   and failing later during `claim`?

3. **(Apply)** The `cleanup_schedule` method does not destroy the NFT for fully-claimed (non-revoked) schedules. Add a `close_nft` method where the NFT holder can voluntarily return the NFT to the contract for destruction, recovering the 100,000 microAlgo MBR. What should happen to the recovered MBR: should it go to the holder, the admin, or be split?

4. **(Analyze)** A secondary market buyer purchases a vesting NFT from a team member. The buyer pays 500 Algo for a schedule with 10,000 tokens remaining. The next day, the admin calls `revoke`. The buyer loses their 500 Algo investment and receives only whatever had vested in that single day. Is this a bug or a feature? How would you modify the contract to protect secondary market buyers while still allowing revocation?

5. **(Analyze)** The contract sets `freeze=Global.zero_address` so NFTs are always transferable. What would happen if you set `freeze=Global.current_application_address` instead? Design a `freeze_schedule` method that freezes an NFT when the beneficiary is under investigation. What are the legal and trust implications?

6. **(Analyze)** A contract mints a new ASA and must write box state about that ASA in the same call. Choose a box key that clients can reference before the call is signed. How will a later wallet or marketplace buyer discover the relationship between the box key and the created ASA?

7. **(Create)** Design an extension where vesting schedules can be *split*: a holder can divide their NFT into two new NFTs, each representing a portion of the remaining allocation. What new method is needed? How do you handle the box storage (one box becomes two)? What happens to the original NFT?

8. **(Create)** The revocation gotcha shows how a holder who has not opted into the vesting token can block revocation. Design a solution: add opt-in status checking to `revoke` so that when the holder is not opted in, vested-but-unclaimed tokens are stored in a `pending_settlements` BoxMap instead of being transferred immediately. Add a `withdraw_settlement` method the holder can call after opting in. What are the MBR implications of the extra box?

9. **(Create, cross-chapter)** Design a contract that combines patterns from Chapters 9 and 12: it creates an ASA (this chapter's inner transaction pattern), accepts deposits via an atomic group (Chapter 9's fund-then-call pattern), and uses wide arithmetic for a proportional calculation (Chapter 9's `mulw`/`divmodw`). Sketch the contract's `__init__`, one state-changing method, and the deployment script.

To reinforce this chapter's concepts, look up creating an ASA, checking an asset balance, box minimum-balance arithmetic and accepting a payment in a group in Appendix D.

## Before You Continue

You should be able to check off all five of these:

- [ ] I can say what makes an ASA an NFT (`total=1`, `decimals=0`) and mint one from inside a contract with `itxn.AssetConfig`
- [ ] I can explain what the ownership-by-asset pattern decouples, and why `claim` checks `nft_asset.balance(Txn.sender)` instead of a stored beneficiary address
- [ ] I can account for the 100,000 microAlgos a minted NFT costs the app account, and say what clawback-then-destroy gets back
- [ ] I can pass a payment and an asset transfer as ABI method arguments, and explain why mint-then-deliver is what lets a beneficiary opt into an asset that does not exist yet
- [ ] I can explain why an inner-created NFT ID is a poor box key and why a caller-supplied schedule ID fixes resource-reference timing

If any of these are unclear, revisit the relevant section before proceeding.

## Mastery Checkpoint
That is the end of Part II. The checklist above asks whether you followed the chapters. The Mastery Checkpoint printed on the next page asks something harder: whether you can build a thing this part did not show you. It is a small program with a stated acceptance test, and a fallback if you stall.
