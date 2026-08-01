<!-- GENERATED FILE. Do not edit.
     Every row below is an example caption in a numbered chapter paired
     with the `<!-- finder: ... -->` line beneath it. Edit those and run
     `python3 scripts/generate_appendices.py`.
     tests/test_book_integrity.py fails if this file has drifted. -->

\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Appendix D: The Example Finder {-}

Every numbered example in the book, listed by what it is *for* rather than by what it is called. The left column is the task you arrived with; the right is where the example that does it lives.

A caption names an example from the author's side. This appendix names it from yours, which is why the wording here will not match the wording on the page. The tables are deliberately uncaptioned: they are lookup surfaces, not numbered exhibits, and nothing in the book cites them.

## By Part {-}

### Part I: Foundations {-}

| To do this | Go to |
|------------|-------|
| See what algokit init generates before touching anything | Example 1-1 |
| Deploy a contract and call a method from Python | Example 1-2 |
| Write an integration test that deploys and calls a contract | Example 1-3 |
| See the smallest useful contract that has an admin method | Example 2-1 |
| Write the smallest complete Algorand contract that actually does something | Example 2-2 |
| Attach a readable error message to a failing check | Example 2-3 |
| Ask the ledger a question about an account, an asset, or another app | Example 2-4 |
| Understand what ARC4Contract generates for me | Example 2-5 |
| See what algokit project run build actually produced | Example 2-6 |
| Connect to a network and get an account that can pay for things | Example 2-7 |
| Deploy a contract using the typed client algokit generated | Example 2-8 |
| Call a contract method and read the value it returned | Example 2-9 |
| See the greeter with all three defects fixed | Example 2-10 |
| See a contract with a few methods a generated client can call | Example 3-1 |
| Know what the AVM will and will not let me do to a value | Example 3-2 |
| Choose between the three text types | Example 3-3 |
| Pull one field out of the middle of a byte string | Example 3-4 |
| Turn a number into exactly eight bytes and read it back | Example 3-5 |
| Do arithmetic with an ARC-4 argument | Example 3-6 |
| Get the native value out of an ARC-4 one | Example 3-7 |
| Treat raw bytes as an ARC-4 value safely | Example 3-8 |
| Cut the cost of argument validation on a method that is over budget | Example 3-9 |
| Find out what several flags cost me | Example 3-10 |
| Give the client more than one thing back from a single call | Example 3-11 |
| Hold exactly N of something where N never changes | Example 3-12 |
| Hold a list when the length is not known in advance | Example 3-13 |
| Run a method on opt-in or delete rather than on an ordinary call | Example 3-14 |
| Handle a call that arrives with no arguments at all | Example 3-15 |
| Restrict a method to creation, or keep it out of creation entirely | Example 3-16 |
| Find out whether renaming a method or changing an argument type breaks deployed callers | Example 3-17 |
| Expose two ways to call the same operation | Example 3-18 |
| Offer a getter clients can call without paying a fee | Example 3-19 |
| Save a client a lookup it would otherwise do before every call | Example 3-20 |
| Read an app spec and see what a contract exposes | Example 3-21 |
| See the counter with all three defects fixed | Example 3-22 |
| See a membership contract that keeps balances in local state | Example 4-1 |
| Declare both global and local state in one contract | Example 4-2 |
| Keep a counter in global state | Example 4-3 |
| Read a global key that might not exist yet | Example 4-4 |
| Tell the difference between a state key set to zero and one never set | Example 4-5 |
| Remove a key from global state entirely | Example 4-6 |
| Reserve state schema slots for features I have not written yet | Example 4-7 |
| Redeploy a contract whose state schema outgrew the deployed one | Example 4-8 |
| Read a specific account's local state from a method | Example 4-9 |
| Store one value per account without requiring an opt-in | Example 4-10 |
| Store several named values per account in local state | Example 4-11 |
| Store several related fields in one state slot | Example 4-12 |
| Fix the "must be copied using .copy()" compiler error | Example 4-13 |
| Update one field of a stored record without re-encoding it | Example 4-14 |
| Make a stored record immutable after it is written | Example 4-15 |
| Set global state values when the contract is created | Example 4-16 |
| Pass parameters to a contract at creation time | Example 4-17 |
| Initialize an account's local state when it opts in | Example 4-18 |
| Run code when an account closes out of my application | Example 4-19 |
| Understand what happens to local state on a clear-state transaction | Example 4-20 |
| See the registry with all three defects fixed | Example 4-21 |
| See a contract that appends records into a single box | Example 5-1 |
| Store a single value in a box | Example 5-2 |
| Check whether a box exists without failing the call | Example 5-3 |
| Create a box up front and delete it to reclaim the MBR | Example 5-4 |
| Check the app account has enough balance before creating a box | Example 5-5 |
| Store one value per account in boxes | Example 5-6 |
| Find out the real box name behind a BoxMap key | Example 5-7 |
| Compute the MBR cost of a box in the contract itself | Example 5-8 |
| Understand why two BoxMaps can overwrite each other | Example 5-9 |
| Key a BoxMap by more than one value | Example 5-10 |
| Avoid declaring box references by hand on every call | Example 5-11 |
| Work out how many box references an app call needs | Example 5-12 |
| Allocate a box of a fixed size and read part of it | Example 5-13 |
| Use raw box operations on one entry of a BoxMap | Example 5-14 |
| Get a box's size without reading its contents | Example 5-15 |
| Update part of a box without rewriting the whole thing | Example 5-16 |
| Read part of a box without reading the whole thing | Example 5-17 |
| Create a box exactly the size of the struct it will hold | Example 5-18 |
| Make an existing box bigger | Example 5-19 |
| Insert bytes into the middle of a box | Example 5-20 |
| Append a fixed-size record to a growing box | Example 5-21 |
| Iterate over box entries without running out of budget | Example 5-22 |
| Recognize an unbounded loop over box data | Example 5-23 |
| See the guestbook with all three defects fixed | Example 5-24 |
| See a linear vesting calculation that returns zero for the whole schedule | Example 6-1 |
| Express a percentage or a fee without floating point | Example 6-2 |
| See what happens when a uint64 addition overflows | Example 6-3 |
| See what happens when a uint64 subtraction goes below zero | Example 6-4 |
| Guard a division against a zero divisor | Example 6-5 |
| See a division-by-zero that compiles cleanly and detonates later | Example 6-6 |
| Multiply two numbers whose product does not fit in 64 bits | Example 6-7 |
| Divide a 128-bit value by a 64-bit divisor | Example 6-8 |
| Understand why divmodw is the more dangerous wide division | Example 6-9 |
| Compute (a * b) / c safely as a reusable subroutine | Example 6-10 |
| Read the current round and the current time inside a contract | Example 6-11 |
| Set and check a deadline using block timestamps | Example 6-12 |
| Make a contract stop working after a chosen round | Example 6-13 |
| See how using Txn.last_valid as a clock gets exploited | Example 6-14 |
| Read the timestamp of an earlier block from inside a contract | Example 6-15 |
| Build a lottery whose outcome nobody can predict when they enter | Example 6-16 |
| See why a block seed cannot be used as a source of randomness | Example 6-17 |
| Compute how much of a grant has vested at a given round | Example 6-18 |
| See why dividing before multiplying pays nothing | Example 6-19 |
| Add a cliff to a linear vesting schedule | Example 6-20 |
| Stop an account from calling a method too often | Example 6-21 |
| See the vesting calculator with all four defects fixed | Example 6-22 |
| See a working tip jar whose money cannot be withdrawn | Example 7-1 |
| Read the application account's address and spendable balance | Example 7-2 |
| Send Algo from a contract with an inner transaction | Example 7-3 |
| Charge the caller for a contract's inner transaction fees | Example 7-4 |
| See how a non-zero inner fee drains a contract | Example 7-5 |
| Accept and validate an Algo payment sent alongside a call | Example 7-6 |
| See a deposit method credit a payment that went elsewhere | Example 7-7 |
| Validate an incoming ASA transfer against a stored asset id | Example 7-8 |
| See a vault credit a worthless asset as if it were the real one | Example 7-9 |
| Bound the size and position of the group a method accepts | Example 7-10 |
| See one payment credited sixteen times in a single group | Example 7-11 |
| Order a state write and an inner payment without a rollback path | Example 7-12 |
| Take a fee from an incoming payment and forward the remainder | Example 7-13 |
| Reject a pool bootstrapped with the same asset on both sides | Example 7-14 |
| See the one-line omission behind Tinyman V1's $3M exploit | Example 7-15 |
| Mint an ASA whose creator is the application account | Example 7-16 |
| Opt an application account into an ASA it did not create | Example 7-17 |
| Transfer ASA units from a contract to an account | Example 7-18 |
| Check that a recipient has opted in before sending them an asset | Example 7-19 |
| Close a contract out of an asset and recover its 100,000 MBR | Example 7-20 |
| Reconfigure an ASA's roles and permanently clear its clawback | Example 7-21 |
| Perform a clawback transfer from a contract | Example 7-22 |
| Account for deposits with stored state rather than with the balance | Example 7-23 |
| See a donation re-price every position in a vault | Example 7-24 |
| See the tip jar with all four defects fixed | Example 7-25 |
| See a contract whose green test suite proves nothing | Example 8-1 |
| Prove the assert message is absent from the compiled bytecode | Example 8-2 |
| Emit a machine-readable error code that survives without the app spec | Example 8-3 |
| Place an unconditional failure inside a method that must return a value | Example 8-4 |
| Compare the two spellings of an unconditional failure | Example 8-5 |
| See which checks the ARC-4 router has already performed for you | Example 8-6 |
| Write interaction-before-effects deliberately and see why it is safe | Example 8-7 |
| Run a method against real ledger state without committing anything | Example 8-8 |
| Measure what a call costs when it does not fit in one app call's budget | Example 8-9 |
| Ask the node which accounts, assets and boxes a call actually touched | Example 8-10 |
| Get the decoded return value from each of the three ways to call a method | Example 8-11 |
| Turn a program counter into the Python statement that produced it | Example 8-12 |
| See the one assertion that can tell a correct contract from an incorrect one | Example 8-13 |
| Test time-dependent behaviour without waiting or deploying | Example 8-14 |
| Prove a rejection happens for the reason you intended | Example 8-15 |
| Emit an event a stranger can find without reading state | Example 8-16 |

