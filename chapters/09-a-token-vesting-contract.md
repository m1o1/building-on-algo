\newpage

\part{Value Under Management}

The contracts in Part II hold other people's money and give it back on a schedule. Chapter 9 turns Part I's vesting math into a production multi-beneficiary contract; Chapters 10 and 11 supply what any contract holding value needs next --- knowing who is calling, and knowing what everything costs; Chapter 12 extends vesting into transferable NFT positions.

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# A Token Vesting Contract

You have a startup's token grant to administer: the company has raised funds, owes tokens to its team, and none of it should arrive all at once. Team members receive their allocation gradually over 12 months, with nothing released during the first 3 months (the "cliff"), and if someone leaves early, the company revokes their unvested tokens. The contract you build this chapter is a **token vesting contract**, and it is the first thing in this book that needs every foundational mechanism at once.

Chapter 8 ended with a single-beneficiary version of this contract. It was deployed, funded, demonstrably paying out, and wrong in three ways no compiler catches: a claim that returned zero instead of refusing, an overflow that only fires at a supply nobody had tested, and an assertion with nothing to say when it failed. You found all three and fixed them. What that contract still cannot do is vest to more than one person, price the storage for doing so, or take anything back when somebody leaves. That is this chapter.

Almost nothing here is new: the concept chapters of Part I were written to make this one an assembly rather than an introduction. Concretely, the whole chapter is a delta against Chapter 8's `simple_vesting_fixed.py`, and the delta is the story:

- **Kept, unchanged in kind** --- the admin captured at creation; an initialize-once guard; the contract opting itself into its asset; `fee=UInt64(0)` on every inner transaction; the vesting curve itself; the `Claimed` event from Example 8-16.
- **Changed** --- one beneficiary becomes many. Six of SimpleVesting's globals (`beneficiary`, `total`, `claimed`, `start`, `cliff`, `end`) collapse into a 41-byte `VestingSchedule` struct, one box per beneficiary, paid for by whoever creates the schedule (the old `beneficiary` global survives as the box *key*, and one field, `is_revoked`, is new). SimpleVesting's combined configure-and-deposit `initialize` splits in two --- `deposit_tokens` fills a pool, `create_schedule` promises from it --- because a pool that funds many schedules cannot be created by any one of them; the name `initialize` survives, doing ch8's `opt_in_to_asset` job. And the curve's division is swapped from `divw` to `divmodw` plus an explicit overflow assert --- a deliberate deviation from what Chapter 6 taught, argued where it happens, and reversed by you in Exercise 5.
- **New, because production is where they matter** --- `revoke` for the person who leaves, `cleanup` to reclaim a spent schedule's storage deposit, the read-only queries a wallet polls, an explicit lifecycle stance taken before the first depositor arrives, and one genuinely new patch of teaching: the encoding and array-type decisions Chapter 5 left as a labeled IOU, redeemed here at the three points where each one lands --- the encoding in the data model, the key shape beside the box arithmetic, and the array-type choice at the first read-modify-write.
- **Not yet done, on purpose** --- seven of the contract's assertions still carry no message. Table 9-2 counts them, and the testing section is where you will feel the absence: a refusal without a message can only ever be tested as "an exception was raised," which Chapter 8 taught you to distrust. Supplying the seven sentences is left to you, and the stranger-tests you write will tell you whether yours are good ones.

That is what "production version" means in this book: not different ideas, the same ideas made answerable to strangers, storage bills, and departures. The chapter builds the changed storage first, then each new capability in the order the contract's own lifecycle needs it.

## Run It First

The finished project for this chapter is in `projects/token-vesting/`.
Running it before you study any one piece shows the whole loop: deploy and fund
the app, create vesting schedules in boxes, then exercise the claim, revoke, and
cleanup workflows against a test Algorand Standard Asset (ASA). Before running
it, predict why each schedule needs its own box MBR payment, what Bob's
revocation should return to the admin, and why cleanup is a separate step after
claims and revocation.

```bash
cd projects/token-vesting
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_token_vesting
algokit project run test
```

Table 9-1 lists the output checkpoints to compare against the
workflow output.

: Table 9-1. Output checkpoints for the token vesting workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| App ID and app address | The app account is the party that will custody the vested ASA |
| Asset ID | The workflow creates its own test ASA, then the app opts into it during initialization |
| Deposit confirmation | The ASA transfer is a grouped argument to `deposit_tokens`, so tokens and accounting move together or not at all |
| Two schedules created, one at a time | Each `create_schedule` call carries an exact 32,500 microAlgo MBR payment and a `box_references` entry naming `v_` followed by the beneficiary's address |
| Alice's partial claim | Past the cliff but short of full vesting, the linear formula releases a fraction |
| Bob's revocation | Vested tokens settle to Bob and the unvested remainder returns to the admin, in one call |
| Bob's post-revoke claim, only when positive | The workflow reads `get_claimable` first, because the contract rejects a zero-amount claim |
| Cleanup refunds the MBR | Deleting an exhausted schedule box returns the 32,500 microAlgos that funded it |
| Test suite passes | The suite reruns each of those paths, including the failure cases, against LocalNet |

Without Docker or Podman, `algokit project run test-static` still runs the
contract, generates the typed client, and runs the source-shape guards for
grouped transactions, wide arithmetic, and inner-transaction fee patterns.
Treat `projects/token-vesting/` as the reference implementation; when
you are ready to build the contract yourself, work through the setup steps that
follow in a fresh project.


## What You Need First

Every concept chapter in Part I ended with a Handoff table naming
the examples this project would lean on. The two most recent are still on your
desk: Chapter 7's Table 7-1 (how this project pays out) and Chapter 8's
Table 8-2 (what its tests need) apply here verbatim, predictions and all, and
are not repeated, with one deliberate exception: the table's first row reaches
back to Chapter 8's Exercise 5, because you wrote `revoke`'s tests before any
`revoke` existed, and this chapter is where you find out what they were tests
of. The rest of Table 9-2 collects the receiving side of the *earlier* five
chapters --- the material far enough back to be worth re-anchoring.

It is not a reading list to finish before you start. Use it now, to see what
the contract is made of before any of it is in front of you, and later, when a
line assumes something you would rather look up than reconstruct. Each
reference in the first column carries its chapter in the number:
Example 6-11 lives in Chapter 6, Example 4-12
in Chapter 4.

Answer the predict column before you follow the link. A prediction you have
committed to is worth more than one you were about to make, especially when it
turns out wrong.

: Table 9-2. What Part I built that this project assumes

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| Chapter 8, Exercise 5 | `revoke`, and the schedule it ends mid-term | You wrote revoke's tests from the requirement before any such method existed. Which of your cases does this `revoke` satisfy, and which one does it decline to make a promise about? |
| Example 2-2 | The `TokenVesting` class and its `create` method | What does subclassing `ARC4Contract` generate that you would otherwise write by hand? |
| Example 2-4 | `beneficiary: Account` on `revoke`, `vesting_asset: Asset` on `initialize` | The contract receives an `Account`. What does it actually receive, and what must the transaction declare? |
| Example 2-3 | The admin, cliff and amount guards (and seven asserts that carry no message at all) | A beneficiary claims before the cliff. What should the failure tell them, and where will that sentence be stored? |
| Example 2-9 | Every deployment and interaction script below | `claim` returns a number. By what mechanism does it reach your Python? |
| Example 3-16 | `create`, which captures the admin exactly once | Configuration happens once. Which `create` value makes that the router's job rather than a flag you maintain? |
| Example 3-6 | Every read of a `VestingSchedule` field before arithmetic | How many conversions belong in a method that does arithmetic on two numeric arguments, and where do they go? |
| Example 3-19 | `get_claimable`, which a wallet polls before showing a claim button | A wallet polls this many times a second. What must the method avoid doing for those calls to cost nothing? |
| Example 3-11 | `get_vesting_info`, which returns a whole schedule in one call | Six fields, one call. What return type hands a generated client six named values rather than a blob? |
| Example 3-14 | The two actions `reject_lifecycle` claims in order to refuse them | It holds assets it owes to people. Which two on-completion actions must it never accept, and how do you say so? |
| Example 4-7 | The five globals declared in `__init__`, four of them for methods still forty pages away | How many slots does a contract reserve when the number of beneficiaries is not known at creation? |
| Example 4-20 | The decision to put schedules in boxes rather than local state | A vesting schedule is an obligation the contract owes a beneficiary. Where can it not live? |
| Example 4-12 | `VestingSchedule`, six fields in one 41-byte record | Six numbers, one record. How many state slots should that cost? |
| Example 4-4 | `available_tokens` and `beneficiary_count`, read before anything has ever written them | Two counters, declared at creation and first read in a method that may run before the method that increments them. What comes back? |
| Example 4-16 | `self.admin.value = Txn.sender.bytes`, in `create` and nowhere else | Which of `Txn.sender` and `Global.creator_address` is safe to store as the admin, and why are they the same value exactly once? |
| Example 5-6 | `self.schedules`, one box per beneficiary, keyed by address | Why can a vesting schedule not live in the beneficiary's local state? |
| Example 5-8 | The 32,500 microAlgo payment grouped with every `create_schedule` | A 32-byte address key, a 2-byte prefix, and a 41-byte record. What does one schedule cost? |
| Example 5-5 | Funding the application account before the first schedule exists | What does the signer see if that funding is short? |
| Example 5-11 | Every client call that touches a schedule box | The method takes the beneficiary as an argument. Does that alone make the box available? |
| Example 5-22 | Why this contract has no "list all schedules" method | How many schedules could such a method return before it failed, and would that number be stable? |
| Chapter 5, Exercise 5 | The grouped MBR payment `create_schedule` takes as a typed argument | You wrote down what the contract must verify about that payment. Which of your checks does this one actually make? |
| Example 6-18 | `calculate_vested`, the release curve all three payout paths call | This project's schedules are per beneficiary. What must be stored per beneficiary that the example held in three globals? |
| Example 6-10 | The wide multiply-then-divide inside `calculate_vested` | The grant is an ASA with decimals. Which ordering survives that, and at what size does the other one abort? |
| Example 6-20 | `cliff_end` and `vesting_end`, and the guard that orders them | Three parameters, three orderings to enforce. Write the assertions before you read them. |
| Example 6-11 | `Global.latest_timestamp`, read by claim, revoke, and the status query | Which of the two globals does a schedule measured in months want, and what does choosing it cost in precision? |
| Example 6-5 | `create_schedule`, which fixes a divisor for that beneficiary's whole schedule | The divisor is `vesting_end - start_time`, set once and never revisited. What does getting the guard wrong cost here? |
| Chapter 6, Exercise 3 | `revoke`, which reduces a total that has already been partly claimed | You worked out how a divisor reaches zero with no attacker involved. Which method here could drive `total - claimed` to zero the same way? |


## Project Setup

