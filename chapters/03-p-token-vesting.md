\newpage

# A Token Vesting Contract

A startup has raised funds and needs to distribute tokens to its team. The tokens should not arrive all at once --- team members receive their allocation gradually over 12 months, with nothing released during the first 3 months (the "cliff"). If someone leaves early, the company can revoke their unvested tokens. This is a **token vesting contract**, and it is the first thing in this book that needs every foundational mechanism at once.

{{ch:testing}} ended with a single-beneficiary version of this contract: deployed, funded, demonstrably paying out, and wrong in three ways no compiler catches --- a claim that returned zero instead of refusing, an overflow that only fires at a supply nobody had tested, and an assertion with nothing to say when it failed. You found all three and fixed them. What that contract still cannot do is vest to more than one person, price the storage for doing so, or take anything back when somebody leaves. That is this chapter.

We will build it one capability at a time. Each section adds a feature and says where the mechanism it needs came from. Almost nothing here is new: the concept chapters of {{part:foundations}} were written to make this one an assembly rather than an introduction, and the sections below are mostly a matter of putting pieces you already have in the order that makes a working contract.

## Run It First

The finished project for this chapter is in `projects/chapter3/token-vesting/`.
Running it before you study any one piece shows the whole loop: deploy and fund
the app, create vesting schedules in boxes, then exercise the claim, revoke, and
cleanup workflows against a test Algorand Standard Asset (ASA). Before running
it, predict why each schedule needs its own box MBR payment, what Bob's
revocation should return to the admin, and why cleanup is a separate step after
claims and revocation.

```bash
cd projects/chapter3/token-vesting
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_token_vesting
algokit project run test
```

{{tbl:vesting-run-it-first}} lists the output checkpoints to compare against the
workflow output.