### Part II: Value Under Management {-}

| To do this | Go to |
|------------|-------|
| Build a compound box key that can be decomposed again | Example 9-1 |
| Understand why an array assignment needs .copy() | Example 9-2 |
| Declare an array whose length is known at compile time | Example 9-3 |
| See a working paid message board that anyone can take over | Example 10-1 |
| Restrict a method to the account that deployed the contract | Example 10-2 |
| Hold an admin role in state so it can change hands | Example 10-3 |
| Hand an admin role over without a typo losing it forever | Example 10-4 |
| Stop a configuration method being called a second time | Example 10-5 |
| Let only the author of a stored record change it | Example 10-6 |
| Let a set of accounts share a role, and cap how many | Example 10-7 |
| Add a switch that stops the contract mutating during an incident | Example 10-8 |
| Restrict a method so only a specific application may call it | Example 10-9 |
| Compare a calling application against a stored address | Example 10-10 |
| Insist a privileged method is reached by a person, not a contract | Example 10-11 |
| Authorize a caller with a signature made off-chain | Example 10-12 |
| Build a payment and an app call as one atomic group from the client | Example 10-13 |
| Stash who passed a check for a later transaction in the group to read | Example 10-14 |
| Read an approval an earlier app call left, checking who wrote it | Example 10-15 |
| Know which transaction fields a stateful contract should not police | Example 10-16 |
| The corrected pay-to-post board, every authorization guard in place | Example 10-17 |
| See a working revenue splitter that spends itself to a halt | Example 11-1 |
| Work out what an application's declared schema costs, and who pays it | Example 11-2 |
| Work out what an application's extra program pages cost | Example 11-3 |
| Make the caller pay the minimum balance for storage they cause | Example 11-4 |
| Return a box deposit to whoever actually paid it | Example 11-5 |
| Ask an account what storage it holds, and what floor that implies | Example 11-6 |
| Read the network's minimum fee instead of hard-coding 1,000 | Example 11-7 |
| Make the caller pay for the inner transactions your contract sends | Example 11-8 |
| Let a relayer pay the fee so your user signs a zero-fee transaction | Example 11-9 |
| Find out how much opcode budget a method actually has left | Example 11-10 |
| Buy opcode budget when a method needs more than 700 | Example 11-11 |
| Get more opcode budget without the contract sending anything | Example 11-12 |
| Measure what a loop costs in opcodes rather than guessing | Example 11-13 |
| Read an account's asset holding that the transaction declared | Example 11-14 |
| Pass an account or asset as a typed argument | Example 11-15 |
| Know when your client cannot work out your resources for you | Example 11-16 |
| The corrected fee splitter, caller-funded fees and accounted dust | Example 11-17 |