You are already in `projects/token-vesting/` from Run It First. You can reuse the project you scaffolded in Chapter 1, keep working from this book's committed copy, or scaffold a fresh one. A fresh `algokit init -t python --name token-vesting` nests the contract project one level down, at `token-vesting/projects/token-vesting` --- the layout Chapter 1 used for `my-first-contract`; `--no-workspace` flattens it if you would rather. Either way, rename `smart_contracts/hello_world` to `smart_contracts/token_vesting` before following the listings.

Your contract code goes in `smart_contracts/token_vesting/contract.py`. The build system discovers contracts by directory, so renaming the folder is all that is needed if you scaffolded. Delete the template-generated `deploy_config.py` inside the renamed directory; it references the old `HelloWorld` contract and is not needed for the scripts in this chapter.

## The Data Model

Each beneficiary's vesting terms are stored as an ARC-4 struct in box storage. The struct comes first because the contract's `__init__` method references it:

Add the following to `smart_contracts/token_vesting/contract.py`:

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

Each `arc4.UInt64` occupies 8 bytes (big-endian), `arc4.Bool` occupies 1 byte, so the struct totals 41 bytes. The same struct creates schedules, tracks claims, and reports vesting status. (See [Algorand Python ARC-4 guide](https://algorandfoundation.github.io/puya/language-guide/arc4/) for struct encoding details.)

Keeping all six fields in one struct, in one box, is a deliberate choice rather than a stylistic one. Recall the box MBR formula from Chapter 5: 2,500 microAlgos per box, plus 400 per byte of *name and value combined*. The per-box constant and the 32-byte beneficiary address in the name are charged once per box, not once per field, so splitting a struct across several boxes pays for the same address several times over. Figure 5-3 priced that comparison in the abstract; a vesting schedule is the same comparison with a real payload attached: six fields, one name, one constant.

The `arc4.UInt64` fields are not the plain `UInt64` the contract's `__init__` uses two sections from now. This is Example 3-6's division showing up in a data structure for the first time: ARC-4 types are the encoded wire format, native types are what the AVM computes on, and a field read out of a box arrives encoded. Every arithmetic path in this contract therefore opens with a conversion and closes with one, and Example 4-12 is the reason there are six fields to convert rather than six state slots to read. The `claim` method runs that conversion line by line.

Three design decisions are baked into that eleven-line struct, and this chapter takes each one up at the point where it starts to bind. The first is already visible: **every field is fixed-width, so the encoding is flat.** Chapter 3 promised that the byte-level anatomy of ARC-4 layouts would become load-bearing when box keys arrived; this is that moment, because from here on the contract's data lives as raw bytes under keys you construct by hand. Six fixed-width fields encode to exactly 41 bytes, field after field, no bookkeeping. That is not what ARC-4 does in general. Anything whose size the type does not fix --- a string, a growable array --- cannot sit inline, because the field after it would have no fixed address. So it is split: a fixed-width *offset* goes in the head, where the field would have been, and the bytes themselves go in the tail. A `string[]` holding `['a', 'bb']`, taken apart:

```text
0002              two elements
0004  0007        where element 0 and element 1 begin, counted
                  from the start of this offset list
0001  61          element 0: a length prefix of 1, then "a"
0002  6262        element 1: a length prefix of 2, then "bb"
```

Two bytes of count, four bytes of offsets, seven bytes of actual content. Every reader of that value trusts the offsets before it looks at anything else.

*Predict: Chapter 3's `Bid` struct --- a `uint64`, then a dynamic array --- is laid out the same way: the number inline, then an offset pointing at the array. A caller who disabled validation writes that offset by hand and puts a number there that points past the end of what they sent. Say what `bid.rounds` reads.*

The answer is: whatever bytes happen to sit there --- a length prefix conjured from adjacent data, then that many bytes of something that was never an array --- or an abort when the read runs off the end. Neither is a decoder error, because with validation disabled there is no decoder standing guard; there is only trust in a number an attacker wrote. A schedule with no variable-size fields has no offsets to trust, which is why it can be read out of a box, sliced, and compared without a decoder in the loop. When Chapter 12 packs and unpacks records by hand, the flatness is what makes that possible.

## A Contract That Exists

Before any tokens can vest, a contract has to exist on the blockchain. Start with the least that can exist: something that can be created and that remembers who created it.

That is Example 2-2 with a name change, and it gets two things for free that you would otherwise have to write. Example 2-5 showed what subclassing `ARC4Contract` saves you: the selector dispatch and the argument decoding for every method below. Example 4-16 showed that `__init__` runs during the creation transaction and never again. The class that follows is an inventory of what this contract will need to remember, and after the create transaction that inventory is fixed.

Add the following class to `smart_contracts/token_vesting/contract.py`, after the `VestingSchedule` struct defined in the previous section:

```python
from algopy import (
    Account, ARC4Contract, BoxMap, Bytes, GlobalState, Txn, UInt64, arc4,
)

class TokenVesting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())      # Admin address, set at creation
        self.asset_id = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.beneficiary_count = GlobalState(UInt64(0))
        self.available_tokens = GlobalState(UInt64(0))
        # Per-beneficiary vesting data, keyed by address.
        # Declared here but boxes are created on demand in create_schedule.
        self.schedules = BoxMap(Account, VestingSchedule, key_prefix=b"v_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Runs on app creation. Records who deployed it."""
        # Txn.sender is an Account object; .bytes extracts the raw 32-byte
        # public key, which is what the Bytes-typed GlobalState expects.
        self.admin.value = Txn.sender.bytes

    @arc4.abimethod(readonly=True)
    def get_admin(self) -> arc4.Address:
        return arc4.Address.from_bytes(self.admin.value)
```

Four of those five globals are declared for sections that are still forty pages
away, and `schedules` for a method that does not exist yet. That is
Example 4-7 being paid for rather than described: the schema is
written into the create transaction, so a slot you have not thought of yet is a
slot this contract will never have. Reserving `beneficiary_count` and
`available_tokens` now costs 28,500 microAlgos each and buys the option to use
them later; declaring them later is not an option at any price for a
contract that refuses updates, which this one does.

::: {.gotcha #schema-is-immutable topic="Global and local state" title="The local schema is fixed at creation; global schema grows only if you allow updates"}
The number of *local* slots an application declares is written into the create transaction and is immutable for the life of the contract. Consensus v42 lets an update rewrite *global* slots and extra pages, but only if the contract approves `UpdateApplication` --- which every contract in this book before Chapter 24 refuses. For those contracts there is still no migration hatch: a contract that needs a sixty-fifth global key needs a new application and a state migration you write yourself. The MBR is charged for what you *declare*, not what you use, so a slot reserved against future need costs 28,500 or 50,000 microAlgos whether you ever write to it or not. That is the price of the option, and it is usually worth paying.
:::

`available_tokens` will track deposited tokens not yet reserved against a
schedule. The `BoxMap` line is Example 5-6 with this contract's
payload in it, and it creates nothing on-chain: it tells the compiler that keys
are `Account` addresses, values are `VestingSchedule` structs, and every box
name begins with `b"v_"`. Boxes appear one at a time, when `create_schedule`
writes them.

Two details in `create` are Example 4-16 applied rather than explained.
Storing `Txn.sender` establishes an authority only because this method can run
exactly once, in the create transaction, where the sender and the creator are
necessarily the same account; in any method that can be called twice, the same
line hands the contract to whoever called last. And
`@arc4.baremethod(create="require")` is Example 3-16's `"require"`: the
router, not a flag you maintain, is what guarantees the once. It is a *bare*
method because there is nothing to select on, so the router matches it on the
transaction's on-completion action instead.

`readonly=True` on `get_admin` promises what Example 3-19 described
and nothing more: clients may route the call through `simulate` and get an
answer with no fee and no block. It is a claim you are making to the client,
not a constraint the protocol enforces on you.

To deploy the contract, compile it with PuyaPy and use AlgoKit. With Chapter 1's environment and the contract directory renamed as in Project Setup above, your contract code is in `smart_contracts/token_vesting/contract.py`. Compile:

```bash
algokit project run build
```

If compilation succeeds, you will see output indicating the approval and clear programs were generated. Check the `smart_contracts/artifacts/token_vesting/` directory; you should find `TokenVesting.approval.teal`, `TokenVesting.clear.teal`, `TokenVesting.arc56.json`, and a generated typed client `token_vesting_client.py`. The subdirectory name matches the contract directory name.

If you get an error about missing imports, make sure `algorand-python` is installed (it should be if you ran `algokit project bootstrap all`). If PuyaPy reports a type error, check that your type annotations match exactly, because Algorand Python is strictly typed.

::: {.note}
**A note on client style.** Chapters 1 and 2 used the generated typed client, and it stays the default everywhere a script is application code. This chapter's teaching scripts deliberately drop to the *generic* client --- string method names, hand-assembled groups, explicit `box_references` --- because watching the transaction get built is part of what the chapter teaches; a typed client populates references by simulating first, and a reference you never wrote is a reference you never learned. The reference implementation shows the other register: the workflow script in `projects/token-vesting/scripts/` and the typed half of `projects/token-vesting/tests/` drive the same flows through the typed client (`token_vesting_client.py`, generated by the build), and production integrations should look like those, not like these scripts.
:::

With LocalNet running (`algokit localnet start`), create a deployment script. Save the following as `deploy.py` in your project root:

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
deployer = algorand.account.localnet_dispenser()

app_spec_path = Path(
    "smart_contracts/artifacts/token_vesting/TokenVesting.arc56.json"
)
factory = algorand.client.get_app_factory(
    app_spec=app_spec_path.read_text(),
    default_sender=deployer.address,
)
app_client, deploy_result = factory.deploy()
print(f"App ID: {app_client.app_id}")
print(f"App Address: {app_client.app_address}")

# Call the read-only method to verify
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(method="get_admin")
)
print(f"Admin: {result.abi_return}")
```

Run it:

```bash
python deploy.py
```

You should see output like:

```text
App ID: 1001
App Address: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ
Admin: DEPLOYER_ADDRESS_HERE
```

If you see `account <address> balance <n> below min <m> (<k> assets)`, your deployer account may not have enough Algo. The LocalNet dispenser account is pre-funded with millions of Algo, so this should not happen with the default setup. If you are using a different account, fund it first.

You can inspect the deployed contract's state using the Algorand REST API. With LocalNet running, the algod endpoint is typically at `http://localhost:4001`:

```bash
# Check the application info (requires curl and jq)
TOKEN=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
curl -s http://localhost:4001/v2/applications/1001 \
  -H "X-Algo-API-Token: $TOKEN" \
  | python -m json.tool
```

This returns the application's global state, the approval and clear program hashes, and other metadata. Use this pattern throughout development to verify that state changes happen as expected.

Compilation leaves the artifacts Chapter 1 catalogued --- the two TEAL programs, the ARC-56 app spec, the typed client --- now for a contract that will custody a grant.

The application account Example 7-2 read from and Example 7-3 spent out of now belongs to something you deployed. Its address is derived from the application ID and nothing else --- `SHA512_256("appID" || big_endian_8_byte(app_id))` --- so it existed as an address before it existed as an account, and nobody holds a private key for it. Everything this contract will ever custody sits there, and the code you are about to write is the only thing that can move it.

The contract now exists on-chain and knows who created it. It cannot do anything else yet.


## Making It Immutable

Lock the contract down before adding real functionality. Example 3-14 enumerated the five on-completion actions an application call can carry and showed how a method declares which of them it will answer to; two of the five are the ones that matter to a contract holding somebody else's tokens. `UpdateApplication` replaces the code. `DeleteApplication` removes the contract. (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/).)

If you do not explicitly handle `UpdateApplication` and `DeleteApplication`, the default behavior depends on your base class. For `ARC4Contract`, unhandled actions are rejected by default, but relying on a default for security-critical behavior is risky. Be explicit. Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        """Make the contract immutable. No one can change or delete it."""
        assert False, "Contract is immutable"
```

SimpleVesting never took this stance --- on LocalNet, against your own money, it did not matter. Here it is not optional: an admin who can call `UpdateApplication` can replace the vesting logic with a transfer to themselves, and every audit and every beneficiary's trust dies with the swap. Immutable-by-assertion is the right default for a contract holding other people's tokens; the legitimate cases for an update path --- and the machinery for gating one, timelocking it, and provably closing it later --- are Chapter 24's subject.


## Accepting Tokens

The vesting contract must hold the tokens it distributes, which means holding an Algorand Standard Asset. All three of Chapter 7's rules for an asset a contract did not create for itself bind here: an account holds an asset only after opting in, the opt-in raises that account's minimum balance by 100,000 microAlgos for as long as the holding lasts, and a transfer to an account that has not opted in fails; inside a group, that takes every other transaction down with it. Example 5-5 is the arithmetic that decides whether this particular account can afford the opt-in it is about to attempt. (See [Assets Overview](https://dev.algorand.co/concepts/assets/overview/).)

The asset itself is chosen before this contract is deployed and not by it, and one of the four authorities Example 7-21 priced is a project decision in its own right. A grant token the beneficiary is meant to own outright should have no freeze address and no clawback address, because either one means the tokens this contract pays out on schedule are tokens a third party can take back off schedule. Nothing in the code below can check that for you. A vesting contract enforcing a schedule against an asset with a live clawback address is enforcing it with an asterisk, and the asterisk belongs in the grant agreement rather than in the contract.

The contract opts itself into the vesting token with an *inner transaction*, which Chapter 7 introduced: the application account signs for itself and sends an asset transfer of zero units to itself. The `fee=UInt64(0)` below is the rule from that chapter, unchanged: an inner transaction's fee comes out of the application account's own balance, so it is set to zero and the caller's fee covers both transactions instead. Here there is no group at all. `initialize` is a single application call carrying one inner transaction, so the caller sets its fee to 2,000 microAlgo and the accounting works out the same way. Pooling is what makes a zero-fee inner transaction legal, and a lone application call is a group of one.

What is new is *when* the opt-in happens: the contract must hold the asset before anybody can deposit into it, and it must be funded above MBR before it can opt in.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
from algopy import Asset, Global, UInt64, itxn

    @arc4.abimethod
    def initialize(self, vesting_asset: Asset) -> None:
        """Set the token to be vested and opt the contract into it."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(0), "Already initialized"

        self.asset_id.value = vesting_asset.id
        self.is_initialized.value = UInt64(1)

        itxn.AssetTransfer(
            xfer_asset=vesting_asset,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),  # Caller covers this via fee pooling.
        ).submit()
```

Before calling `initialize`, the client must fund the contract with enough Algo
for the MBR and set the outer transaction fee high enough to cover the inner
transaction.

The `vesting_asset: Asset` parameter is Example 2-4 arriving where it
matters: the method takes an `Asset`, and since PuyaPy 5.0 the ABI argument
travels as a plain `uint64` asset ID rather than as an index into a foreign
array. The declaration is still required and still decides whether the call
runs; it has only moved. The ID arrives by value; the *availability* of that
asset to this call comes from the transaction's resource references, and a
method that reaches for an asset nobody declared fails at the first opcode that
touches it, with `unavailable Asset` and the ID. Example 5-11 made the
same point about boxes and added the part that catches people: algokit-utils
populates missing references for you by simulating first, so a call that would
fail from the raw SDK succeeds from the typed client and teaches you nothing.
Every script in this chapter names its references explicitly, so that the
transactions you read here are the transactions the AVM actually sees.

## Compiling and Running What You Have So Far

The contract can now be created, can reject updates and deletes, and can initialize itself by opting into a vesting token. Compile and run the full workflow on LocalNet before adding more features.

Recompile after adding the `initialize` method and the immutability bare method:

```bash
algokit project run build
```

Now prove the three methods work together on LocalNet. Save the following as `test_initialize.py` in your project root --- it creates a test ASA, deploys, then funds and initializes in one atomic group:

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Step 1: Create a test token (ASA) to use as the vesting asset
result = algorand.send.asset_create(
    algokit_utils.AssetCreateParams(
        sender=admin.address,
        total=10_000_000_000,  # 10,000 tokens with 6 decimals
        decimals=6,
        default_frozen=False,
        asset_name="TestVestingToken",
        unit_name="TVT",
    )
)
token_id = result.asset_id
print(f"Created test token: ASA ID {token_id}")

# Step 2: Deploy the vesting contract
app_spec_path = Path(
    "smart_contracts/artifacts/token_vesting/TokenVesting.arc56.json"
)
factory = algorand.client.get_app_factory(
    app_spec=app_spec_path.read_text(),
    default_sender=admin.address,
)
# A bare create, because this contract's create method is a bare method.
# factory.deploy() would hand back the app you deployed last time, which is
# what a deployment script wants and not what a first run wants.
app_client, create_result = factory.send.bare.create()
print(f"Deployed contract: App ID {app_client.app_id}")
print(f"Contract address: {app_client.app_address}")

# Step 3: Fund the contract (for MBR) and call initialize
# Use a transaction group: payment + app call
composer = algorand.new_group()
composer.add_payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=app_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(200_000),  # 0.2 Algo for MBR
    )
)
composer.add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="initialize",
            args=[token_id],
            # Cover the inner transaction fee via fee pooling
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        )
    )
)
composer.send()
print(f"Initialized with token {token_id}")