Table: Output checkpoints for the token vesting workflow {#tbl:vesting-run-it-first}

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| App ID and app address | The app account is the party that will custody the vested ASA |
| Asset ID | The workflow creates its own test ASA, then the app opts into it during initialization |
| Deposit confirmation | The ASA transfer is a grouped argument to `deposit_tokens`, so tokens and accounting move together or not at all |
| Two schedule boxes created | Each `create_schedule` call carries an exact 32,500 microAlgo MBR payment and a `box_references` entry naming `v_` followed by the beneficiary's address |
| Alice's partial claim | Past the cliff but short of full vesting, the linear formula releases a fraction |
| Bob's revocation | Vested tokens settle to Bob and the unvested remainder returns to the admin, in one call |
| Bob's post-revoke claim, only when positive | The workflow reads `get_claimable` first, because the contract rejects a zero-amount claim |
| Cleanup refunds the MBR | Deleting an exhausted schedule box returns the 32,500 microAlgos that funded it |
| Test suite passes | The suite reruns each of those paths, including the failure cases, against LocalNet |

Without Docker or Podman, `algokit project run test-static` still compiles the
contract, generates the typed client, and runs the source-shape guards for
grouped transactions, wide arithmetic, and inner-transaction fee patterns.
Treat `projects/chapter3/token-vesting/` as the reference implementation; when
you are ready to build the contract yourself, work through the setup steps that
follow in a fresh project.


## What You Need First

Every concept chapter in {{part:foundations}} ended with a Handoff table naming
the examples this project would lean on. {{tbl:vesting-what-you-need-first}} is
the other side of those seven tables, collected in one place.

It is not a reading list to finish before you start. The sections below are
written to be read in order and each one says where its ingredients came from.
This table is for two other moments: now, to see what the contract is made of
before any of it is in front of you, and later, when a line assumes something
you would rather look up than reconstruct. Each reference in the first column
carries its chapter in the number: {{ex:two-clocks}} lives in
{{ch:numbers-and-time}}, {{ex:validate-at-boundary}} in {{ch:testing}}.

Answer the predict column before you follow the link. A prediction you have
committed to is worth more than one you were about to make, including --- and
especially --- when it turns out wrong.

Table: What {{part:foundations}} built that this project assumes {#tbl:vesting-what-you-need-first}

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| {{ex:smallest-contract}} | The `TokenVesting` class and its `create` method | What does subclassing `ARC4Contract` generate that you would otherwise write by hand? |
| {{ex:reference-types}} | `beneficiary: Account` on `revoke`, `vesting_asset: Asset` on `initialize` | The contract receives an `Account`. What does it actually receive, and what must the transaction declare? |
| {{ex:assert-message}} | The admin, cliff and amount guards --- and seven asserts that carry no message at all | A beneficiary claims before the cliff. What should the failure tell them, and where will that sentence be stored? |
| {{ex:without-arc4contract}} | `reject_lifecycle`, which refuses updates and deletes | Which on-completion actions must a contract holding other people's tokens refuse, and why? |
| {{ex:typed-call}} | Every deployment and interaction script below | `claim` returns a number. By what mechanism does it reach your Python? |
| {{ex:create-modes}} | `create`, which captures the admin exactly once | Configuration happens once. Which `create` value makes that the router's job rather than a flag you maintain? |
| {{ex:arc4-boundary}} | Every read of a `VestingSchedule` field before arithmetic | How many conversions belong in a method that does arithmetic on two numeric arguments, and where do they go? |
| {{ex:readonly-method}} | `get_claimable`, which a wallet polls before showing a claim button | A wallet polls this many times a second. What must the method avoid doing for those calls to cost nothing? |
| {{ex:tuple-return}} | `get_vesting_info`, which returns a whole schedule in one call | Six fields, one call. What return type hands a generated client six named values rather than a blob? |
| {{ex:allow-actions}} | The two actions `reject_lifecycle` claims in order to refuse them | It holds assets it owes to people. Which two on-completion actions must it never accept, and how do you say so? |
| {{ex:state-schema-fixed}} | The five globals declared in `__init__`, four of them for methods still forty pages away | How many slots does a contract reserve when the number of beneficiaries is not known at creation? |
| {{ex:clear-state-drops-local}} | The decision to put schedules in boxes rather than local state | A vesting schedule is an obligation the contract owes a beneficiary. Where can it not live? |
| {{ex:struct-arc4}} | `VestingSchedule`, six fields in one 41-byte record | Six numbers, one record. How many state slots should that cost? |
| {{ex:global-get-default}} | `available_tokens` and `beneficiary_count`, read before anything has ever written them | Two counters, declared at creation and first read in a method that may run before the method that increments them. What comes back? |
| {{ex:init-defaults}} | `self.admin.value = Txn.sender.bytes`, in `create` and nowhere else | Which of `Txn.sender` and `Global.creator_address` is safe to store as the admin, and why are they the same value exactly once? |
| {{ex:boxmap-declare}} | `self.schedules`, one box per beneficiary, keyed by address | Why can a vesting schedule not live in the beneficiary's local state? |
| {{ex:box-mbr-math}} | The 32,500 microAlgo payment grouped with every `create_schedule` | A 32-byte address key, a 2-byte prefix, and a 41-byte record. What does one schedule cost? |
| {{ex:app-mbr-floor}} | Funding the application account before the first schedule exists | What does the signer see if that funding is short? |
| {{ex:box-refs-auto}} | Every client call that touches a schedule box | The method takes the beneficiary as an argument. Does that alone make the box available? |
| {{ex:boxmap-scan-cost}} | Why this contract has no "list all schedules" method | How many schedules could such a method return before it failed, and would that number be stable? |
| {{ch:boxes}}, Exercise 5 | The grouped MBR payment `create_schedule` takes as a typed argument | You wrote down what the contract must verify about that payment. Which of your checks does this one actually make? |
| {{ex:linear-vesting}} | `calculate_vested`, the release curve all three payout paths call | This project's schedules are per beneficiary. What must be stored per beneficiary that the example held in three globals? |
| {{ex:mul-div}} | The wide multiply-then-divide inside `calculate_vested` | The grant is an ASA with decimals. Which ordering survives that, and at what size does the other one abort? |
| {{ex:vesting-cliff}} | `cliff_end` and `vesting_end`, and the guard that orders them | Three parameters, three orderings to enforce. Write the assertions before you read them. |
| {{ex:two-clocks}} | `Global.latest_timestamp`, read by claim, revoke, and the status query | Which of the two globals does a schedule measured in months want, and what does choosing it cost in precision? |
| {{ex:divide-by-zero}} | `create_schedule`, which fixes a divisor for that beneficiary's whole schedule | The divisor is `vesting_end - start_time`, set once and never revisited. What does getting the guard wrong cost here? |
| {{ch:numbers-and-time}}, Exercise 3 | `revoke`, which reduces a total that has already been partly claimed | You worked out how a divisor reaches zero with no attacker involved. Which method here could drive `total - claimed` to zero the same way? |
| {{ex:grouped-asset-transfer}} | `deposit_tokens`, which takes the grant supply from the admin | This contract checks the transfer's asset, amount and destination, but authorizes on the *app call's* sender. Say why those are different accounts. |
| {{ex:asa-self-optin}} | `initialize`, which opts the application into the grant asset before any deposit | Who pays the 100,000 microAlgo, and what breaks if they pay it late? |
| {{ex:inner-payment}} | The `itxn.AssetTransfer` that ends `claim` | The payout is an asset transfer, not a payment. Which of the example's two guards still applies, and what replaces the other? |
| {{ex:inner-fee-zero}} | `fee=UInt64(0)` on every inner transaction in the contract | A claim is one app call and one inner transfer. Write the pooled-fee arithmetic before you read it. |
| {{ex:group-bounds}} | `Global.group_size == UInt64(2)` in `deposit_tokens` and `create_schedule` | The transfer arrives as a typed argument rather than by index. Say what that changes about the size check, and what it does not. |
| {{ex:balance-is-not-ledger}} | `available_tokens`, decremented whenever a schedule is created | This contract tracks unpromised supply in state rather than reading its own holding. What could an outsider do to it if it read the holding instead? |
| {{ex:optin-gate-eager}} | The payout, against a beneficiary who may never have opted in | The transfer is allowed to fail rather than being gated. Predict what the beneficiary sees, and what one line would change that. |
| {{ex:assert-message-home}} | Every rejection on the claim path | Pick the authorization check on `claim` and write the message you would put on it, then compare. |
| {{ex:validate-at-boundary}} | `deposit_tokens` and its typed transfer parameter | It asserts the transfer's asset, amount and receiver, and not its position. Say which of those the router had already guaranteed. |
| {{ex:requirement-vs-code}} | Deciding, per method, what the requirement says rather than what the draft does | Vesting has one requirement that is easy to state and easy to implement wrongly. Write it as a sentence, then write the assertion that would fail if the contract broke it. |
| {{ex:unit-test-context}} | The fast half of the test suite, over the schedule arithmetic | Which of this contract's methods can be tested with `patch_global_fields` alone, and which cannot, and why? |
| {{ex:negative-test-simulate}} | One test per security assertion, each pinned to its message | The admin-only methods each need a stranger test. What must such a test assert beyond "an exception was raised"? |
| {{ex:simulate-extra-budget}} | Sizing a group that pays several beneficiaries at once | How would you find the point at which the group needs a second app call, without deploying twice? |
| {{ex:pc-to-source-line}} | The procedure for a claim that fails on LocalNet | What do you do with a `pc` from a failed claim, in order, and where does the procedure stop working? |


## Project Setup

If you scaffolded a project while working through {{ch:setup}}, you can reuse it. Otherwise, scaffold a new one. The `--name` flag sets the project directory name; the template always creates a `hello_world/` contract directory inside it, which we rename to match the chapter:

```bash
algokit init -t python --name token-vesting
cd token-vesting
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/token_vesting
```

Your contract code goes in `smart_contracts/token_vesting/contract.py`. The build system discovers contracts by directory, so renaming the folder is all that is needed. Delete the template-generated `deploy_config.py` inside the renamed directory --- it references the old `HelloWorld` contract and is not needed for the scripts in this chapter.

## The Data Model

Before we write the contract class, we define the data structure that represents a vesting schedule. Each beneficiary's vesting terms are stored as an ARC-4 struct in box storage. We define it first because the contract's `__init__` method references it:

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

Each `arc4.UInt64` occupies 8 bytes (big-endian), `arc4.Bool` occupies 1 byte, so the struct totals 41 bytes. We will use this struct throughout the contract --- for creating schedules, tracking claims, and reading vesting status. (See [Algorand Python ARC-4 guide](https://algorandfoundation.github.io/puya/lg-arc4.html) for struct encoding details.)

Keeping all six fields in one struct, in one box, is a deliberate choice rather than a stylistic one. Recall the box MBR formula from {{ch:boxes}}: 2,500 microAlgos per box, plus 400 per byte of *name and value combined*. The per-box constant and the 32-byte beneficiary address in the name are charged once per box, not once per field --- so splitting a struct across several boxes pays for the same address several times over. {{fig:packed-box-layout}} priced that comparison in the abstract; a vesting schedule is the same comparison with a real payload attached: six fields, one name, one constant.

Notice the `arc4.UInt64` fields, which are not the plain `UInt64` the contract's `__init__` uses two sections from now. This is {{ex:arc4-boundary}}'s division showing up in a data structure for the first time: ARC-4 types are the encoded wire format, native types are what the AVM computes on, and a field read out of a box arrives encoded. Every arithmetic path in this contract therefore opens with a conversion and closes with one, and {{ex:struct-arc4}} is the reason there are six fields to convert rather than six state slots to read. The `claim` method is where you will watch it happen line by line.


## A Contract That Exists

Before we can vest tokens, we need a contract on the blockchain. Start with the least that can exist: something that can be created and that remembers who created it.

That is {{ex:smallest-contract}} with a name change, and the two things it gets for free are the two you would otherwise have to write --- {{ex:without-arc4contract}} showed what subclassing `ARC4Contract` saves you, which is the selector dispatch and the argument decoding for every method below, and {{ex:init-defaults}} showed that `__init__` runs during the creation transaction and never again. Read the class that follows as an inventory of what this contract will need to remember, because after the create transaction that inventory is fixed.

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
        # public key, which is what our Bytes-typed GlobalState expects.
        self.admin.value = Txn.sender.bytes

    @arc4.abimethod(readonly=True)
    def get_admin(self) -> arc4.Address:
        return arc4.Address.from_bytes(self.admin.value)
```

Four of those five globals are declared for sections that are still forty pages
away, and `schedules` for a method that does not exist yet. That is
{{ex:state-schema-fixed}} being paid for rather than described: the schema is
written into the create transaction, so a slot you have not thought of yet is a
slot this contract will never have. Reserving `beneficiary_count` and
`available_tokens` now costs 28,500 microAlgos each and buys the option to use
them later; declaring them later is not an option at any price.

::: {.gotcha #schema-is-immutable topic="Global and local state" title="The state schema is fixed at creation and can never be widened"}
The number of global and local slots an application declares is written into the create transaction and is immutable for the life of the contract. There is no migration, no resize, no `UpdateApplication` escape hatch --- a contract that needs a sixty-fifth global key needs a new application and a state migration you write yourself. The MBR is charged for what you *declare*, not what you use, so a slot reserved against future need costs 28,500 or 50,000 microAlgos whether you ever write to it or not. That is the price of the option, and it is usually worth paying.
:::

`available_tokens` will track deposited tokens not yet reserved against a
schedule. The `BoxMap` line is {{ex:boxmap-declare}} with this contract's
payload in it, and it creates nothing on-chain: it tells the compiler that keys
are `Account` addresses, values are `VestingSchedule` structs, and every box
name begins with `b"v_"`. Boxes appear one at a time, when `create_schedule`
writes them.

Two details in `create` are worth pausing on, and both are {{ex:init-defaults}}
being applied rather than explained. Storing `Txn.sender` establishes an
authority only because this method can run exactly once, in the create
transaction, where the sender and the creator are necessarily the same account
--- in any method that can be called twice, the same line hands the contract to
whoever called last. And `@arc4.baremethod(create="require")` is
{{ex:create-modes}}'s `"require"`: the router, not a flag you maintain, is what
guarantees the once. It is a *bare* method because there is nothing to select
on, so the router matches it on the transaction's on-completion action instead.

`readonly=True` on `get_admin` promises exactly what {{ex:readonly-method}} said
it promises and nothing more: clients may route the call through `simulate` and
get an answer with no fee and no block. It is a claim you are making to the
client, not a constraint the protocol enforces on you.

To deploy this contract, you compile it with PuyaPy and use AlgoKit. If you set up the environment as described in {{ch:mental-model}} and renamed the contract directory as shown in the Project Setup section above, your contract code should be in `smart_contracts/token_vesting/contract.py`. Compile:

```bash
algokit project run build
```

If compilation succeeds, you will see output indicating the approval and clear programs were generated. Check the `smart_contracts/artifacts/token_vesting/` directory --- you should find `TokenVesting.approval.teal`, `TokenVesting.clear.teal`, `TokenVesting.arc56.json`, and a generated typed client `token_vesting_client.py`. The subdirectory name matches the contract directory name.

If you get an error about missing imports, make sure `algorand-python` is installed (it should be if you ran `algokit project bootstrap all`). If PuyaPy reports a type error, check that your type annotations match exactly --- Algorand Python is strictly typed.

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

This returns the application's global state, the approval and clear program hashes, and other metadata. You will use this pattern throughout development to verify that state changes happen as expected.

The compilation step produces three artifacts: `TokenVesting.approval.teal` (the approval program in human-readable TEAL assembly), `TokenVesting.clear.teal` (the clear state program), and `TokenVesting.arc56.json` (the ARC-56 application specification containing method signatures, state schema, type information, and source maps for debugging). The ARC-56 spec is what clients use to construct properly formatted transactions --- it is the equivalent of an ABI JSON file in the Ethereum ecosystem.

The application account {{ex:app-account}} read from and {{ex:inner-payment}} spent out of now belongs to something you deployed. Its address is derived from the application ID and nothing else --- `SHA512_256("appID" || big_endian_8_byte(app_id))` --- so it existed as an address before it existed as an account, and nobody holds a private key for it. Everything this contract will ever custody sits there, and the code you are about to write is the only thing that can move it.

Your contract now exists on-chain. It knows who created it. It cannot do anything else yet.


## Making It Immutable

Before we add any real functionality, we lock the contract down. {{ex:allow-actions}} enumerated the five on-completion actions an application call can carry and showed how a method declares which of them it will answer to; two of the five are the ones that matter to a contract holding somebody else's tokens. `UpdateApplication` replaces the code. `DeleteApplication` removes the contract. (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/).)

If you do not explicitly handle `UpdateApplication` and `DeleteApplication`, the default behavior depends on your base class. For `ARC4Contract`, unhandled actions are rejected by default --- but relying on defaults for security-critical behavior is risky. It is better to be explicit. Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        """Make the contract immutable. No one can change or delete it."""
        assert False, "Contract is immutable"
```

This is not optional for financial contracts. Consider what happens without it: the admin deploys the vesting contract, team members see the code and trust it, and then the admin calls `UpdateApplication` to replace the vesting logic with code that sends all tokens to their own address. The contract was audited, but the audit is meaningless if the code can be changed post-deployment.

Immutability is the foundation of trustlessness. Once deployed, the rules encoded in the contract are the rules forever. Users can verify the source code, confirm it matches the deployed bytecode, and trust that it will behave consistently. This is the entire value proposition of smart contracts over traditional custodial arrangements.

There are legitimate reasons to want upgradeable contracts --- bug fixes, feature additions, regulatory compliance. If you need upgradeability during an initial stabilization period, use a multisig with a timelock and publicly commit to making the contract immutable by a specific date. But the default should always be immutability, especially for contracts that hold other people's money.


## Accepting Tokens

Our vesting contract must hold the tokens it distributes, which means holding an Algorand Standard Asset. All three of {{ch:moving-value}}'s rules for an asset a contract did not create for itself bind here: an account holds an asset only after opting in, the opt-in raises that account's minimum balance by 100,000 microAlgos for as long as the holding lasts, and a transfer to an account that has not opted in fails --- inside a group, taking every other transaction down with it. {{ex:app-mbr-floor}} is the arithmetic that decides whether this particular account can afford the opt-in it is about to attempt. (See [Assets Overview](https://dev.algorand.co/concepts/assets/overview/).)

The asset itself is chosen before this contract is deployed and not by it, and one of the four authorities {{ex:asa-roles}} priced is worth naming here as a project decision. A grant token the beneficiary is meant to own outright should have no freeze address and no clawback address, because either one means the tokens this contract pays out on schedule are tokens a third party can take back off schedule. Nothing in the code below can check that for you. A vesting contract enforcing a schedule against an asset with a live clawback address is enforcing it with an asterisk, and the asterisk belongs in the grant agreement rather than in the contract.

The contract opts itself into the vesting token with an *inner transaction*, which {{ch:moving-value}} introduced: the application account signs for itself and sends an asset transfer of zero units to itself. The `fee=UInt64(0)` below is the rule from that chapter, unchanged --- an inner transaction's fee comes out of the application account's own balance, so it is set to zero and the caller's fee covers both transactions instead. Note what that means here, where there is no group at all: `initialize` is a single application call carrying one inner transaction, so the caller sets its fee to 2,000 microAlgo and the accounting works out the same way. Pooling is what makes a zero-fee inner transaction legal, and a lone application call is a group of one.

What is new is *when* the opt-in happens, and that is the design question worth your attention: the contract must hold the asset before anybody can deposit into it, and it must be funded above MBR before it can opt in.

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
transaction. The following script demonstrates the complete initialize flow
using AlgoKit Utils.

The `vesting_asset: Asset` parameter is {{ex:reference-types}} arriving where it
matters: the method takes an `Asset`, and since PuyaPy 5.0 the ABI argument
travels as a plain `uint64` asset ID rather than as an index into a foreign
array. The declaration is still required, and it is still the thing that decides
whether the call runs --- it has only moved. The ID arrives by value; the
*availability* of that asset to this call comes from the transaction's resource
references, and a method that reaches for an asset nobody declared fails at the
first opcode that touches it, with `unavailable Asset` and the ID.
{{ex:box-refs-auto}} made the same point about boxes and added the
part that catches people --- algokit-utils populates missing references for you
by simulating first, so a call that would fail from the raw SDK succeeds from
the typed client and teaches you nothing. Every script in this chapter names its
references explicitly. That is not because the tooling needs it; it is so that
the transactions you read here are the transactions the AVM actually sees.

## Compiling and Running What We Have So Far

At this point our contract can be created, reject updates/deletes, and initialize itself by opting into a vesting token. Let us compile and run through the full workflow on LocalNet to make sure everything works before adding more features.

Recompile after adding the `initialize` method and the immutability bare method:

```bash
algokit project run build
```

Check that the artifacts were updated (the file timestamps should change). If you get compilation errors, the most common causes are missing imports (make sure all of `Asset`, `Global`, `UInt64`, `itxn` are imported from `algopy`) or type mismatches in the method signature.

Now create a test script that deploys the contract, creates a test ASA, and calls `initialize`. Save the following as `test_initialize.py` in your project root:

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
app_client, deploy_result = factory.deploy()
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

Run it with `python test_initialize.py`. If everything works, you will see the token creation, deployment, and initialization succeed. If you see `account <address> balance <n> below min <m> (<k> assets)`, increase the funding amount. If you see `Only admin`, make sure the same account that deployed the contract is calling `initialize`.

This workflow --- edit, compile, deploy, call, verify --- is the loop you will follow for the rest of this chapter. Each new method we add can be tested incrementally on LocalNet before moving on.


## Depositing Tokens

The admin needs to deposit the tokens that will be distributed. This means the contract must accept an incoming asset transfer bundled in an atomic group with the method call.

This is {{ex:grouped-asset-transfer}}, scaled up from a vault to a grant. The transfer arrives as a typed parameter rather than by index, which {{ex:validate-at-boundary}} showed is the router promising three things before your first assertion runs: that the transaction at that position is an asset transfer, that it is in this group, and that it is directly before this call. What the router does not promise is *which* asset, *how much*, or *where it went*, and those are exactly the assertions below.

{{ex:group-bounds}} is the other half. A typed parameter fixes what sits at one position; it says nothing about how many other transactions the caller has attached, which is why `Global.group_size` is still checked explicitly.

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

Three of {{ch:moving-value}}'s four questions each appear in the assertions, though not in this order --- which asset, how much, where it went. The fourth, whose it was, is not asked, and its absence is the decision worth understanding. `deposit_txn.sender` is never compared to anything. Authorization runs instead on the *app call's* `Txn.sender`, which must be the admin, so the question this contract asks is not "did the caller pay this?" but "did the admin authorize this arriving?" The two are different accounts on purpose: the admin may direct a deposit that a treasury, an exchange, or a grant program funds, and requiring them to be the same account would rule that out for no gain. Nothing is credited to anybody by name here --- the tokens go into one undifferentiated pool --- so there is no per-account bookkeeping for a mismatched sender to corrupt. Substituting one authorization question for another is safe exactly when that is true, and the tip jar in {{ch:moving-value}} is the case where it was not.

After validation, `available_tokens` increases by the amount received. Later, `create_schedule` will reserve from this counter before writing a new beneficiary schedule, which prevents the admin from promising more tokens than the contract actually holds.

The same `+=` is also the all-or-nothing rule from {{ch:moving-value}} doing real work for the first time in a contract you are shipping, so it is worth naming what it buys you here. The write does not go to the ledger when the line runs; it goes to a copy the whole group shares, and the ledger takes that copy only if every transaction in the group approves, as {{fig:group-commit}} showed. So the deposit and the increment to `available_tokens` are one indivisible thing: there is no state in which the contract believes it holds tokens it did not receive, and no cleanup path to write for the case where the transfer is rejected.

::: {.note}
**A check you will see, and should not copy here.** Tutorials often assert `asset_close_to == Global.zero_address` and `rekey_to == Global.zero_address` on every incoming grouped transaction. Both fields belong to the *sender's* account --- one drains that account's balance, the other reassigns its signing authority --- and the sender here is the admin, not the contract. The contract receives the `amount` it asserted either way, and its own account is reachable only by transactions it signs itself, which default both fields to zero. So the assertion buys the contract nothing and costs the admin's wallet a legal transaction shape. Where these checks *are* the whole game is Logic Signatures, whose program is the only thing standing between an account and anyone who cares to drain it; {{ch:limit-order-book}} takes that up properly. (See [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/).)
:::


## Creating Vesting Schedules

Now we record each team member's vesting schedule. This is per-user data, and where it lives is the most consequential decision in the contract.

*Before reading on: {{ch:state}} and {{ch:boxes}} gave you three places this could go. Pick one, and say what a beneficiary could do to the contract's books if you picked wrong.*

Local state is the tempting answer, because the minimum balance is charged to the account that opts in, which feels like the right party paying. {{ex:clear-state-drops-local}} is why it is the wrong answer, and a vesting schedule is close to the worst case for it. Suppose Bob has claimed 500 of his 1,000 units and then sends a ClearState transaction. It succeeds --- it always succeeds, whatever the clear state program says --- and the record of those 500 units is gone. Bob re-registers and claims 1,000 more. The contract's own accounting was deletable by the person it was accounting against.

::: {.gotcha #clear-state-always-succeeds topic="Global and local state" title="ClearState always succeeds, so local state cannot hold an obligation"}
Users can delete their local state at any time via ClearState, and the protocol guarantees this always succeeds. Never use local state as the sole record of financial obligations, debts, or token claims.
:::

So the schedules go in boxes. The rule that decides it is short enough to carry: **a record the contract owes somebody cannot live somewhere that somebody can delete.** (See [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/).)

::: {.check}
Without looking back, name the three Algorand storage types and one hard constraint on each. Which can a user delete unilaterally? Which has a schema fixed at creation? Which does the application fully control, and who pays for it?
:::

That makes the declaration in `__init__` {{ex:boxmap-declare}} and {{ex:struct-arc4}} used together: a `BoxMap` for the per-account mapping, an `arc4.Struct` so six fields cost one box rather than six. The box name is the `"v_"` prefix plus a 32-byte address, so 34 bytes, and the record is 41. Run that through {{ex:box-mbr-math}} and one beneficiary costs `2,500 + 400 * (34 + 41) = 32,500` microAlgos, about 0.033 Algo.

The `key_prefix=b"v_"` is declared rather than left to default for the sake of that arithmetic. Omit it and PuyaPy uses the attribute name instead, so `self.schedules` gives you a nine-byte prefix and a 41-byte name --- a different MBR, silently, in a funding calculation you wrote by hand two sections from here. The failure surfaces as a balance error inside `create_schedule` and says nothing about box names.

`start_time`, `cliff_end`, and `vesting_end` are all written from one read of `Global.latest_timestamp`, which is {{ex:two-clocks}}'s second clock: seconds from the proposer's wall clock rather than rounds from the ledger's own counter. This contract is denominated in seconds because a grant agreement is, and the skew {{ex:two-clocks}} measured --- bounded only by monotonicity and a ceiling of roughly 25 seconds over the previous block --- is invisible against a three-month cliff. Reading the clock once is not a defence against the value moving --- `Global.latest_timestamp` is the previous block's timestamp and is fixed for the whole transaction, so three reads inside one method would return three identical values. It is a defence against the reader having to know that. One named `now`, three fields derived from it, and the relationship between `start_time`, `cliff_end`, and `vesting_end` is visible on the page instead of resting on a protocol guarantee you would have to go and look up.

Which is also why every comparison against that clock in this contract is a `>=` and never an `==`. A cliff is a threshold you cross, not an instant you hit; {{ex:two-clocks}} showed what happens to code that assumes otherwise.

Every call that touches a box has to say so in advance, and this is the first
place in the book where you write that declaration by hand rather than let the
client infer it. {{ex:box-refs-auto}} is why: algokit-utils simulates the call,
watches which boxes it reaches for, and fills the array in for you, so a script
that would fail from the raw SDK succeeds from the typed client. {{ex:box-io-budget}}
priced what the declaration buys --- 2,048 bytes of read/write capacity per
reference. A 41-byte `VestingSchedule` fits inside one with room to spare, and
the 34-byte name that drove the MBR arithmetic above does not count against the
budget at all.

The full grouped call has three moving pieces: create the MBR payment, pass it
as the typed transaction argument, and include the beneficiary's box reference
on the app call. In this chapter the admin funds schedule MBR and receives the
refund during cleanup, so the contract rejects MBR payments from other senders.
If you want third-party sponsorship, model the sponsor and refund recipient
explicitly instead of reusing this admin-owned MBR flow.

On the client side, the app-call portion looks like this (this is client-side
code, not part of the contract):

```python
# Client must declare the box this transaction will access
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="create_schedule",
        args=[beneficiary_address, 1_000_000, 7_776_000, 31_536_000, mbr_txn],
        # decode_address is from algosdk.encoding
        box_references=[b"v_" + decode_address(beneficiary_address)],
    )
)
```

Forgetting this declaration produces `invalid Box reference` followed by the
box name in hex --- an error you will hit whenever auto-population is disabled
or you build transactions with the raw SDK. Do not confuse it with `read budget
exceeded`, which is a different failure: that one means the references were
declared and there were not enough of them for the combined size of every box
the transaction referenced --- a budget charged before the program runs, against
each referenced box's full stored size whether or not you read a byte of it. If
you see `invalid Box reference`, your first check should always be: did I
declare the box references?

For boxes larger than 2KB, you need multiple references to the same box (for
example, a 4KB box needs two references). The Cookbook (Recipe 6.5) shows this
pattern in detail. Raw SDK `boxes`, AlgoKit Utils `box_references`, and
`algokit_utils.BoxReference` are client-side representations of this same
resource-reference idea.

::: {.gotcha #box-refs-on-every-method topic="Box storage" title="Every method that touches a box needs its own box reference"}
Every method that accesses box storage requires box references on the client side --- not just `create_schedule`. The `claim`, `revoke`, `cleanup_schedule`, `get_vesting_info`, and `get_claimable` methods all read or write the beneficiary's box and must include the same `box_references` declaration. Forgetting this on read-only methods like `get_vesting_info` is a common mistake --- the AVM enforces the I/O budget regardless of whether the access is a read or write.
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

The release curve itself you have already written. {{ex:linear-vesting}} is this
calculation for one grant held in globals, {{ex:vesting-cliff}} adds the cliff
branch and settles the question of whether the linear term measures from `start`
or from `cliff` --- this contract measures from `start`, so arriving at the cliff
releases a lump sum covering everything since the grant began --- and
{{ex:mul-div}} is the multiply-then-divide underneath both. What is new here is
only that the three parameters come out of a box instead of out of state, and
that the same subroutine has to serve three callers.

Two things about `calculate_vested` deserve a second look, because both are
places where {{ch:numbers-and-time}} drew a line and this code sits right on it.

The first is the width. `total * elapsed` is the expression the arithmetic asks
for and the one that must never be written narrow. {{ex:linear-vesting}} put a
number on it for a ninety-day schedule; for the four-year schedule this contract
is built around, the elapsed seconds reach 126,143,999 on the last second before
the schedule closes, and a narrow multiply overflows for any grant *above*
146,235,605,498 base units --- about 146,235 tokens at six decimals. That is not
a large grant. It is a mid-size employee
allocation, and the contract that used the narrow form would pay out correctly
for months and then abort on every call for the rest of the term. Hence
`op.mulw`, which cannot fail: it multiplies two `UInt64`s into a 128-bit product
returned as a high word and a low word.

*Predict before reading on: the narrow version of this contract pays out
correctly for months and then aborts. Which call is the first one to fail --- and
does the grant that triggers it have to be unusually large, or does it just have
to be old?*

The second is the division, and it is the one to be careful about, because the
code below does not do what {{ch:numbers-and-time}} told you to do. That chapter
was blunt: `divw` fails loudly on an overflowing quotient, `divmodw` fails
silently, and for money you take the loud one. This subroutine calls
`op.divmodw`. What makes it safe is the line immediately after:

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
least $2^{64}$ and `q_hi` is not. No pair of inputs separates them --- and that
equivalence holds *here* only because the divisor's own high word is the
hardcoded `UInt64(0)` on the line above. The assertion is not a belt-and-braces
extra; it is `divw`'s abort condition written out by hand.

In *this* subroutine it can never fire. The division is reached only when
`now < vesting_end` and `now >= cliff_end >= start`, so `elapsed < duration`,
so the quotient is strictly less than `total` and therefore fits by
construction. Delete the assert and all fourteen unit tests still pass, because
no input can make it fire. That is worth knowing and worth not relying on: the
invariant lives four branches away from the line it protects, and the next edit
to `create_schedule` is under no obligation to preserve it. Swapping the pair
for `op.divw(high, low, duration)` moves the same guarantee into the opcode,
where no edit can drop it --- Exercise 3 asks you to make that swap. The version
below is here because it is the shape you will meet in real codebases, and
because the point worth carrying is not which opcode to prefer but that
**a four-word return you only wanted one word from is a place where an
overflow check has to be written, not assumed** --- and {{ex:divmodw-silent}} is
what its absence buys you in a routine that lacks this one's luck.

Everything else follows the rules already established. The division floors, so a
beneficiary is paid slightly less than the exact fraction at each intermediate
claim and the dust stays in the contract, which is the direction
{{ch:numbers-and-time}} argued for at length; the `now >= vesting_end` branch
bypasses the division entirely and pays the exact total, so the dust comes back
on the last claim.

`duration` cannot be zero on any path that reaches the division, and the
argument takes two steps rather than one. The first is
{{ex:divide-by-zero}}'s rule applied at the point of establishment:
`create_schedule` asserts `vesting_duration > cliff_duration` before writing
either field, so a freshly created schedule has `vesting_end > start_time` and
`duration` is positive. The second step is the one that is easy to skip.
`revoke` also writes those fields --- it sets both `cliff_end` and `vesting_end`
to the revocation timestamp --- so a revocation at the exact second the grant
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
competing for the 8,192-byte program limit.

Add this module-level function to `smart_contracts/token_vesting/contract.py`, placed **between** the `VestingSchedule` struct definition and the `TokenVesting` class (outside the class, not as a method). Module-level subroutines can be shared across multiple contracts in the same file. Class methods decorated with `@subroutine` are also valid and are scoped to that contract --- we will use class-method subroutines in Chapters {{chn:amm}} and {{chn:amm-factory}}. We use a module-level subroutine here because `calculate_vested` is pure logic that could be reused by other contracts (see the [PuyaPy structure guide](https://algorandfoundation.github.io/puya/lg-structure.html)):

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

The method below is where {{ex:arc4-boundary}} stops being a rule and starts
being four lines of code in a row. Every argument `calculate_vested` receives is
a field read out of a box and converted on the way in; the result comes back
native, gets compared and subtracted natively, and is re-encoded only when it
goes back into the box. Convert at the edge, compute in the middle.

::: {.spec}
**Quick reference: converting between ARC-4 and native types.** When you read `schedule.total_amount`, you get an `arc4.UInt64`. To do math with it, convert: `total = schedule.total_amount.as_uint64()`. To write it back: `schedule.total_amount = arc4.UInt64(new_value)`. For booleans: `schedule.is_revoked.native` yields a Python `bool`. Use `.as_uint64()` and `.as_biguint()` on the numeric ARC-4 types, where `.native` is deprecated (see the `@deprecated` annotations in the [PuyaPy `arc4` stubs](https://github.com/algorandfoundation/puya/blob/main/stubs/algopy-stubs/arc4.pyi)); use `.native` for `String`, `Bool`, `Address`, and `DynamicBytes`, where it remains the standard conversion.
:::

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def claim(self) -> UInt64:
        """Beneficiary claims their vested tokens."""
        beneficiary = Txn.sender
        assert beneficiary in self.schedules, "No vesting schedule"

        # .copy() is required: box storage returns a reference to encoded data.
        # To modify fields, we need a mutable, detached copy --- similar to
        # how an ORM returns a detached object that you modify then save back.
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

        return claimable
```

::: {.setup}
**Beneficiary prerequisites.** Before calling `claim`, the beneficiary must (1) have a funded account (at least 0.2 Algo for the base MBR plus ASA opt-in MBR), and (2) have opted into the vesting ASA (a zero-amount self-transfer of the asset). Without the opt-in, the inner `AssetTransfer` fails with `receiver error: must optin, asset <id> missing from <address>`, surfaced through the AVM's inner-transaction wrapper as `inner tx 0 failed: receiver error: must optin, ...`. The `receiver error:` prefix is the part that matters --- the same `asset <id> missing from <address>` tail appears without it when the *sender* is the one not opted in, and the two send you to different accounts. In a production system, you might add an `opt_in_beneficiary` method that handles this in one atomic group, but for this contract the beneficiary manages it themselves.
:::

Two details in this method are settled by earlier chapters rather than by
anything local. The inner transfer carries `fee=UInt64(0)`, which is
{{ex:inner-fee-zero}}: the caller's fee covers it through pooling, so the
application account never quietly drains itself paying for its own outbound
transactions. And the transfer goes out *before* `claimed_amount` is updated,
which on Ethereum would be the textbook reentrancy bug and here is
{{ex:no-reentrancy}} --- nothing on the receiving side gets control back, so the
ordering is a readability choice and not a security one.

The failure mode that does bite is the recipient's, not the contract's.
{{ex:optin-gate-eager}} is the shape of it: a beneficiary who has never opted
into the grant asset cannot receive it, and the inner transfer takes the whole
call down with it.


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
vested at the revocation timestamp. We also set `cliff_end` and `vesting_end`
to that same timestamp so a later `claim` treats the capped amount as fully
vested. Without that freeze, `claim` would apply the original vesting curve to
the already-capped amount and underpay the beneficiary.


## Cleaning Up Completed Schedules

After a beneficiary has claimed everything, their box consumes storage and locks MBR. Cleaning up deletes the box and refunds the freed MBR.

::: {.gotcha #boxes-outlive-a-deleted-app topic="Box storage" title="Deleting an application does not delete its boxes, and the MBR is gone"}
Cleanup is not housekeeping, it is the only way to get the money back. If an application is deleted while it still owns boxes, those boxes remain in the ledger and the MBR they hold is locked permanently --- there is no application left to call `box_del`, and no protocol path that reclaims it. A contract that creates boxes therefore needs a delete path that is *reachable*: either it refuses `DeleteApplication` outright, as this one does, or it asserts that no boxes remain before allowing deletion. Shipping a deletable, box-owning contract with no such assertion is how funds become unrecoverable without anybody writing a bug.
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

Notice that `cleanup_schedule` has no admin check --- it is deliberately permissionless. Anyone may trigger it once a schedule is fully claimed, and the MBR refund always goes to the admin (who funded it) regardless of who calls the method.

If the contract were deleted while boxes still exist, the MBR would be locked forever. Always clean up boxes before deleting an app. (See [Storage Overview](https://dev.algorand.co/concepts/smart-contracts/storage/overview/) for box lifecycle details.)


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

The `calculate_vested` subroutine is now used in three places. Without it, the vesting math would be duplicated three times in compiled TEAL, consuming precious program bytes within the 8,192-byte limit. (See [Algorand Python structure guide](https://algorandfoundation.github.io/puya/lg-structure.html) for subroutine usage.)


## Testing the Vesting Contract

::: {.note}
Check whether `pytest` and `algorand-python-testing` are already listed in the generated `pyproject.toml`, add whichever is missing, and create a `tests/` directory in your project root. Run pytest from the project environment created by `algokit project bootstrap all` rather than installing it into an unrelated system Python. (See [Testing](https://dev.algorand.co/algokit/utils/python/testing/) for AlgoKit testing patterns.)
:::

{{ch:testing}} argued that a contract needs two test suites rather than one, and
this contract is the case that makes the argument concrete. Vesting is almost
entirely a function of the clock, and a four-year schedule is not something you
can wait for. So the suite splits along the line {{tbl:integration-vs-unit}}
drew.

The fast half is {{ex:unit-test-context}} applied to the schedule arithmetic.
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
`cleanup_schedule` and `reject_lifecycle`, and none of `claim` --- not because
`claim`'s admin check is unreachable, but because everything interesting past it
is an inner transaction. `initialize` and `deposit_tokens` are the only two that
are AVM all the way down.

That is the useful shape of the answer: the slow suite is not "the methods you
could not unit-test," it is "the last few lines of most of them." LocalNet, real
accounts, real MBR, and the {{ex:negative-test-simulate}} pattern for every
security assertion. The project directory for this chapter ships both:
`tests/test_vesting_unit.py` for the fast half and `tests/test_token_vesting.py`
for the slow one, with a `conftest.py` that skips the slow file entirely when
LocalNet is not running.

Here is the deployment helper the LocalNet half is built on. The remaining
helpers follow the same approach --- adapt the interaction patterns from the
deployment section above:

```python
from pathlib import Path
import algokit_utils

APP_SPEC = Path(
    "smart_contracts/artifacts/token_vesting/"
    "TokenVesting.arc56.json"
).read_text()

def deploy_vesting(algorand, admin):
    """Deploy a fresh TokenVesting contract and
    fund it with enough Algo for MBR."""
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC,
        default_sender=admin.address,
    )
    app_client, _ = factory.deploy()
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
```

::: {.tryit}
**Exercise.** Write the `deposit_tokens` and `create_schedule` helpers yourself, using the deployment script patterns from earlier in this chapter. Both build a two-transaction group, so both are places where {{ex:group-bounds}}'s assertion and the helper's construction have to agree; if they disagree, the test fails for a reason that has nothing to do with vesting.
:::

Before diving into the test code, there are two LocalNet behaviors that will affect how you write your test helpers.

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

With those LocalNet behaviors in mind, the following outline belongs in
`tests/test_token_vesting.py` after you implement the helper functions shown
earlier (not part of the contract code):

```python
import pytest
import algokit_utils

class TestTokenVesting:
    def test_full_lifecycle(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)

        # Fund the beneficiary (MBR + ASA opt-in MBR + fee headroom)
        algorand.send.payment(algokit_utils.PaymentParams(
            sender=admin.address, receiver=beneficiary.address,
            amount=algokit_utils.AlgoAmount.from_micro_algo(500_000),
        ))
        # Beneficiary opts into the vesting ASA (required before claiming)
        algorand.send.asset_transfer(algokit_utils.AssetTransferParams(
            sender=beneficiary.address, receiver=beneficiary.address,
            asset_id=token_id, amount=0,
        ))

        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id])
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)

        # Use short durations for LocalNet testing (seconds, not months).
        # Production contracts would use cliff_duration=90*86400,
        # vesting_duration=365*86400.
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        assert get_claimable(vesting, beneficiary) == 0
        advance_time(algorand, 10)  # Past cliff
        claimable = get_claimable(vesting, beneficiary)
        assert 0 < claimable < 1_000_000_000

        call_method(vesting, "claim", [], sender=beneficiary.address)
        advance_time(algorand, 30)  # Past full vesting
        call_method(vesting, "claim", [], sender=beneficiary.address)
        call_method(vesting, "cleanup_schedule", [beneficiary.address])

    def test_revocation_returns_unvested(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id])
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        advance_time(algorand, 15)  # Past cliff, mid-vesting
        unvested = call_method(vesting, "revoke", [beneficiary.address])
        assert unvested.abi_return > 0
        claimed = call_method(vesting, "claim", [], sender=beneficiary.address)
        assert claimed.abi_return > 0

    def test_double_claim_fails(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id])
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        advance_time(algorand, 10)  # Past cliff
        call_method(vesting, "claim", [], sender=beneficiary.address)
        with pytest.raises(Exception, match="Nothing to claim"):
            call_method(vesting, "claim", [], sender=beneficiary.address)

# Helper: wraps the v4 send.call pattern for concise test code.
# Methods that emit inner transactions (claim, revoke, cleanup_schedule)
# need static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000) so the
# outer transaction's fee covers the inner transaction via fee pooling.
def call_method(app_client, method, args, sender=None, static_fee=None):
    return app_client.send.call(
        algokit_utils.AppClientMethodCallParams(
            method=method, args=args, sender=sender, static_fee=static_fee,
        )
    )
```

::: {.tip}
Use the `simulate` endpoint for debugging and security testing, not just read-only queries. Simulate executes the full transaction logic without committing state changes or charging fees --- ideal for diagnosing failures and verifying security checks.
:::

This is a client-side script illustrating the simulate pattern (not part of the contract code). It is {{ex:negative-test-simulate}} pointed at this contract, and the shape is the one that chapter insisted on: a failing simulate *raises*, so the assertion is on the exception, not on a field of a returned object.

```python
import algokit_utils
from algokit_utils.errors import LogicError

# Build a transaction you expect to fail: a claim from an account that
# has no schedule. The attacker needs enough Algo to pay its own fee --
# simulate still charges it, and an unfunded sender fails with
# `overspend` before the approval program runs, which is not the
# failure we are testing for.
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

> Use this pattern to verify every security invariant: construct the attack, simulate it, and confirm both that it raises *and* which assertion caught it. A negative test that only checks "something went wrong" passes when the contract fails for the wrong reason.


## Consolidated Imports

Throughout this chapter, imports were introduced incrementally as each feature required them. Here is the complete set of imports needed at the top of `smart_contracts/token_vesting/contract.py`:

```python
from algopy import (
    ARC4Contract, Account, Asset, BoxMap, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, itxn, op, subroutine,
)
```

## Summary

This chapter introduced no mechanism you had not already met. What it asked of
you was to hold eight of them at once and let them constrain each other, which
is a different skill from learning any one of them and the one production work
actually tests. Having built it, you should be able to:

- Fix a state schema before you know every method, and say what that option cost
- Choose between global state and a box on the shape of the obligation rather than the size of the data
- Recognize when a payout path needs an opt-in that happened in a different transaction, days earlier
- Price a box, a payment, and an opt-in against one application account's balance without deploying to find out
- Carry an overflow argument through three call sites and one subroutine, and say which line actually enforces it
- Read a group of two as one thing that either happens or does not
- Say why an ordering that would be a reentrancy bug elsewhere is only a readability choice here

{{tbl:vesting-build-sequence}} summarizes the build sequence and the mechanisms each step puts into play.

Table: Build sequence and the mechanisms each step puts into play {#tbl:vesting-build-sequence}

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

::: {.note}
**A note on typed clients.** Throughout this book, deployment and test scripts use the `AppFactory` and `app_client.send.call()` pattern with string method names. For larger production projects, use the **typed client** that `algokit project run build` generates automatically (e.g., `token_vesting_client.py` in the artifacts directory). The typed client provides method-specific functions with type-checked arguments (`app_client.send.initialize(args=InitializeArgs(vesting_asset=token_id))`), eliminating string method names and catching parameter errors at development time. See Cookbook recipe 16.3 for a complete example.
:::

In the next chapter, we extend the vesting contract with NFTs for transferability. Then in {{ch:amm}}, these same concepts reappear in a higher-stakes context as we build a constant product AMM with multi-token accounting, price curves, and LP token mechanics.

## Exercises

1. **(Understand)** Without rereading the contract, list every account whose minimum balance this system raises, and what each raise bought. There are four answers and one of them is not the application account. Then say which of the four is refundable and by whose call.

2. **(Apply)** Modify the vesting contract to support a second cliff: tokens vest 25% immediately at the first cliff (3 months), then the remaining 75% linearly from 3 to 12 months. What changes to `calculate_vested` are needed?

3. **(Evaluate)** Replace the `op.divmodw` pair in `calculate_vested` with a single `op.divw(high, low, duration)`, deleting the `assert q_hi == 0` line the swap absorbs. Run `tests/test_vesting_unit.py` against both versions: all fourteen pass either way, and the chapter has already told you why --- the assert is unreachable on this contract's control flow. So the tests cannot decide this for you. Decide it on the argument instead. Write down the chain of facts that makes the assert unreachable, then say which link a future maintainer is most likely to break without noticing, and which of the two versions still refuses to pay out a wrong number afterwards. Then answer the question that generalizes: when the tests agree, what is left to choose on?

4. **(Apply)** Add a `pause` method that prevents all claims until unpaused, callable only by admin. What state field do you add, and which methods need to check it? Note that {{ex:state-schema-fixed}} makes this exercise unimplementable on an already-deployed contract --- say what you would have had to do at creation time to keep the option open.

5. **(Analyze)** The `cleanup_schedule` method sends the freed MBR to the admin, not the beneficiary. Argue both sides: should the MBR refund go to the admin (who funded it) or the beneficiary (whose data it stored)? What are the security implications of each choice?

6. **(Create)** Design an extension where the admin can increase a beneficiary's total allocation after the schedule is already created. What new method is needed? What happens to already-vested tokens? What security checks prevent abuse?

7. **(Create, cross-chapter)** The vesting contract uses a single admin address. Design a modification where admin operations (`initialize`, `create_schedule`, `revoke`) require approval from 2-of-3 multisig signers. What changes to the admin check pattern are needed? How does Algorand's native multisig support simplify this compared to implementing multisig logic in the contract itself?

::: {.tryit}
**Practice with the Cookbook.** Reinforce this chapter's concepts with Cookbook recipes: 1.2 (contract with `__init__`), 3.3 (wide arithmetic), 6.2 (BoxMap), 8.1 (Algo payment), and 11.1 (creator-only method).
:::

## Further Reading

- [Algorand Python Program Structure](https://algorandfoundation.github.io/puya/lg-structure.html) --- program structure, decorators, `__init__` semantics
- [Types](https://algorandfoundation.github.io/puya/lg-types.html) --- UInt64, Bytes, BigUInt, ARC-4 types
- [Storage](https://algorandfoundation.github.io/puya/lg-storage.html) --- GlobalState, LocalState, Box, BoxMap
- [Transactions](https://algorandfoundation.github.io/puya/lg-transactions.html) --- gtxn parameters, inner transactions
- [ARC-4 in Python](https://algorandfoundation.github.io/puya/lg-arc4.html) --- abimethod, baremethod, ARC4Contract
- [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/) --- MBR formula, I/O budget, lifecycle
- [App Client](https://dev.algorand.co/algokit/utils/python/app-client/) --- deployment, method calls, simulation
- [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) --- program size, opcode budget, stack limits
- [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/) --- the rekey_to field and its security implications
- [AVM Opcodes](https://dev.algorand.co/reference/algorand-teal/opcodes/) --- mulw, divmodw, bsqrt, and all other opcodes

## Before You Continue

Before starting the next chapter, you should be able to:

- [ ] Name every account this contract's MBR is charged to, and what each charge bought
- [ ] Say which of this contract's eleven methods can be tested without an AVM, and where the line runs
- [ ] Trace one claim from the app call through the box read, the arithmetic, and the inner transfer
- [ ] Explain why a schedule lives in a box rather than in the beneficiary's local state
- [ ] Point at the single line that keeps `calculate_vested` from returning a wrong number, and say what makes it currently unreachable

If any of these are unclear, revisit the relevant section before proceeding.