### Part III: Building a DEX {-}

| To do this | Go to |
|------------|-------|
| See a price quote that gives value away in both directions | Example 13-1 |
| Fix which asset a pool's price is quoted in, once and for all | Example 13-2 |
| Store a fractional price in a type that has no fractions | Example 13-3 |
| Decide between BigUInt and a wide multiply | Example 13-4 |
| Price a share of a pool in a unit that did not exist before | Example 13-5 |
| Round a division that decides what ENTERS the contract | Example 13-6 |
| Follow the residue a floored payout leaves behind | Example 13-7 |
| Say where a swap fee actually goes | Example 13-8 |
| Reproduce a contract's quote off-chain, to the unit | Example 13-9 |
| Stop the first depositor from taking the second one's money | Example 13-10 |
| Accumulate a price so any two readings give an average | Example 13-11 |
| Compute what an LP gave up by providing rather than holding | Example 13-12 |
| Quote both directions of a swap without ever forming a price | Example 13-13 |
| See a parent contract that pays whichever child it is handed | Example 15-1 |
| See how little it takes to impersonate a contract | Example 15-2 |
| Call another contract's method with the compiler checking it | Example 15-3 |
| Call a contract whose source you do not have | Example 15-4 |
| Satisfy a callee that requires a grouped payment | Example 15-5 |
| Send several inner transactions atomically | Example 15-6 |
| Find the limit on nested application calls | Example 15-7 |
| Read a value out of another application without calling it | Example 15-8 |
| Read one account's local state for another application | Example 15-9 |
| Find out who created an application | Example 15-10 |
| Read state a transaction earlier in the same group just wrote | Example 15-11 |
| Deploy one contract from inside another | Example 15-12 |
| Give a newly created application an account it can use | Example 15-13 |
| Keep a spawned child's id instead of taking it from the caller | Example 15-14 |