# Verify: check the contract's global state
app_info = algorand.client.algod.application_info(app_client.app_id)
print("Global state:")
for kv in app_info["params"]["global-state"]:
    print(f"  {kv}")
```

Run it with `poetry run python test_initialize.py`:

```console
$ poetry run python test_initialize.py
Created test token: ASA ID 2702
Deployed contract: App ID 2703
Contract address: 4Q6XBSFFMYVNQYKYES564Z66GP65QI46AF4TT3HDC3BISUKJ53GIMBOXWE
Initialized with token 2702
Global state:
  {'key': 'YWRtaW4=', 'value': {'bytes': 'zzXFF6Cx...GOFtd7Q=',
   'type': 1, 'uint': 0}}
  {'key': 'YXNzZXRfaWQ=', 'value': {'bytes': '', 'type': 2, 'uint': 2702}}
  {'key': 'aXNfaW5pdGlhbGl6ZWQ=', 'value': {'bytes': '', 'type': 2,
   'uint': 1}}
    ... available_tokens and beneficiary_count, both still zero ...
```

Your identifiers will differ; the shape will not. The keys are base64
(`YWRtaW4=` is `admin`, `YXNzZXRfaWQ=` is `asset_id`), algod returns them in no
particular order, and the two elided above are the slots reserved at creation
for methods that do not exist yet.

Two failures are worth meeting on purpose. Fund the contract 150,000 instead of
200,000 and the group dies on a check that is not yours: the program approves,
the inner opt-in is built, and the ledger then refuses to settle an account
below its floor:

```console
>>> composer.send()          # payment of 150_000, then initialize
ValueError: Error resolving execution info via simulate in transaction 1:
transaction LIAR...PIDA: account 63QB...4XAE balance 150000 below min
200000 (1 assets)
```

That is Example 5-5's arithmetic enforced by the ledger: 100,000 for the
account to exist and 100,000 more for the asset it is opting into, with the
`(1 assets)` at the end naming the holding that raised the floor. The second
failure is the guard you wrote:

```console
>>> app_client.send.call(algokit_utils.AppClientMethodCallParams(
...     method="initialize", args=[token_id],
...     sender=stranger.address,
...     static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000)))
LogicError: Txn GB7Q...6LQQ had error 'Runtime error when executing
TokenVesting (appId: 2703) in transaction 0: Only admin' at PC 298
    ... 10 lines of TEAL trace ...
```

One refusal comes from the ledger and one from your own assertion, and only the
second one names a reason a caller can act on. This is Chapter 1's loop with a
group in step 4, and every method added below gets the same treatment before you
move on.


## Depositing Tokens

The admin deposits the tokens to be distributed, so the contract must accept an incoming asset transfer bundled in an atomic group with the method call.

This is Example 7-8, scaled up from a vault to a grant. The transfer arrives as a typed parameter rather than by index, which Example 8-6 showed is the router promising three things before your first assertion runs: that the transaction at that position is an asset transfer, that it is in this group, and that it is directly before this call. What the router does not promise is *which* asset, *how much*, or *where it went*, and those are exactly the assertions below.

Example 7-10 is the other half. A typed parameter fixes what sits at one position; it says nothing about how many other transactions the caller has attached, which is why `Global.group_size` is still checked explicitly.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
from algopy import gtxn

    @arc4.abimethod
    def deposit_tokens(
        self,
        deposit_txn: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """Admin deposits tokens into the vesting pool."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert self.is_initialized.value == UInt64(1), "Not initialized"

        assert deposit_txn.asset_receiver == Global.current_application_address
        assert deposit_txn.xfer_asset == Asset(self.asset_id.value)
        assert deposit_txn.asset_amount > UInt64(0)

        self.available_tokens.value += deposit_txn.asset_amount
        return deposit_txn.asset_amount
```

Three of Chapter 7's four questions each appear in the assertions, though not in this order: which asset, how much, where it went. The fourth, whose it was, is not asked, and its absence is a decision. `deposit_txn.sender` is never compared to anything. Authorization runs instead on the *app call's* `Txn.sender`, which must be the admin, so the question this contract asks is not "did the caller pay this?" but "did the admin authorize this arriving?" The two are different accounts on purpose: the admin may direct a deposit that a treasury, an exchange, or a grant program funds, and requiring them to be the same account would rule that out for no gain. Nothing is credited to anybody by name here (the tokens go into one undifferentiated pool), so there is no per-account bookkeeping for a mismatched sender to corrupt. Substituting one authorization question for another is safe exactly when that is true, and the tip jar in Chapter 7 is the case where it was not.

After validation, `available_tokens` increases by the amount received. Later, `create_schedule` will reserve from this counter before writing a new beneficiary schedule, which prevents the admin from promising more tokens than the contract actually holds.

That `+=` is where Chapter 7's all-or-nothing rule first pays off in a contract you are shipping. The write does not go to the ledger when the line runs; it goes to a copy the whole group shares, and the ledger takes that copy only if every transaction in the group approves, as Figure 7-2 showed. The deposit and the increment to `available_tokens` are therefore one indivisible thing: there is no state in which the contract believes it holds tokens it did not receive, and no cleanup path to write for the case where the transfer is rejected.

::: {.note}
**A check you will see, and should not copy here.** Tutorials often assert `asset_close_to == Global.zero_address` and `rekey_to == Global.zero_address` on every incoming grouped transaction. Both fields belong to the *sender's* account --- one drains that account's balance, the other reassigns its signing authority --- and the sender here is the admin, not the contract. The contract receives the `amount` it asserted either way, and its own account is reachable only by transactions it signs itself, which default both fields to zero. So the assertion buys the contract nothing and costs the admin's wallet a legal transaction shape. Where these checks *are* the whole game is Logic Signatures, whose program is the only thing standing between an account and anyone who cares to drain it; Chapter 21 takes that up properly. (See [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/).)
:::


## Creating Vesting Schedules

Each team member's vesting schedule is per-user data, and where it lives is the most consequential decision in the contract.

*Before reading on: Chapter 4 and Chapter 5 gave you three places this could go. Pick one, and say what a beneficiary could do to the contract's books if you picked wrong.*

Local state is the tempting answer, because the minimum balance is charged to the account that opts in, which feels like the right party paying. Example 4-20 already convicted it: ClearState always succeeds, whatever the clear state program says, so a schedule in Bob's local state is a debt ledger Bob can erase mid-claim and re-register fresh. A vesting schedule --- a liability, half-paid, measured against exactly the person who could delete it --- is that example's worst case wearing a suit.

So the schedules go in boxes. The rule that decides it is short enough to carry: **a record the contract owes somebody cannot live somewhere that somebody can delete.** (See [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/).)

::: {.check}
Without looking back, name the three Algorand storage types and one hard constraint on each. Which can a user delete unilaterally? Which has a schema fixed at creation? Which does the application fully control, and who pays for it?
:::

That makes the declaration in `__init__` Example 5-6 and Example 4-12 used together: a `BoxMap` for the per-account mapping, an `arc4.Struct` so six fields cost one box rather than six. The box name is the `"v_"` prefix plus a 32-byte address, so 34 bytes, and the record is 41. Run that through Example 5-8 and one beneficiary costs `2,500 + 400 * (34 + 41) = 32,500` microAlgos, about 0.033 Algo.

The `key_prefix=b"v_"` is declared rather than left to default for the sake of that arithmetic. Omit it and PuyaPy uses the attribute name instead, so `self.schedules` gives you a nine-byte prefix and a 41-byte name: a different MBR, silently, in a funding calculation you wrote by hand two sections from here. The failure surfaces as a balance error inside `create_schedule` and says nothing about box names.

The name's shape is the second of the schedule struct's three design decisions: **a prefix plus a fixed-width value, so the name can be taken apart again.** `b"v_"` plus a 32-byte address is always 34 bytes, so the map's cost is the same for every beneficiary --- the arithmetic above holds for the thousandth schedule exactly as for the first --- and the address is always the last 32 bytes of the name. The same trick works with numbers, and Chapter 12 will need it when schedule IDs replace addresses as keys:

**Example 9-1.** A key you can always take apart

<!-- example: examples/boxes/key_prefix_itob.py mode=compile -->
<!-- finder: build a compound box key that can be decomposed again -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class Keys(ARC4Contract):
    @arc4.abimethod
    def keyed(self, prefix: Bytes, n: UInt64) -> Bytes:
        # Fixed width is the point: a prefix plus itob is a key you can always
        # take apart again, because the number is always the last eight bytes.
        return prefix + op.itob(n)
```

`itob` always produces exactly eight bytes: the number seven becomes `00 00 00 00 00 00 00 07`, never the single byte `07`, so a key built as prefix-plus-`itob` can always be taken apart again --- the number is always the last eight bytes, where a variable-width encoding would leave you guessing.

`start_time`, `cliff_end`, and `vesting_end` are all written from one read of `Global.latest_timestamp`, which is Example 6-11's second clock: seconds from the proposer's wall clock rather than rounds from the ledger's own counter. This contract is denominated in seconds because a grant agreement is, and the skew Example 6-11 measured --- bounded only by monotonicity and a ceiling of roughly 25 seconds over the previous block --- is invisible against a three-month cliff. Reading the clock once is not a defence against the value moving. `Global.latest_timestamp` is the previous block's timestamp and is fixed for the whole transaction, so three reads inside one method would return three identical values. It is a defence against the reader having to know that. One named `now`, three fields derived from it, and the relationship between `start_time`, `cliff_end`, and `vesting_end` is visible on the page instead of resting on a protocol guarantee you would have to look up.

Which is also why every comparison against that clock in this contract is a `>=` and never an `==`. A cliff is a threshold you cross, not an instant you hit; Example 6-11 showed what happens to code that assumes otherwise.

Every call that touches a box has to say so in advance, and this is the first
place in the book where you write that declaration by hand rather than let the
client infer it. Example 5-11 is why: algokit-utils simulates the call,
watches which boxes it reaches for, and fills the array in for you, so a script
that would fail from the raw SDK succeeds from the typed client. Example 5-12
priced what the declaration buys: 2,048 bytes of read/write capacity per
reference. A 41-byte `VestingSchedule` fits inside one with room to spare, and
the 34-byte name that drove the MBR arithmetic above does not count against the
budget at all.

The full grouped call has three moving pieces: create the MBR payment, pass it
as the typed transaction argument, and include the beneficiary's box reference
on the app call. In this chapter the admin funds schedule MBR and receives the
refund during cleanup, so the contract rejects MBR payments from other senders.
If you want third-party sponsorship, model the sponsor and refund recipient
explicitly instead of reusing this admin-owned MBR flow.

All three, in full (client-side code, not part of the contract):

```python
# decode_address is from algosdk.encoding
mbr_txn = algorand.create_transaction.payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=app_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(32_500),
    )
)
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="create_schedule",
        args=[beneficiary_address, 1_000_000, 86_400, 31_536_000, mbr_txn],
        account_references=[beneficiary_address],
        # Client must declare the box this transaction will access
        box_references=[b"v_" + decode_address(beneficiary_address)],
    )
)
```

`create_transaction.payment` builds the payment without sending it; passing it
as the last argument is what makes the client group the two together, in that
order, which is the group shape `create_schedule` asserts. The durations are
seconds: a cliff one day out and vesting over a year.

Forgetting this declaration produces `invalid Box reference` followed by the
box name in hex, an error you will hit whenever auto-population is disabled
or you build transactions with the raw SDK. Do not confuse it with `read budget
exceeded`, which is a different failure: that one means the references were
declared and there were not enough of them for the combined size of every box
the transaction referenced, a budget charged before the program runs against
each referenced box's full stored size whether or not you read a byte of it. If
you see `invalid Box reference`, check first whether you declared the box
references.

For boxes larger than 2KB, you need multiple references to the same box (for
example, a 4KB box needs two references). Chapter 5 shows this
pattern in detail. Raw SDK `boxes`, AlgoKit Utils `box_references`, and
`algokit_utils.BoxReference` are client-side representations of this same
resource-reference idea.

::: {.gotcha #box-refs-on-every-method topic="Box storage" title="Every method that touches a box needs its own box reference"}
Every method that accesses box storage requires box references on the client side, not just `create_schedule`. The `claim`, `revoke`, `cleanup_schedule`, `get_vesting_info`, and `get_claimable` methods all read or write the beneficiary's box and must include the same `box_references` declaration. Forgetting this on read-only methods like `get_vesting_info` is a common mistake: the AVM enforces the I/O budget regardless of whether the access is a read or write.
:::

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def create_schedule(
        self,
        beneficiary: Account,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> None:
        """Create a vesting schedule for a team member."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert beneficiary not in self.schedules, "Schedule already exists"
        assert total_amount > UInt64(0), "Amount must be positive"
        assert vesting_duration > cliff_duration, "Vesting must exceed cliff"
        assert self.available_tokens.value >= total_amount, "Insufficient tokens"

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(41))
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.sender == Txn.sender
        assert mbr_payment.amount == box_mbr

        now = Global.latest_timestamp
        self.schedules[beneficiary] = VestingSchedule(
            total_amount=arc4.UInt64(total_amount),
            claimed_amount=arc4.UInt64(0),
            start_time=arc4.UInt64(now),
            cliff_end=arc4.UInt64(now + cliff_duration),
            vesting_end=arc4.UInt64(now + vesting_duration),
            is_revoked=arc4.Bool(False),
        )
        self.available_tokens.value -= total_amount
        self.beneficiary_count.value += UInt64(1)
```

Two details keep the accounting honest. First, the schedule amount must fit
inside `available_tokens`, and the contract subtracts it as soon as the schedule
is created. Tokens committed to a schedule are reserved, even if they have not
vested yet. Second, the MBR payment must equal `box_mbr` exactly. Accepting
overpayment would strand the excess Algo in the app account because
`cleanup_schedule` refunds only the storage MBR.


## Claiming Vested Tokens

This is the core logic. A beneficiary calls `claim` and receives whatever tokens have vested since their last claim. The math must be exact.

The release curve itself you have already written. Example 6-18 is this
calculation for one grant held in globals; Example 6-20 adds the cliff
branch and settles whether the linear term measures from `start` or from
`cliff` (this contract measures from `start`, so arriving at the cliff releases
a lump sum covering everything since the grant began); and Example 6-10 is the
multiply-then-divide underneath both. What is new here is that the three
parameters come out of a box instead of out of state, and that the same
subroutine has to serve three callers.

Two things about `calculate_vested` sit right on a line
Chapter 6 drew.

*Predict before reading on: a version of this contract with a narrow
`total * elapsed` multiply pays out correctly for months and then aborts.
Which call is the first one to fail, and does the grant that triggers it have
to be unusually large, or does it just have to be old? Commit to both halves;
the arithmetic below rules on them.*