### Part IV: Chance {-}

| To do this | Go to |
|------------|-------|
| Draw an outcome from a block seed and watch a caller choose it | Example 18-1 |
| Fix a value now and reveal it later, verifiably | Example 18-2 |
| Read a randomness beacon from inside a contract | Example 18-3 |
| Run a raffle from entry to payout | Example 18-4 |

### Part V: Stateless Programs {-}

| To do this | Go to |
|------------|-------|
| See the smallest complete LogicSig | Example 20-1 |
| See a LogicSig that authorises more than its author meant | Example 20-2 |
| The checks a LogicSig cannot ship without | Example 20-3 |
| A LogicSig that is its own account, with no key anywhere | Example 20-4 |
| An account's own key signs a program once, and cannot unsign it | Example 20-5 |
| See why naming an application is a wider permission than it looks | Example 20-6 |
| Narrow a LogicSig to a single method of a single application | Example 20-7 |
| Get a LogicSig's address from inside a smart contract | Example 20-8 |
| Stop a LogicSig-signed transaction being replayed | Example 20-9 |
| The LogicSig version of trusting caller-supplied input | Example 20-10 |
| See where a LogicSig's opcode budget comes from | Example 20-11 |

### Part VI: Cryptography {-}

| To do this | Go to |
|------------|-------|
| Choose a hash by what it costs | Example 22-1 |
| Check a signature made by a key that never signed a transaction | Example 22-2 |
| Stop a signature being valid for something it was not meant for | Example 22-3 |
| Derive a signer's key from an ECDSA signature | Example 22-4 |
| Prove an address is on a list you are not storing | Example 22-5 |
| Get randomness that nobody chose and everybody can verify | Example 22-6 |
| Add and multiply points on BN254 | Example 22-7 |
| The hash that is expensive here and cheap inside a proof | Example 22-8 |
| See why a pairing check needs companion transactions | Example 22-9 |
| Verify a signature a quantum computer is not expected to forge | Example 22-10 |
| Make a contract believe a proof only because it watched it verify | Example 23-1 |

### Part VII: Shipping {-}

| To do this | Go to |
|------------|-------|
| Write bytes into a transaction's log | Example 24-1 |
| Emit an event a client can recognise | Example 24-2 |
| Emit an event without importing its struct | Example 24-3 |
| Attach an error code a client can switch on | Example 24-4 |
| See what makes a contract impossible to change | Example 24-5 |
| Allow an upgrade without allowing it forever | Example 24-6 |
| Pause a live contract and announce the switch | Example 24-7 |
| Find out whether a contract has been replaced | Example 24-8 |
| Delete a contract and get its minimum balance back | Example 24-9 |
| See a contract that can be observed, changed and shut down | Example 24-10 |

## Alphabetical {-}

| To do this | Go to |
|------------|-------|
| A LogicSig that is its own account, with no key anywhere | Example 20-4 |
| Accept and validate an Algo payment sent alongside a call | Example 7-6 |
| Account for deposits with stored state rather than with the balance | Example 7-23 |
| Accumulate a price so any two readings give an average | Example 13-11 |
| Add a cliff to a linear vesting schedule | Example 6-20 |
| Add a switch that stops the contract mutating during an incident | Example 10-8 |
| Add and multiply points on BN254 | Example 22-7 |
| Allocate a box of a fixed size and read part of it | Example 5-13 |
| Allow an upgrade without allowing it forever | Example 24-6 |
| An account's own key signs a program once, and cannot unsign it | Example 20-5 |
| Append a fixed-size record to a growing box | Example 5-21 |
| Ask an account what storage it holds, and what floor that implies | Example 11-6 |
| Ask the ledger a question about an account, an asset, or another app | Example 2-4 |
| Ask the node which accounts, assets and boxes a call actually touched | Example 8-10 |
| Attach a readable error message to a failing check | Example 2-3 |
| Attach an error code a client can switch on | Example 24-4 |
| Authorize a caller with a signature made off-chain | Example 10-12 |
| Avoid declaring box references by hand on every call | Example 5-11 |
| Bound the size and position of the group a method accepts | Example 7-10 |
| Build a compound box key that can be decomposed again | Example 9-1 |
| Build a lottery whose outcome nobody can predict when they enter | Example 6-16 |
| Build a payment and an app call as one atomic group from the client | Example 10-13 |
| Buy opcode budget when a method needs more than 700 | Example 11-11 |
| Call a contract method and read the value it returned | Example 2-9 |
| Call a contract whose source you do not have | Example 15-4 |
| Call another contract's method with the compiler checking it | Example 15-3 |
| Charge the caller for a contract's inner transaction fees | Example 7-4 |
| Check a signature made by a key that never signed a transaction | Example 22-2 |
| Check that a recipient has opted in before sending them an asset | Example 7-19 |
| Check the app account has enough balance before creating a box | Example 5-5 |
| Check whether a box exists without failing the call | Example 5-3 |
| Choose a hash by what it costs | Example 22-1 |
| Choose between the three text types | Example 3-3 |
| Close a contract out of an asset and recover its 100,000 MBR | Example 7-20 |
| Compare a calling application against a stored address | Example 10-10 |
| Compare the two spellings of an unconditional failure | Example 8-5 |
| Compute (a * b) / c safely as a reusable subroutine | Example 6-10 |
| Compute how much of a grant has vested at a given round | Example 6-18 |
| Compute the MBR cost of a box in the contract itself | Example 5-8 |
| Compute what an LP gave up by providing rather than holding | Example 13-12 |
| Connect to a network and get an account that can pay for things | Example 2-7 |
| Create a box exactly the size of the struct it will hold | Example 5-18 |
| Create a box up front and delete it to reclaim the MBR | Example 5-4 |
| Cut the cost of argument validation on a method that is over budget | Example 3-9 |
| Decide between BigUInt and a wide multiply | Example 13-4 |
| Declare an array whose length is known at compile time | Example 9-3 |
| Declare both global and local state in one contract | Example 4-2 |
| Delete a contract and get its minimum balance back | Example 24-9 |
| Deploy a contract and call a method from Python | Example 1-2 |
| Deploy a contract using the typed client algokit generated | Example 2-8 |
| Deploy one contract from inside another | Example 15-12 |
| Derive a signer's key from an ECDSA signature | Example 22-4 |
| Divide a 128-bit value by a 64-bit divisor | Example 6-8 |
| Do arithmetic with an ARC-4 argument | Example 3-6 |
| Draw an outcome from a block seed and watch a caller choose it | Example 18-1 |
| Emit a machine-readable error code that survives without the app spec | Example 8-3 |
| Emit an event a client can recognise | Example 24-2 |
| Emit an event a stranger can find without reading state | Example 8-16 |
| Emit an event without importing its struct | Example 24-3 |
| Expose two ways to call the same operation | Example 3-18 |
| Express a percentage or a fee without floating point | Example 6-2 |
| Find out how much opcode budget a method actually has left | Example 11-10 |
| Find out the real box name behind a BoxMap key | Example 5-7 |
| Find out what several flags cost me | Example 3-10 |
| Find out whether a contract has been replaced | Example 24-8 |
| Find out whether renaming a method or changing an argument type breaks deployed callers | Example 3-17 |
| Find out who created an application | Example 15-10 |
| Find the limit on nested application calls | Example 15-7 |
| Fix a value now and reveal it later, verifiably | Example 18-2 |
| Fix the "must be copied using .copy()" compiler error | Example 4-13 |
| Fix which asset a pool's price is quoted in, once and for all | Example 13-2 |
| Follow the residue a floored payout leaves behind | Example 13-7 |
| Get a box's size without reading its contents | Example 5-15 |
| Get a LogicSig's address from inside a smart contract | Example 20-8 |
| Get more opcode budget without the contract sending anything | Example 11-12 |
| Get randomness that nobody chose and everybody can verify | Example 22-6 |
| Get the decoded return value from each of the three ways to call a method | Example 8-11 |
| Get the native value out of an ARC-4 one | Example 3-7 |
| Give a newly created application an account it can use | Example 15-13 |
| Give the client more than one thing back from a single call | Example 3-11 |
| Guard a division against a zero divisor | Example 6-5 |
| Hand an admin role over without a typo losing it forever | Example 10-4 |
| Handle a call that arrives with no arguments at all | Example 3-15 |
| Hold a list when the length is not known in advance | Example 3-13 |
| Hold an admin role in state so it can change hands | Example 10-3 |
| Hold exactly N of something where N never changes | Example 3-12 |
| Initialize an account's local state when it opts in | Example 4-18 |
| Insert bytes into the middle of a box | Example 5-20 |
| Insist a privileged method is reached by a person, not a contract | Example 10-11 |
| Iterate over box entries without running out of budget | Example 5-22 |
| Keep a counter in global state | Example 4-3 |
| Keep a spawned child's id instead of taking it from the caller | Example 15-14 |
| Key a BoxMap by more than one value | Example 5-10 |
| Know what the AVM will and will not let me do to a value | Example 3-2 |
| Know when your client cannot work out your resources for you | Example 11-16 |
| Know which transaction fields a stateful contract should not police | Example 10-16 |
| Let a relayer pay the fee so your user signs a zero-fee transaction | Example 11-9 |
| Let a set of accounts share a role, and cap how many | Example 10-7 |
| Let only the author of a stored record change it | Example 10-6 |
| Make a contract believe a proof only because it watched it verify | Example 23-1 |
| Make a contract stop working after a chosen round | Example 6-13 |
| Make a stored record immutable after it is written | Example 4-15 |
| Make an existing box bigger | Example 5-19 |
| Make the caller pay for the inner transactions your contract sends | Example 11-8 |
| Make the caller pay the minimum balance for storage they cause | Example 11-4 |
| Measure what a call costs when it does not fit in one app call's budget | Example 8-9 |
| Measure what a loop costs in opcodes rather than guessing | Example 11-13 |
| Mint an ASA whose creator is the application account | Example 7-16 |
| Multiply two numbers whose product does not fit in 64 bits | Example 6-7 |
| Narrow a LogicSig to a single method of a single application | Example 20-7 |
| Offer a getter clients can call without paying a fee | Example 3-19 |
| Opt an application account into an ASA it did not create | Example 7-17 |
| Order a state write and an inner payment without a rollback path | Example 7-12 |
| Pass an account or asset as a typed argument | Example 11-15 |
| Pass parameters to a contract at creation time | Example 4-17 |
| Pause a live contract and announce the switch | Example 24-7 |
| Perform a clawback transfer from a contract | Example 7-22 |
| Place an unconditional failure inside a method that must return a value | Example 8-4 |
| Price a share of a pool in a unit that did not exist before | Example 13-5 |
| Prove a rejection happens for the reason you intended | Example 8-15 |
| Prove an address is on a list you are not storing | Example 22-5 |
| Prove the assert message is absent from the compiled bytecode | Example 8-2 |
| Pull one field out of the middle of a byte string | Example 3-4 |
| Quote both directions of a swap without ever forming a price | Example 13-13 |
| Read a global key that might not exist yet | Example 4-4 |
| Read a randomness beacon from inside a contract | Example 18-3 |
| Read a specific account's local state from a method | Example 4-9 |
| Read a value out of another application without calling it | Example 15-8 |
| Read an account's asset holding that the transaction declared | Example 11-14 |
| Read an app spec and see what a contract exposes | Example 3-21 |
| Read an approval an earlier app call left, checking who wrote it | Example 10-15 |
| Read one account's local state for another application | Example 15-9 |
| Read part of a box without reading the whole thing | Example 5-17 |
| Read state a transaction earlier in the same group just wrote | Example 15-11 |
| Read the application account's address and spendable balance | Example 7-2 |
| Read the current round and the current time inside a contract | Example 6-11 |
| Read the network's minimum fee instead of hard-coding 1,000 | Example 11-7 |
| Read the timestamp of an earlier block from inside a contract | Example 6-15 |
| Recognize an unbounded loop over box data | Example 5-23 |
| Reconfigure an ASA's roles and permanently clear its clawback | Example 7-21 |
| Redeploy a contract whose state schema outgrew the deployed one | Example 4-8 |
| Reject a pool bootstrapped with the same asset on both sides | Example 7-14 |
| Remove a key from global state entirely | Example 4-6 |
| Reproduce a contract's quote off-chain, to the unit | Example 13-9 |
| Reserve state schema slots for features I have not written yet | Example 4-7 |
| Restrict a method so only a specific application may call it | Example 10-9 |
| Restrict a method to creation, or keep it out of creation entirely | Example 3-16 |
| Restrict a method to the account that deployed the contract | Example 10-2 |
| Return a box deposit to whoever actually paid it | Example 11-5 |
| Round a division that decides what ENTERS the contract | Example 13-6 |
| Run a method against real ledger state without committing anything | Example 8-8 |
| Run a method on opt-in or delete rather than on an ordinary call | Example 3-14 |
| Run a raffle from entry to payout | Example 18-4 |
| Run code when an account closes out of my application | Example 4-19 |
| Satisfy a callee that requires a grouped payment | Example 15-5 |
| Save a client a lookup it would otherwise do before every call | Example 3-20 |
| Say where a swap fee actually goes | Example 13-8 |
| See a contract that appends records into a single box | Example 5-1 |
| See a contract that can be observed, changed and shut down | Example 24-10 |
| See a contract whose green test suite proves nothing | Example 8-1 |
| See a contract with a few methods a generated client can call | Example 3-1 |
| See a deposit method credit a payment that went elsewhere | Example 7-7 |
| See a division-by-zero that compiles cleanly and detonates later | Example 6-6 |
| See a donation re-price every position in a vault | Example 7-24 |
| See a linear vesting calculation that returns zero for the whole schedule | Example 6-1 |
| See a LogicSig that authorises more than its author meant | Example 20-2 |
| See a membership contract that keeps balances in local state | Example 4-1 |
| See a parent contract that pays whichever child it is handed | Example 15-1 |
| See a price quote that gives value away in both directions | Example 13-1 |
| See a vault credit a worthless asset as if it were the real one | Example 7-9 |
| See a working paid message board that anyone can take over | Example 10-1 |
| See a working revenue splitter that spends itself to a halt | Example 11-1 |
| See a working tip jar whose money cannot be withdrawn | Example 7-1 |
| See how a non-zero inner fee drains a contract | Example 7-5 |
| See how little it takes to impersonate a contract | Example 15-2 |
| See how using Txn.last_valid as a clock gets exploited | Example 6-14 |
| See one payment credited sixteen times in a single group | Example 7-11 |
| See the counter with all three defects fixed | Example 3-22 |
| See the greeter with all three defects fixed | Example 2-10 |
| See the guestbook with all three defects fixed | Example 5-24 |
| See the one assertion that can tell a correct contract from an incorrect one | Example 8-13 |
| See the one-line omission behind Tinyman V1's $3M exploit | Example 7-15 |
| See the registry with all three defects fixed | Example 4-21 |
| See the smallest complete LogicSig | Example 20-1 |
| See the smallest useful contract that has an admin method | Example 2-1 |
| See the tip jar with all four defects fixed | Example 7-25 |
| See the vesting calculator with all four defects fixed | Example 6-22 |
| See what algokit init generates before touching anything | Example 1-1 |
| See what algokit project run build actually produced | Example 2-6 |
| See what happens when a uint64 addition overflows | Example 6-3 |
| See what happens when a uint64 subtraction goes below zero | Example 6-4 |
| See what makes a contract impossible to change | Example 24-5 |
| See where a LogicSig's opcode budget comes from | Example 20-11 |
| See which checks the ARC-4 router has already performed for you | Example 8-6 |
| See why a block seed cannot be used as a source of randomness | Example 6-17 |
| See why a pairing check needs companion transactions | Example 22-9 |
| See why dividing before multiplying pays nothing | Example 6-19 |
| See why naming an application is a wider permission than it looks | Example 20-6 |
| Send Algo from a contract with an inner transaction | Example 7-3 |
| Send several inner transactions atomically | Example 15-6 |
| Set and check a deadline using block timestamps | Example 6-12 |
| Set global state values when the contract is created | Example 4-16 |
| Stash who passed a check for a later transaction in the group to read | Example 10-14 |
| Stop a configuration method being called a second time | Example 10-5 |
| Stop a LogicSig-signed transaction being replayed | Example 20-9 |
| Stop a signature being valid for something it was not meant for | Example 22-3 |
| Stop an account from calling a method too often | Example 6-21 |
| Stop the first depositor from taking the second one's money | Example 13-10 |
| Store a fractional price in a type that has no fractions | Example 13-3 |
| Store a single value in a box | Example 5-2 |
| Store one value per account in boxes | Example 5-6 |
| Store one value per account without requiring an opt-in | Example 4-10 |
| Store several named values per account in local state | Example 4-11 |
| Store several related fields in one state slot | Example 4-12 |
| Take a fee from an incoming payment and forward the remainder | Example 7-13 |
| Tell the difference between a state key set to zero and one never set | Example 4-5 |
| Test time-dependent behaviour without waiting or deploying | Example 8-14 |
| The checks a LogicSig cannot ship without | Example 20-3 |
| The corrected fee splitter, caller-funded fees and accounted dust | Example 11-17 |
| The corrected pay-to-post board, every authorization guard in place | Example 10-17 |
| The hash that is expensive here and cheap inside a proof | Example 22-8 |
| The LogicSig version of trusting caller-supplied input | Example 20-10 |
| Transfer ASA units from a contract to an account | Example 7-18 |
| Treat raw bytes as an ARC-4 value safely | Example 3-8 |
| Turn a number into exactly eight bytes and read it back | Example 3-5 |
| Turn a program counter into the Python statement that produced it | Example 8-12 |
| Understand what ARC4Contract generates for me | Example 2-5 |
| Understand what happens to local state on a clear-state transaction | Example 4-20 |
| Understand why an array assignment needs .copy() | Example 9-2 |
| Understand why divmodw is the more dangerous wide division | Example 6-9 |
| Understand why two BoxMaps can overwrite each other | Example 5-9 |
| Update one field of a stored record without re-encoding it | Example 4-14 |
| Update part of a box without rewriting the whole thing | Example 5-16 |
| Use raw box operations on one entry of a BoxMap | Example 5-14 |
| Validate an incoming ASA transfer against a stored asset id | Example 7-8 |
| Verify a signature a quantum computer is not expected to forge | Example 22-10 |
| Work out how many box references an app call needs | Example 5-12 |
| Work out what an application's declared schema costs, and who pays it | Example 11-2 |
| Work out what an application's extra program pages cost | Example 11-3 |
| Write an integration test that deploys and calls a contract | Example 1-3 |
| Write bytes into a transaction's log | Example 24-1 |
| Write interaction-before-effects deliberately and see why it is safe | Example 8-7 |
| Write the smallest complete Algorand contract that actually does something | Example 2-2 |