The first hazard is the width. `total * elapsed` is the expression the
arithmetic asks for and the one that must never be written narrow. Example
6-18 put a number on it for a ninety-day schedule --- and in this contract the
schedule length is an *argument*, so the contract must survive the longest
schedule any admin will ever grant. Grant Chapter 8's default, four years, and
the elapsed seconds reach 126,143,999 on the last second before the schedule
closes: a narrow multiply overflows for any grant *above* 146,235,605,498
base units, about 146,235 tokens at six decimals. That is not a large grant.
It is a mid-size employee allocation, and the contract that used the narrow
form would pay out correctly for months and then abort on every call for the
rest of the term --- the answer to both halves of the prediction: the first
call to fail is the first one after the product crosses sixty-four bits, and
the grant does not have to be big, only the schedule old enough. Hence
`op.mulw`, which cannot fail: it multiplies two `UInt64`s into a 128-bit product
returned as a high word and a low word.

The second hazard is the division, and the code below does not do what
Chapter 6 told you to do. That chapter was blunt: `divw` fails
loudly on an overflowing quotient, `divmodw` fails silently, and for money you
take the loud one. This subroutine calls `op.divmodw`. What makes it safe is the
line immediately after:

```python
    q_hi, vested, r_hi, r_lo = op.divmodw(high, low, UInt64(0), duration)
    assert q_hi == 0, "Overflow in vesting calculation"
```

`divmodw` returns a 128-bit quotient in two words, and `q_hi == 0` says that
quotient fit in sixty-four. `divw` phrases the same condition differently: it
aborts when the divisor is not strictly greater than the numerator's high word.
The two are the same test. Write the numerator as $N = h \cdot 2^{64} + l$ and
the divisor as $d$. (Both opcodes abort outright at $d = 0$, so take $d \ge 1$
throughout.) If $d > h$ then $N \le h \cdot 2^{64} + (2^{64} - 1) <
(h+1) \cdot 2^{64} \le d \cdot 2^{64}$, so the quotient is below $2^{64}$ and
`q_hi` is zero. If $d \le h$ then $N \ge d \cdot 2^{64}$, so the quotient is at
least $2^{64}$ and `q_hi` is not. No pair of inputs separates them, and that
equivalence holds *here* only because the divisor's own high word is the
hardcoded `UInt64(0)` on the line above. The assertion is not a belt-and-braces
extra; it is `divw`'s abort condition written out by hand.

In *this* subroutine it can never fire. The division is reached only when
`now < vesting_end` and `now >= cliff_end >= start`, so `elapsed < duration`,
so the quotient is strictly less than `total` and therefore fits by
construction. Delete the assert and all twenty-one unit tests still pass,
because no input can make it fire. Do not rely on that: the invariant lives four
branches away from the line it protects, and the next edit to `create_schedule`
is under no obligation to preserve it. Swapping the pair for
`op.divw(high, low, duration)` moves the same guarantee into the opcode, where
no edit can drop it, and Exercise 5 asks you to make that swap. The version
below is the shape you will meet in real codebases. The general point is not
which opcode to prefer but that
**a four-word return you only wanted one word from is a place where an
overflow check has to be written, not assumed**, and Example 6-9 is
what its absence buys you in a routine that lacks this one's luck.

The division floors, so a beneficiary is paid slightly less than the exact
fraction at each intermediate claim and the dust stays in the contract, the
direction Chapter 6 argued for; the `now >= vesting_end` branch
bypasses the division entirely and pays the exact total, so the dust comes back
on the last claim.

`duration` cannot be zero on any path that reaches the division, and the
argument takes two steps rather than one. The first is
Example 6-5's rule applied at the point of establishment:
`create_schedule` asserts `vesting_duration > cliff_duration` before writing
either field, so a freshly created schedule has `vesting_end > start_time` and
`duration` is positive. The second step is the one that is easy to skip.
`revoke` also writes those fields, setting both `cliff_end` and `vesting_end`
to the revocation timestamp, so a revocation at the exact second the grant
began leaves `vesting_end == start_time` and a `duration` of zero. What saves
it is the guard immediately above: the division runs only when
`now < vesting_end`, and `now` is at least the revocation time, so the
zero-duration schedule takes the `now >= vesting_end` branch and never reaches
the divide. The divisor is guarded where it is established *and* the one method
that can un-establish it is closed off by the branch, which is the shape this
argument has to have whenever a second writer exists.

`calculate_vested` is a `@subroutine` because `claim`, `revoke`, and
`get_claimable` all need it, and the decorator makes the compiler emit one TEAL
subroutine called via `callsub`/`retsub` rather than three inlined copies
competing for the program's 2,048-byte page (extra pages exist, at 100,000 microAlgos of creator MBR each --- this contract stays under half of its first page).

Add this module-level function to `smart_contracts/token_vesting/contract.py`, placed **between** the `VestingSchedule` struct definition and the `TokenVesting` class (outside the class, not as a method). Module-level subroutines can be shared across multiple contracts in the same file. Class methods decorated with `@subroutine` are also valid and are scoped to that contract; Chapters 14 and 16 use class-method subroutines. `calculate_vested` is module-level because it is pure logic that could be reused by other contracts (see the [PuyaPy structure guide](https://algorandfoundation.github.io/puya/language-guide/structure/)):

```python
from algopy import op, subroutine

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
    high, low = op.mulw(total, elapsed)
    q_hi, vested, r_hi, r_lo = op.divmodw(high, low, UInt64(0), duration)
    assert q_hi == 0, "Overflow in vesting calculation"
    return vested
```

### What the Box Actually Holds

Every argument the subroutine takes comes out of a box, and reading them is governed by the third and last of the schedule struct's design decisions: **the record is a struct, not an array --- and if it had been an array, only some arrays would do.** PuyaPy has four array types you choose between, the choice turns on one question asked twice --- *does assignment copy, and can the value change after it is built?* --- and the answers determine both what compiles and what is storable. The schedule never became an array, but the reasoning that rejected each candidate is the same reasoning you will use whenever a record of yours does need one, and the `.copy()` rule at the centre of it governs the read `claim` is about to make.

**Example 9-2.** A value-semantics array

<!-- example: examples/boxes/array_value.py mode=compile -->
<!-- finder: understand why an array assignment needs .copy() -->

```python
from algopy import ARC4Contract, Array, UInt64, arc4


class Bag(ARC4Contract):
    @arc4.abimethod
    def two_bags(self) -> UInt64:
        a = Array[UInt64]()
        a.append(UInt64(1))
        b = a.copy()  # without .copy() this line is a compile error
        b.append(UInt64(2))
        return a.length + b.length
```

The line that matters is `b = a.copy()`: without `.copy()`, that line does not compile. `Array` has **value semantics** (two names must mean two arrays), and rather than silently copying for you or silently aliasing, PuyaPy makes you say which you meant. This is the same rule, and the same error message, that Chapter 4 met on `arc4.Struct` --- one rule, not two --- and it is the rule you will obey on the next page, the first time `claim` reads a schedule out of its box.

The other two array types are the ones the schedule was never going to be, and Table 9-3's rows record why. `ReferenceArray` is the opposite choice --- `b = a` is legal and hands out a second name for the same array, which buys cheap passing to subroutines and costs the one thing a stored record cannot give up: it lives in scratch space rather than in an encoded value, so putting one in a box fails to compile with `type is not suitable for storage`. `ImmutableArray`, usually made by calling `.freeze()` on a finished `Array`, is the mirror image: nothing can change after it is built, so plain assignment aliases safely, there is no `.copy()` to call or to need, and `.append()` returns a new array instead of mutating the old one.

**Example 9-3.** An array with its length in its type

<!-- example: examples/boxes/array_fixed_key.py mode=compile -->
<!-- finder: declare an array whose length is known at compile time -->

```python
import typing

from algopy import ARC4Contract, Box, BoxMap, FixedArray, UInt64, arc4

Slots = FixedArray[UInt64, typing.Literal[4]]


class Bag(ARC4Contract):
    def __init__(self) -> None:
        self.bag = Box(Slots, key=b"b")
        self.seen = BoxMap(Slots, UInt64, key_prefix=b"s")

    @arc4.abimethod
    def fill(self) -> UInt64:
        slots = Slots.full(UInt64(0))
        slots[0] = UInt64(7)
        # No MBR pre-flight here; this contract exists to show the types.
        self.bag.value = slots.copy()  # a box value
        self.seen[slots] = UInt64(1)  # and a fixed-length box name
        return self.bag.value.freeze()[0]
```

That listing creates two boxes and pays 34,600 microAlgos of new MBR without checking it can afford to --- the guard belongs in front of those writes, in the form Chapter 5's corrected guestbook uses.

`FixedArray[UInt64, typing.Literal[4]]` puts the length in the type, which makes the whole thing a fixed-size type: `size_of` works on it, `zero_bytes` works on it, and, decisively, it makes a **`BoxMap` key of a fixed name length**. Every box in the map is named by the same number of bytes, so every box in the map costs the same, and you can price the map before you build it --- exactly the property the schedule map gets from its 34-byte names.

The two commented lines cash that claim: the same array goes into a `Box` as a value on one line and names a `BoxMap` entry on the next. `.full(...)` builds one with every slot set, and `.copy()` is required going into the box for the reason Example 9-2 established; the return line reads, freezes, and indexes without any `.copy()` ceremony, because a frozen value aliases safely.

A dynamic `Array` can be a box *value*: boxes are perfectly happy with length-prefixed data, and a box you `resize` is the natural home for one. It can also be a `BoxMap` key, since `BoxMap(Array[UInt64], UInt64, key_prefix=b"b")` compiles without a word of complaint, and that is a trap the compiler will not spring for you. A dynamic key encodes to a different number of bytes for every entry, so every box in the map has a different name length, so `2,500 + 400 × (name + data)` is a different number for every box; you can no longer price the map, only one entry of it. It also puts the map back in the variable-length-key family Chapter 5's collision gotcha warned about. "Fixed is better" is not a matter of taste here: a fixed-size array is the one you can *name a box with* and still know what the map costs, and a dynamic one is the one you should only *fill a box with*.

Table 9-3 settles the choice. The *Assignment* column decides whether your code compiles; the *Can it be stored* column decides whether the value can leave the transaction at all.

: Table 9-3. The four array types you choose between, and how to tell them apart

| Type | Assignment | Mutable | Can it be stored | Reach for it when |
|--------------------|------------------------|---------|----------------------|------------------------|
| `Array` | `.copy()` required | yes | value; key priced per entry | building a variable-length value locally |
| `FixedArray` | `.copy()` required | yes | value **or** fixed-price key | the length is known and the value must be sizeable |
| `ImmutableArray` | aliases safely (no `.copy()`) | no | value; key priced per entry | a built value that must not change afterwards |
| `ReferenceArray` | aliases | yes | **no** | passing a large working array to subroutines |
`FixedArray` is the only row that can name a box at a fixed price, because its length is in its type, and `ReferenceArray` is the only row that cannot be stored at all; `ImmutableFixedArray` is `FixedArray`'s frozen counterpart, and `FixedArray.freeze()` is how you get one. The remaining two rows differ only in whether the value can change after it is built, which is the assignment column stated a second way, since a value that cannot change is safe to alias.

The schedule struct is what the three decisions look like settled: fixed-width fields for a flat encoding, a fixed-length name for a priceable map, and value semantics that demand `.copy()` at every read-modify-write. Chapter 17's farm makes the same three decisions about its staker records, and inherits them from here instead of remaking them.

The method below is where Example 3-6 stops being a rule and starts
being four lines of code in a row. Every argument `calculate_vested` receives is
a field read out of a box and converted on the way in; the result comes back
native, gets compared and subtracted natively, and is re-encoded only when it
goes back into the box. Convert at the edge, compute in the middle.

::: {.note}
**Quick reference: converting between ARC-4 and native types.** When you read `schedule.total_amount`, you get an `arc4.UInt64`. To do math with it, convert: `total = schedule.total_amount.as_uint64()`. To write it back: `schedule.total_amount = arc4.UInt64(new_value)`. For booleans: `schedule.is_revoked.native` yields a Python `bool`. Use `.as_uint64()` and `.as_biguint()` on the numeric ARC-4 types, where `.native` is deprecated (see the `@deprecated` annotations in the [PuyaPy `arc4` stubs](https://github.com/algorandfoundation/puya/blob/main/stubs/algopy-stubs/arc4.pyi)); use `.native` for `String`, `Bool`, `Address`, and `DynamicBytes`, where it remains the standard conversion.
:::

Add the event from Example 8-16 at module level (beside the `VestingSchedule` struct), then the method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
class Claimed(arc4.Struct):
    """ARC-28 event: who was paid, and how much (Example 8-16's device)."""

    beneficiary: arc4.Address
    amount: arc4.UInt64
```

The struct is the event's shape; `claim` is its only emitter:

```python
    @arc4.abimethod
    def claim(self) -> UInt64:
        """Beneficiary claims their vested tokens."""
        beneficiary = Txn.sender
        assert beneficiary in self.schedules, "No vesting schedule"

        # .copy() -- the value-semantics rule from Example 9-2.
        schedule = self.schedules[beneficiary].copy()

        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )

        claimable = vested - schedule.claimed_amount.as_uint64()
        assert claimable > UInt64(0), "Nothing to claim"

        # Send tokens to the beneficiary
        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=beneficiary,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        # Record the claim
        schedule.claimed_amount = arc4.UInt64(
            schedule.claimed_amount.as_uint64() + claimable
        )
        self.schedules[beneficiary] = schedule.copy()

        arc4.emit(Claimed(arc4.Address(beneficiary), arc4.UInt64(claimable)))
        return claimable
```

Two prerequisites sit with the beneficiary before any of this can run.

::: {.setup}
**Beneficiary prerequisites.** Before calling `claim`, the beneficiary must (1) have a funded account (at least 0.2 Algo for the base MBR plus ASA opt-in MBR), and (2) have opted into the vesting ASA (a zero-amount self-transfer of the asset). Without the opt-in, the inner `AssetTransfer` fails with `receiver error: must optin, asset <id> missing from <address>`, surfaced through the AVM's inner-transaction wrapper as `inner tx 0 failed: receiver error: must optin, ...`. The `receiver error:` prefix is the part that matters: the same `asset <id> missing from <address>` tail appears without it when the *sender* is the one not opted in, and the two send you to different accounts. In a production system, you might add an `opt_in_beneficiary` method that handles this in one atomic group, but for this contract the beneficiary manages it themselves.
:::

Two details in this method are settled by earlier chapters rather than by
anything local. The inner transfer carries `fee=UInt64(0)`, which is
Example 7-4: the caller's fee covers it through pooling, so the
application account never quietly drains itself paying for its own outbound
transactions. And the transfer goes out *before* `claimed_amount` is updated,
which on Ethereum would be the textbook reentrancy bug and here is
Example 8-7: nothing on the receiving side gets control back, so the
ordering is a readability choice and not a security one.

The failure mode that does bite is the recipient's, not the contract's.
Example 7-19 is the shape of it: a beneficiary who has never opted
into the grant asset cannot receive it, and the inner transfer takes the whole
call down with it.

The claim path is written; prove it answers before moving on. Append two probes
to `test_initialize.py`. The first needs nothing you have not already scripted
--- the admin has no schedule, so the box lookup fails and the refusal names it:

```console
>>> app_client.send.call(
...     algokit_utils.AppClientMethodCallParams(method="claim"))
LogicError: Txn ACDG...MBLQ had error 'Runtime error when executing
TokenVesting (appId: 2703) in transaction 0: No vesting schedule'
at PC 601
    ... 10 lines of TEAL trace ...
```

For the second probe, run the deposit group and the `create_schedule` call from
the previous two sections for a fresh Alice account whose cliff is a day away
(`cliff_duration=86_400`), then have Alice call `claim`. The box exists this
time, so the call gets past the first guard and the curve returns zero:

```console
>>> app_client.get_global_state()["available_tokens"].value
999000000
>>> app_client.send.call(algokit_utils.AppClientMethodCallParams(
...     method="claim", sender=alice.address,
...     static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
...     asset_references=[token_id],
...     box_references=[b"v_" + decode_address(alice.address)]))
LogicError: Txn PRVD...GU4A had error 'Runtime error when executing
TokenVesting (appId: 2703) in transaction 0: Nothing to claim'
at PC 635
    ... 10 lines of TEAL trace ...
>>> app_client.get_global_state()["available_tokens"].value
999000000
```

Two different refusals from two different guards, at two different program
counters:

- [ ] An account with no schedule is refused for not having one, by name
- [ ] A beneficiary before her cliff is refused for having nothing vested, by name
- [ ] Neither refusal moved a token, and `available_tokens` still reconciles: one
      billion deposited, one million reserved against Alice's schedule, and the
      same 999,000,000 before and after both refusals

A vesting contract spends most of its life saying no correctly; you have just
watched it do the two saying-noes that guard everything the remaining methods add.

## Revoking Unvested Tokens

If a team member leaves, the admin reclaims the unvested portion. Already-vested tokens remain claimable. The revoke method uses [inner transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/) to return the unvested tokens to the admin.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def revoke(self, beneficiary: Account) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert beneficiary in self.schedules, "No schedule"

        schedule = self.schedules[beneficiary].copy()
        assert not schedule.is_revoked.native, "Already revoked"

        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        unvested = schedule.total_amount.as_uint64() - vested

        schedule.is_revoked = arc4.Bool(True)
        schedule.total_amount = arc4.UInt64(vested)
        schedule.cliff_end = arc4.UInt64(now)
        schedule.vesting_end = arc4.UInt64(now)
        self.schedules[beneficiary] = schedule.copy()

        if unvested > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=Account(self.admin.value),
                asset_amount=unvested,
                fee=UInt64(0),
            ).submit()

        return unvested
```

After revocation, the schedule's `total_amount` becomes the amount that had
vested at the revocation timestamp. Setting `cliff_end` and `vesting_end`
to that same timestamp makes a later `claim` treat the capped amount as fully
vested. Without that freeze, `claim` would apply the original vesting curve to
the already-capped amount and underpay the beneficiary.

Prove the split before moving on. Recompile, then give a second beneficiary a
schedule short enough to watch --- Bob, one million units, a two-second cliff
and twenty seconds of vesting --- let a few seconds pass, and revoke him a
quarter of the way through:

```console
>>> def bob_claimable():   # the query a wallet polls before it offers a claim
...     return app_client.send.call(
...         algokit_utils.AppClientMethodCallParams(
...             method="get_claimable", args=[bob.address],
...             account_references=[bob.address],
...             box_references=[b"v_" + decode_address(bob.address)])
...     ).abi_return
...
>>> def holding(who):      # that account's balance of the grant asset
...     return algorand.asset.get_account_information(
...         who, token_id).balance
...
>>> bob_claimable()               # 5 of 20 seconds elapsed
250000
>>> app_client.send.call(algokit_utils.AppClientMethodCallParams(
...     method="revoke", args=[bob.address],
...     static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
...     asset_references=[token_id],
...     account_references=[bob.address],
...     box_references=[b"v_" + decode_address(bob.address)])).abi_return
750000
>>> holding(admin.address)        # 9,000,000,000 before the call
9000750000
>>> bob_claimable()               # frozen, not still ramping
250000
```

One call moved the unvested 750,000 back to the admin and left the vested
250,000 where Bob can still reach it. The second `bob_claimable()` is the freeze
working: twenty seconds later it would still say 250,000, because `revoke` set
`cliff_end` and `vesting_end` to the revocation second.

Bob's claim then goes through the same query, because a claim of zero is a
refusal and a wallet should not send one:

```console
>>> claimable = bob_claimable()
>>> if claimable:
...     app_client.send.call(algokit_utils.AppClientMethodCallParams(
...         method="claim", sender=bob.address,
...         static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
...         asset_references=[token_id],
...         box_references=[b"v_" + decode_address(bob.address)]
...     )).abi_return
...
250000
>>> holding(bob.address)
250000
>>> bob_claimable()
0
```

- [ ] The revocation split the grant and lost nothing: 250,000 claimed plus
      750,000 returned is the whole 1,000,000
- [ ] The unvested remainder reached the admin's holding, not the contract's
- [ ] `get_claimable` answered before the claim, and answered zero after it ---
      which is exactly the answer that tells a wallet not to send one


## Cleaning Up Completed Schedules

After a beneficiary has claimed everything, their box consumes storage and locks MBR. Cleaning up deletes the box and refunds the freed MBR.

::: {.gotcha #boxes-outlive-a-deleted-app topic="Box storage" title="Deleting an application does not delete its boxes, and the MBR is gone"}
Delete an application while it still owns boxes and those boxes stay in the ledger with their MBR locked permanently: there is no application left to call `box_del`, and no protocol path that reclaims it. A contract that creates boxes therefore needs a *reachable* delete path --- either it refuses `DeleteApplication`, as a contract holding other people's assets should, or it asserts that no boxes remain before allowing deletion.
:::

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def cleanup_schedule(self, beneficiary: Account) -> None:
        assert beneficiary in self.schedules, "No schedule"

        schedule = self.schedules[beneficiary].copy()
        claimed = schedule.claimed_amount.as_uint64()
        assert claimed >= schedule.total_amount.as_uint64()

        del self.schedules[beneficiary]
        self.beneficiary_count.value -= UInt64(1)

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(41))
        itxn.Payment(
            receiver=Account(self.admin.value),
            amount=box_mbr,
            fee=UInt64(0),
        ).submit()
```

`cleanup_schedule` has no admin check; it is deliberately permissionless. Anyone may trigger it once a schedule is fully claimed, and the MBR refund always goes to the admin (who funded it) regardless of who calls the method.

Always clean up boxes before deleting an app. (See [Storage Overview](https://dev.algorand.co/concepts/smart-contracts/storage/overview/) for box lifecycle details.)


## Querying Vesting Status

Read-only methods let beneficiaries check their status without paying fees.

Add these methods to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod(readonly=True)
    def get_vesting_info(self, beneficiary: Account) -> VestingSchedule:
        assert beneficiary in self.schedules, "No schedule"
        return self.schedules[beneficiary].copy()

    @arc4.abimethod(readonly=True)
    def get_claimable(self, beneficiary: Account) -> UInt64:
        assert beneficiary in self.schedules, "No schedule"
        schedule = self.schedules[beneficiary].copy()
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        return vested - schedule.claimed_amount.as_uint64()
```

`calculate_vested` now serves three callers. Without it, the vesting math would be duplicated three times in compiled TEAL, spending the 2,048-byte program page three times faster for no benefit. (See [Algorand Python structure guide](https://algorandfoundation.github.io/puya/language-guide/structure/) for subroutine usage.)


## Testing the Vesting Contract

One piece of housekeeping stands between you and the first test run.

::: {.note}
Check whether `pytest` and `algorand-python-testing` are already listed in the generated `pyproject.toml`, add whichever is missing, and create a `tests/` directory in your project root. Run pytest from the project environment created by `algokit project bootstrap all` rather than installing it into an unrelated system Python. (See [Testing](https://dev.algorand.co/algokit/utils/python/testing/) for AlgoKit testing patterns.)
:::

Chapter 8 argued that a contract needs two test suites rather than one, and
this contract is the case that makes the argument concrete. Vesting is almost
entirely a function of the clock, and a multi-month schedule is not something you
can wait for. So the suite splits along the line Table 8-1
drew.

The fast half is Example 8-14 applied to the schedule arithmetic.
`algorand-python-testing` runs `calculate_vested` and the read-only methods as
ordinary Python against an in-memory ledger, and
`ctx.ledger.patch_global_fields(latest_timestamp=...)` moves the clock four
years in one assignment. Every test in that half runs in under a millisecond,
which is what makes it reasonable to test the cliff boundary, the floor
direction, the freeze `revoke` applies to the curve, and the overflow threshold
individually rather than picking one and hoping.

*Before reading on: of the eleven methods on this contract, some can be tested
that way and some cannot. Sort them, and say what the dividing line is.*

If you sorted them into two piles you drew the line in the wrong place. It is
not between methods. It runs through the middle of them.

The line is the AVM. `patch_global_fields` can lie about the time; it cannot
conjure an asset holding, a box minimum-balance payment, or an inner transfer
that actually leaves the application account. But almost every method here is a
sequence of assertions followed by an effect, and only the effect needs a chain.
`create_schedule`'s "Only admin" check runs happily in memory against a
synthesized group; the 32,500-microAlgo payment that same method verifies does
not. `revoke` recomputes the curve, caps the total, and freezes the schedule
entirely in Python; its refund transfer does not. So the shipped unit file tests
the authorization prefix of `create_schedule`, all of `revoke` and
`cleanup_schedule` and `reject_lifecycle`, and none of `claim`, not because
`claim`'s admin check is unreachable, but because everything interesting past it
is an inner transaction. `initialize` and `deposit_tokens` are the only two that
are AVM all the way down.

The slow suite is not "the methods you could not unit-test," it is "the last few
lines of most of them." LocalNet, real accounts, real MBR, and the
Example 8-15 pattern for every security assertion. The project
directory for this chapter ships both: `tests/test_vesting_unit.py` for the fast
half and `tests/test_token_vesting.py` for the slow one, with a `conftest.py`
that skips the slow file entirely when LocalNet is not running.

Here are the helpers the LocalNet half is built on. Every one of them is a
script you have already written in this chapter, wrapped in a function so the
tests below read as vesting rather than as transaction assembly:

```python
import os
from pathlib import Path
import algokit_utils
from algosdk.encoding import decode_address

APP_SPEC = Path(
    "smart_contracts/artifacts/token_vesting/"
    "TokenVesting.arc56.json"
).read_text()

BOX_MBR = 2_500 + 400 * (34 + 41)

def deploy_vesting(algorand, admin):
    """Deploy a fresh TokenVesting contract and
    fund it with enough Algo for MBR."""
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC,
        default_sender=admin.address,
    )
    # A bare create, because this contract's create method
    # is a bare method. factory.deploy() would hand back
    # the app this admin deployed last time, which is what
    # a deployment script wants and not what a test wants.
    # The note keeps two tests from building the same
    # create transaction twice.
    app_client, _ = factory.send.bare.create(
        params=algokit_utils.AppFactoryCreateParams(
            note=os.urandom(8)
        )
    )
    # Fund the contract: 300,000 covers base MBR +
    # ASA opt-in + inner txn fee headroom
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=admin.address,
            receiver=app_client.app_address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(300_000)
            ),
        )
    )
    return app_client

def create_test_asa(algorand, admin, total):
    """Create the ASA this contract will vest.
    The admin holds all of it."""
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=admin.address,
            total=total,
            decimals=6,
            asset_name="TestVestingToken",
            unit_name="TVT",
            # Two tests creating the same ASA from the same
            # admin build the same transaction twice, and
            # the second is refused as already in the ledger.
            note=os.urandom(8),
        )
    )
    return result.asset_id

def deposit_tokens(algorand, admin, vesting, token_id, amount):
    """Group the transfer with the call, which is what
    the method asserts."""
    transfer = algorand.create_transaction.asset_transfer(
        algokit_utils.AssetTransferParams(
            sender=admin.address,
            receiver=vesting.app_address,
            asset_id=token_id,
            amount=amount,
        )
    )
    return vesting.send.call(
        algokit_utils.AppClientMethodCallParams(
            method="deposit_tokens",
            args=[transfer],
            asset_references=[token_id],
        )
    ).abi_return

def create_schedule(algorand, admin, vesting, beneficiary,
                    total, cliff_duration, vesting_duration):
    """Pay the box MBR and create the schedule,
    in one group of two."""
    mbr_txn = algorand.create_transaction.payment(
        algokit_utils.PaymentParams(
            sender=admin.address,
            receiver=vesting.app_address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(BOX_MBR)
            ),
        )
    )
    vesting.send.call(
        algokit_utils.AppClientMethodCallParams(
            method="create_schedule",
            args=[beneficiary, total, cliff_duration,
                  vesting_duration, mbr_txn],
            account_references=[beneficiary],
            box_references=[
                b"v_" + decode_address(beneficiary)
            ],
        )
    )

def get_claimable(vesting, beneficiary):
    """What a wallet polls. Readonly, and it still has to
    name the box."""
    return vesting.send.call(
        algokit_utils.AppClientMethodCallParams(
            method="get_claimable",
            args=[beneficiary],
            account_references=[beneficiary],
            box_references=[
                b"v_" + decode_address(beneficiary)
            ],
        )
    ).abi_return
```

`deposit_tokens` and `create_schedule` are the two that build groups, and both
are places where Example 7-10's assertion and the helper's construction have to
agree: pass the funding transaction as the last argument and the client groups
it immediately before the call, which is the shape the contract asserts. Get
that wrong and the test fails for a reason that has nothing to do with vesting.

::: {.tryit}
**Exercise.** Add a `revoke_schedule` helper in the same register, then use it
to write the case the LocalNet half is missing: a beneficiary revoked *before*
the cliff, who can claim nothing afterwards and is cleaned up anyway. Its
references are not `claim`'s. `revoke` names a box by its argument where `claim`
names one by its sender, and one of the two calls needs no asset reference at
all. Say which, and why, before you run it.
:::

Two LocalNet behaviors affect how you write your test helpers.

::: {.gotcha #localnet-time-needs-blocks topic="Testing and simulation" title="time.sleep() does not advance LocalNet's block timestamp"}
On LocalNet, block timestamps only advance when new blocks are
produced, and blocks are produced on demand when transactions are submitted.
Calling `time.sleep(N)` alone does NOT advance the block timestamp. You must
also submit a transaction, even a zero-amount self-payment, to produce a block
with the updated timestamp. A typical `advance_time` helper sleeps for the
desired duration, then sends a dummy transaction to trigger a new block:

```python
import time

def advance_time(algorand, seconds):
    """Sleep, then send a dummy txn to produce a block."""
    time.sleep(seconds)
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=dispenser.address,
            receiver=dispenser.address,
            amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        )
    )
```

For testing, use short durations for cliff and vesting periods. For example,
set a cliff of 8 seconds and total vesting of 30 seconds instead of 90 days
and 365 days.
:::

The sleep-then-block version above is enough on a fresh LocalNet, and it is
the shape to remember. The helper the project ships adds one discipline on
top: after producing the block it reads the ledger clock back and keeps
sealing blocks until the clock has actually reached the target, raising if
it never does. That guard costs nothing on your machine and is what lets the
suite survive a shared or long-lived node whose clock another test suite has
already moved. Chapter 17 returns to this and names the full set of clock
rules.

A second LocalNet quirk affects rapid-fire test transactions.

::: {.gotcha #duplicate-txid-in-tests topic="Testing and simulation" title="Identical app calls in quick succession collide as duplicate transaction IDs"}
Sending identical app calls in rapid succession on LocalNet can
produce identical transaction IDs, causing `transaction already in ledger`
errors. Add a unique `note` field to each transaction, such as
`note=os.urandom(8)` or `note=f"test-{i}".encode()`. In practice, add
`note=os.urandom(8)` to every `AppClientMethodCallParams` and
`PaymentParams`/`AssetTransferParams` in your test helpers; it costs nothing
and prevents intermittent test failures.
:::

These three belong in `tests/test_token_vesting.py`, beside the helper
functions shown earlier (not part of the contract code):

```python
import os
import pytest
import algokit_utils

# Wraps the v4 send.call pattern for concise test code. Methods that emit
# inner transactions (claim, revoke, cleanup_schedule) need a static_fee of
# 2,000 so the outer transaction's fee covers the inner one by pooling; the
# note is what tells two otherwise identical calls apart.
FEE_FOR_ONE_INNER = algokit_utils.AlgoAmount.from_micro_algo(2_000)

def call_method(app_client, method, args, sender=None, static_fee=None):
    return app_client.send.call(
        algokit_utils.AppClientMethodCallParams(
            method=method, args=args, sender=sender,
            static_fee=static_fee, note=os.urandom(8),
        )
    )

def onboard_beneficiary(algorand, admin, beneficiary, token_id):
    """Fund a beneficiary and opt them into the grant asset.
    Nothing can be paid to an account that has not opted in."""
    algorand.send.payment(algokit_utils.PaymentParams(
        sender=admin.address, receiver=beneficiary.address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(500_000),
        note=os.urandom(8),
    ))
    algorand.send.asset_transfer(algokit_utils.AssetTransferParams(
        sender=beneficiary.address, receiver=beneficiary.address,
        asset_id=token_id, amount=0,
    ))

class TestTokenVesting:
    def test_full_lifecycle(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        onboard_beneficiary(algorand, admin, beneficiary, token_id)

        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id],
                    static_fee=FEE_FOR_ONE_INNER)
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)

        # Use short durations for LocalNet testing (seconds, not months).
        # Production contracts would use cliff_duration=90*86400,
        # vesting_duration=365*86400.
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        assert get_claimable(vesting, beneficiary.address) == 0
        advance_time(algorand, 10)  # Past cliff
        claimable = get_claimable(vesting, beneficiary.address)
        assert 0 < claimable < 1_000_000_000

        call_method(vesting, "claim", [], sender=beneficiary.address,
                    static_fee=FEE_FOR_ONE_INNER)
        advance_time(algorand, 30)  # Past full vesting
        call_method(vesting, "claim", [], sender=beneficiary.address,
                    static_fee=FEE_FOR_ONE_INNER)
        call_method(vesting, "cleanup_schedule", [beneficiary.address],
                    static_fee=FEE_FOR_ONE_INNER)

    def test_revocation_returns_unvested(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        onboard_beneficiary(algorand, admin, beneficiary, token_id)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id],
                    static_fee=FEE_FOR_ONE_INNER)
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        # A long vesting window, so that blocks produced by anything else
        # sharing this LocalNet cannot finish the schedule mid-test.
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=300)

        advance_time(algorand, 15)  # Past cliff, mid-vesting
        unvested = call_method(vesting, "revoke", [beneficiary.address],
                               static_fee=FEE_FOR_ONE_INNER)
        assert unvested.abi_return > 0
        claimed = call_method(vesting, "claim", [],
                              sender=beneficiary.address,
                              static_fee=FEE_FOR_ONE_INNER)
        assert claimed.abi_return > 0
        assert claimed.abi_return + unvested.abi_return == 1_000_000_000

    def test_double_claim_fails(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        onboard_beneficiary(algorand, admin, beneficiary, token_id)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id],
                    static_fee=FEE_FOR_ONE_INNER)
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        # Past full vesting, deliberately: mid-schedule a second claim
        # succeeds, because submitting the first one produced a block and a
        # second of vesting with it. Only an exhausted schedule refuses.
        advance_time(algorand, 35)
        call_method(vesting, "claim", [], sender=beneficiary.address,
                    static_fee=FEE_FOR_ONE_INNER)
        with pytest.raises(Exception, match="Nothing to claim"):
            call_method(vesting, "claim", [], sender=beneficiary.address,
                        static_fee=FEE_FOR_ONE_INNER)
```

The suite so far submits everything it tests; some of what belongs in it should never be submitted.

::: {.tip}
Use the `simulate` endpoint for debugging and security testing, not just read-only queries. Simulate executes the full transaction logic without committing state changes or charging fees, which is ideal for diagnosing failures and verifying security checks.
:::

This is a client-side script illustrating the simulate pattern (not part of the contract code). It is Example 8-15 pointed at this contract, and the shape is the one that chapter insisted on: a failing simulate *raises*, so the assertion is on the exception, not on a field of a returned object.

```python
import algokit_utils
from algokit_utils.errors import LogicError

# Build a transaction you expect to fail: a claim from an account that
# has no schedule. The attacker needs enough Algo to pay its own fee --
# simulate still charges it, and an unfunded sender fails with
# `overspend` before the approval program runs, which is not the
# failure under test.
attacker = algorand.account.random()
algorand.send.payment(algokit_utils.PaymentParams(
    sender=admin.address, receiver=attacker.address,
    amount=algokit_utils.AlgoAmount.from_micro_algo(200_000),
))

group = algorand.new_group().add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="claim",
            sender=attacker.address,
        )
    )
)

try:
    group.simulate()
    raise AssertionError("the contract accepted a claim with no schedule")
except LogicError as err:
    # `message` wraps the assert string rather than equalling it,
    # so match on containment.
    assert "No vesting schedule" in err.message
```

The probe generalizes to every assertion in the contract.

::: {.tip}
Use this pattern to verify every security invariant: construct the attack, simulate it, and confirm both that it raises *and* which assertion caught it. A negative test that only checks "something went wrong" passes when the contract fails for the wrong reason.
:::


## Consolidated Imports

The complete set of imports needed at the top of `smart_contracts/token_vesting/contract.py`:

```python
from algopy import (
    ARC4Contract, Account, Asset, BoxMap, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, itxn, op, subroutine,
)
```

## Summary

With one exception --- the array-and-encoding decisions Chapter 5 deferred here by name --- this chapter introduced no mechanism you had not already met. It asked you to
hold eight of them at once and let them constrain each other, which is a
different skill from learning any one of them. Having built it, you should be
able to:

- Fix a state schema before you know every method, and say what that option cost
- Choose between global state and a box on the shape of the obligation rather than the size of the data
- Recognize when a payout path needs an opt-in that happened in a different transaction, days earlier
- Price a box, a payment, and an opt-in against one application account's balance without deploying to find out
- Carry an overflow argument through three call sites and one subroutine, and say which line actually enforces it
- Read a group of two as one thing that either happens or does not
- Say why an ordering that would be a reentrancy bug elsewhere is only a readability choice here

Table 9-4 summarizes the build sequence and the mechanisms each step puts into play.

: Table 9-4. Build sequence and the mechanisms each step puts into play

| Step | Feature | Mechanisms in Play |
|------|---------|--------------------|
| 1 | Deploy and admin | Contract structure, ARC4Contract, __init__, GlobalState, ABI methods, ARC-56, contract addresses, schema immutability |
| 2 | Immutability | OnCompletion actions, bare methods, trust model |
| 3 | Token opt-in | ASAs, inner transactions, MBR, fee pooling, resource references |
| 4 | Deposit tokens | Atomic groups, typed gtxn parameters, verifying asset/receiver/amount |
| 5 | Vesting schedules | Local state's ClearState trapdoor, box storage, BoxMap, arc4.Struct, timestamps, I/O budget |
| 6 | Claim tokens | Integer math, overflow, wide arithmetic, rounding, subroutines, reentrancy safety |
| 7 | Revocation | Authorization, design patterns for capping allocations |
| 8 | Cleanup | Box lifecycle, MBR refunds |
| 9 | Read-only queries | Subroutine reuse, program size budgeting |

One deliberate convention break runs through the chapter and is argued where it starts: the client-style note before the first deployment script is why every teaching script here is hand-assembled through the generic client while the project's suite drives the same flows through the typed one.

The vesting contract works, and it cannot yet say two things a production system must: who exactly is calling it, and what everything it does costs. Chapters 10 and 11 supply both --- deliberately, back to back --- and Chapter 12 then spends them, extending this contract so a vesting position becomes a thing a wallet can hold and a marketplace can transfer.

## Exercises

1. **(Understand)** Without rereading the contract, list every account whose minimum balance this system raises, and what each raise bought. There are four answers and one of them is not the application account. Then say which of the four is refundable and by whose call.

2. **(Apply)** Modify the vesting contract to support a second cliff: tokens vest 25% immediately at the first cliff (3 months), then the remaining 75% linearly from 3 to 12 months. What changes to `calculate_vested` are needed?

3. **(Apply)** Add a `pause` method that prevents all claims until unpaused, callable only by admin. What state field do you add, and which methods need to check it? Example 4-7 makes this exercise unimplementable on an already-deployed contract, so say what you would have had to do at creation time to keep the option open.

4. **(Analyze)** The `cleanup_schedule` method sends the freed MBR to the admin, not the beneficiary. Argue both sides: should the MBR refund go to the admin (who funded it) or the beneficiary (whose data it stored)? What are the security implications of each choice?

5. **(Evaluate)** Replace the `op.divmodw` pair in `calculate_vested` with a single `op.divw(high, low, duration)`, deleting the `assert q_hi == 0` line the swap absorbs. Run `tests/test_vesting_unit.py` against both versions: all twenty-one pass either way. The chapter has already told you why; the assert is unreachable on this contract's control flow. So the tests cannot decide this for you. Decide it on the argument instead. Write down the chain of facts that makes the assert unreachable, then say which link a future maintainer is most likely to break without noticing, and which of the two versions still refuses to pay out a wrong number afterwards. Then answer the question that generalizes: when the tests agree, what is left to choose on?

6. **(Create)** Design an extension where the admin can increase a beneficiary's total allocation after the schedule is already created. What new method is needed? What happens to already-vested tokens? What security checks prevent abuse?

7. **(Create, cross-chapter)** The vesting contract uses a single admin address. Design a modification where admin operations (`initialize`, `create_schedule`, `revoke`) require approval from 2-of-3 multisig signers. What changes to the admin check pattern are needed? How does Algorand's native multisig support simplify this compared to implementing multisig logic in the contract itself?

::: {.tryit}
**Practice.** Look up a contract with `__init__`, wide arithmetic, a `BoxMap`, an Algo payment, and a creator check in Appendix D, which indexes every numbered example in the book by the task it performs.
:::

## Further Reading

- [Algorand Python Program Structure](https://algorandfoundation.github.io/puya/language-guide/structure/) --- program structure, decorators, `__init__` semantics
- [Types](https://algorandfoundation.github.io/puya/language-guide/types/) --- UInt64, Bytes, BigUInt, ARC-4 types
- [Storage](https://algorandfoundation.github.io/puya/language-guide/storage/) --- GlobalState, LocalState, Box, BoxMap
- [Transactions](https://dev.algorand.co/algokit/languages/python/lg-transactions/) --- gtxn parameters, inner transactions
- [ARC-4 in Python](https://algorandfoundation.github.io/puya/language-guide/arc4/) --- abimethod, baremethod, ARC4Contract
- [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/) --- MBR formula, I/O budget, lifecycle
- [App Client](https://dev.algorand.co/algokit/utils/python/app-client/) --- deployment, method calls, simulation
- [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) --- program size, opcode budget, stack limits
- [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/) --- the rekey_to field and its security implications
- [AVM Opcodes](https://dev.algorand.co/reference/algorand-teal/opcodes/) --- mulw, divmodw, bsqrt, and all other opcodes

## Before You Continue

You should be able to check off all five of these:

- [ ] I can name every account this contract's MBR is charged to, and what each charge bought
- [ ] I can say which of this contract's eleven methods can be tested without an AVM, and where the line runs
- [ ] I can trace one claim from the app call through the box read, the arithmetic, and the inner transfer
- [ ] I can explain why a schedule lives in a box rather than in the beneficiary's local state
- [ ] I can point at the single line that keeps `calculate_vested` from returning a wrong number, and say what makes it currently unreachable

If any of these are unclear, revisit the relevant section before proceeding.
