\newpage

\part{Foundations}

Part I takes you from an empty directory to a tested contract. Chapter 1 stands up the toolchain and gets a contract deployed and answering before any theory. Chapters 2 through 8 then build the machine one mechanism at a time: what a contract is, how calls reach methods, where state lives, what growth costs, why arithmetic refuses, how value moves, and how to prove all of it with tests. Part I ends with a single-beneficiary vesting contract and the test suite that documents exactly what it still gets wrong.

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Setup}}
```
# From Zero to Deployed

Every chapter in this book ends with something you can run, and most of them make you run things in the middle too. That only works if running things is cheap: a compiler that is one command away, a private network that confirms transactions instantly and resets without ceremony, and a client library that calls your contract the way you call any other Python code. This chapter stands all of that up, and then proves it works by taking one contract --- a contract you will not write a line of --- from an empty directory to a deployed application that answers you by name.

There are no ideas in this chapter. That is deliberate. The mistakes worth making in this book are mistakes about contracts, and you cannot make those while you are still fighting your PATH. Spend the twenty minutes here, once, so that every later failure is an interesting one.

::: {.spec title="What you will stand up"}
By the end of this chapter, on your machine:

1. The toolchain installed and verified, and LocalNet --- a private Algorand network --- running and disposable
2. A scaffolded contract compiled, deployed, and answering method calls from a typed Python client
3. A first test passing, and the edit-compile-deploy-interact-test loop run once end to end
:::

By the end of this chapter you will be able to:

- Install the toolchain and verify every dependency with one command
- Start, stop, and reset a private Algorand network, and say which of those destroys state
- Scaffold a project and name what each generated directory is for
- Compile a contract and name the artifacts the build leaves on disk
- Deploy to LocalNet and call a method through the generated typed client
- Write and run a first integration test against the deployed contract
- Run the five-step loop --- edit, compile, deploy, interact, test --- without consulting this chapter
- Apply three debugging habits when any step refuses

## What You Install, and What Each Piece Is For

Three installations, each with one job. **Python 3.12** runs your contract code, your deployment scripts, and your tests --- this book is validated against 3.12 exactly, not merely "3.12 or later." **Docker** (with Compose v2.5.0 or later) hosts LocalNet, the private Algorand network you will deploy against a hundred times before you ever touch a public one. **AlgoKit** is the command-line tool that drives everything else: scaffolding, compilation, network management, client generation, deployment. Think of it as the `cargo` of Algorand --- one entry point to the whole toolchain.

::: {.setup title="Install once"}
1. Install Python 3.12 and verify with `python3 --version` (or `py -3.12 --version` on Windows).
2. Install Git, and Docker Desktop or Docker Engine with Compose v2.5.0+.
3. Install [Poetry](https://python-poetry.org/docs/#installation), the dependency manager the project template uses: `pipx install poetry`.
4. Install AlgoKit: `pipx install algokit`, or `brew install algorandfoundation/tap/algokit` on macOS.
5. Run `algokit doctor` and fix everything it flags.

Platform variations and every failure mode we know about live in Appendix A.
:::

```console
$ algokit --version
algokit, version 2.10.2
```

This book was validated with AlgoKit 2.10.2 and Python 3.12; the Preface records the full pinned baseline. Newer patch and minor versions usually work, but if a later release changes a scaffolded file or a command's behavior mid-chapter, pin back to the validated versions and finish the chapter before experimenting.

`algokit doctor` checks Python, Docker, Docker Compose, and Git in one pass and prints a line per dependency. Fix every flagged line before continuing --- each one is a failure you would otherwise meet later, mid-walkthrough, wearing a less helpful error message.

## A Network of Your Own

Public blockchains make terrible development environments: real money, four-second finality, faucets that run dry. LocalNet is an entire Algorand network --- consensus node, indexer, key management daemon --- running in Docker containers on your machine, with pre-funded accounts and instant, on-demand blocks. Nothing you do on it costs anything or reaches anyone.

```console
$ algokit localnet start
Starting AlgoKit LocalNet now...
```

Two companion commands earn their keep immediately. `algokit localnet status` tells you whether the containers are actually up --- the first thing to check when anything refuses to connect. `algokit localnet explore` opens Lora, a block explorer pointed at your private network, where you can watch your own transactions land, inspect application state, and browse accounts. You will use it in this chapter to look at a deployment with your own eyes.

Two more commands look similar and are not. `algokit localnet stop` shuts the containers down and *preserves* the ledger --- start again and every application and balance is exactly where you left it. `algokit localnet reset` wipes the network back to genesis: every account, every application, every transaction, gone. Both are cheap; only one is destructive; and this chapter ends by demonstrating the difference, because knowing it is what makes LocalNet feel disposable instead of fragile.

::: {.gotcha #localnet-state-is-disposable topic="Compilation, tooling, and shipping" title="LocalNet reset invalidates every hard-coded app ID"}
`algokit localnet reset` wipes application IDs along with everything else. Any script that hard-codes an app ID stops working the moment you reset, and the error is a confusing "application does not exist" rather than anything about the reset. Re-deploy after every reset, or better, never hard-code the ID: the interact script later in this chapter re-derives it on every run, which is why it survives resets that break its hard-coded cousins.
:::

## Scaffolding a Project

```console
$ mkdir algorand-book && cd algorand-book
$ algokit init -t python --name my-first-contract
```

The wizard asks a few questions even with the template flag; accept the defaults. AlgoKit generates a *workspace* with your contract project nested inside it:

```text
my-first-contract/                     # Workspace root
  .algokit.toml                        # Workspace configuration
  projects/
    my-first-contract/                 # Your contract project
      smart_contracts/
        hello_world/
          contract.py                  # The template contract
          deploy_config.py             # Its deployment script
      .algokit.toml                    # Project configuration
      pyproject.toml                   # Python dependencies
```

The directory that matters is `smart_contracts/hello_world/` --- contract code on the left, deployment configuration on the right. Later chapters rename this directory to match each build (`smart_contracts/token_vesting/`, `smart_contracts/constant_product_pool/`); the layout around it never changes. Move into the project and install its dependencies:

```console
$ cd my-first-contract/projects/my-first-contract
$ algokit project bootstrap all
```

Bootstrap drives Poetry to install three packages you will meet constantly: `algorand-python` (the typed stubs your contract code imports), `puyapy` (the compiler that turns that Python into AVM bytecode), and `algokit-utils` (the client library your scripts and tests use to talk to a network). If your editor underlines imports after this, it is pointed at the wrong interpreter --- Appendix A has the two-line fix.

## The Contract You Did Not Write

The template ships one contract. Open `smart_contracts/hello_world/contract.py` and read it once:

**Example 1-1.** The template contract, exactly as scaffolded

<!-- example: examples/setup/hello_world_contract.py mode=compile -->
<!-- finder: see what algokit init generates before touching anything -->

```python
from algopy import ARC4Contract, String
from algopy.arc4 import abimethod


class HelloWorld(ARC4Contract):
    @abimethod()
    def hello(self, name: String) -> String:
        return "Hello, " + name
```

A class, a decorator, a method that concatenates two strings. Do not study it. Every load-bearing word in this file --- what `ARC4Contract` generates, what `@abimethod` promises callers, what a `String` is on the wire, what happens to the class when nobody is calling it --- is Chapter 2's subject, and Chapter 2 earns those answers by building a contract from an empty file and breaking it. Today this file has one job: to be something the pipeline can chew on.

## Compile: What the Build Leaves Behind

```console
$ algokit project run build
```

*Predict, before you look: what does a build like this have to leave on disk, and who is each piece for? List your guesses.*

When it finishes, look in `smart_contracts/artifacts/hello_world/`. The build left artifacts for three different consumers:

| Artifact | What it is | Who reads it |
|---|---|---|
| `HelloWorld.approval.teal`, `HelloWorld.clear.teal` | The compiled programs, in the AVM's assembly language | The network |
| `HelloWorld.arc56.json` | The app spec: method signatures, types, state schema, error map | Every client and tool |
| `hello_world_client.py` | A generated Python class with a real method per contract method | Your scripts and tests |

(The two `.puya.map` files beside them are source maps --- the compiler's record of which TEAL line came from which Python line. Chapter 8 puts them to work.)

The `.teal` files are what actually runs on chain --- readable assembly, worth a thirty-second scroll now and a real read in Chapter 2. The `.arc56.json` app spec is the contract's public interface as data; it is what you publish so strangers can build against you. The generated *typed client* wraps that spec in Python: your type checker sees the `hello` method and its argument types, and a typo in a method name fails before anything reaches a network.

::: {.gotcha #compile-py-vs-project-build topic="Compilation, tooling, and shipping" title="Compiling a contract is not the same command as building a project"}
`algokit compile py` and `algokit project run build` are not interchangeable. `compile py` compiles one file and drops artifacts wherever you point it; `project run build` runs the pipeline defined in `.algokit.toml`, placing artifacts where the template's scripts expect them and generating the typed client. Use `compile py` here and your deploy step will fail to find the app spec at the path every script in this book assumes.
:::

## Deploy and Call It

The template wired a deployment script when it scaffolded --- `deploy_config.py`, the right-hand file you saw earlier. Run it through AlgoKit:

```console
$ algokit project deploy localnet
Deploying smart contracts from AlgoKit compliant repository
INFO: Deploying app hello_world
INFO: Called hello on HelloWorld (1002) with name=world,
      received: Hello, world
```

Your application ID will differ --- on a fresh LocalNet it is a small number like 1002; only its uniqueness matters. Now open `deploy_config.py` and read what actually happened, because you own every line of it. The script makes three moves: it *deploys* the compiled contract (idempotently --- run the command again and it finds the existing app instead of creating a second one), it *funds* the new application's account with one Algo, and it *calls* `hello("world")` once as a smoke test. That last line of output is your contract answering.

Two facts in that transcript matter for the rest of the book. The application **ID** is how every future call names this contract. And the application has an **address** --- an account the contract itself owns, which is what that one-Algo payment funded. Chapter 2 has a lot to say about both.

Now call it yourself. Create `interact.py` in the project root, next to `pyproject.toml`:

**Example 1-2.** Deploy-or-find the contract, then call it

<!-- example: examples/setup/interact.py mode=script -->
<!-- finder: deploy a contract and call a method from Python -->

```python
"""Find the deployed HelloWorld (deploying if needed) and call it."""

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.hello_world.hello_world_client import (
    HelloWorldFactory,
)


def main() -> None:
    algorand = AlgorandClient.default_localnet()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        HelloWorldFactory, default_sender=deployer.address
    )
    client, _ = factory.deploy()
    print(f"hello_world {client.app_id} lives at {client.app_address}")

    result = client.send.hello(args=("Ada",))
    print(f"returned {result.abi_return!r}")


if __name__ == "__main__":
    main()
```

Twelve working lines, four moves. `AlgorandClient.default_localnet()` points at your LocalNet with no configuration. `from_environment("DEPLOYER")` resolves the *same* deployer account the template's deploy script uses --- on LocalNet it is created in the local wallet and funded automatically; on a public network it would come from a `DEPLOYER_MNEMONIC` environment variable. Because deployment is idempotent *per deployer and app name*, `factory.deploy()` finds the app the CLI just created rather than making another --- which is also why this script re-derives the app ID instead of hard-coding it. And `client.send.hello(args=("Ada",))` is the generated typed client at work: a real method with checked argument types, not a string with a prayer attached.

```console
$ poetry run python interact.py
hello_world 1002 lives at BYL5256Z4EUKDDVONXU6UVYXUPZEUQ6JDL3D76FLN4BXDGMGHRTQ3SXZXA
returned 'Hello, Ada'
```

A program you compiled is running on a network you own, and it knows your name. Run it twice: the ID does not change, because `deploy()` found what it already deployed. Then open Lora (`algokit localnet explore`), look up your application ID, and inspect the transactions you just made. Nothing in this book is more magic than what you are looking at.

## Prove It with Tests

The scaffold does not presume your test runner, so add one:

```console
$ poetry add --group dev pytest
```

Then hold the contract to its one promise. Create `test_hello_world.py` in the project root:

**Example 1-3.** A first test: deploy, call, assert

<!-- example: examples/setup/test_hello_world.py mode=script -->
<!-- finder: write an integration test that deploys and calls a contract -->

```python
"""The template contract, held to its one promise."""

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.hello_world.hello_world_client import (
    HelloWorldFactory,
)


def test_hello_greets_by_name() -> None:
    algorand = AlgorandClient.default_localnet()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        HelloWorldFactory, default_sender=deployer.address
    )
    client, _ = factory.deploy()

    result = client.send.hello(args=("Ada",))

    assert result.abi_return == "Hello, Ada"
```

It is `interact.py` with an assertion where the print was --- an *integration* test, running against the real LocalNet. Run it:

```console
$ poetry run pytest -q
.                                                                [100%]
1 passed in 0.54s
```

One thin test, but the habit it anchors is the book's spine: **a chapter is not finished when the code compiles; it is finished when a test you can rerun says what the code does.** Chapter 8 is entirely about what makes a contract test worth trusting --- including the kind that runs without a network at all. Until then, every chapter ends by running something, and most end by running tests.

## The Loop

You have now run every step this book will ever ask of you. Named and ordered:

| Step | Command | What it proves |
|---|---|---|
| 1. Edit | your editor, `contract.py` | --- |
| 2. Compile | `algokit project run build` | the contract is expressible |
| 3. Deploy | `algokit project deploy localnet` | the network accepts it |
| 4. Interact | `poetry run python interact.py` | a client can drive it |
| 5. Test | `poetry run pytest` | it does what you claim |

**Edit, compile, deploy, interact, test.** Every chapter that follows assumes this loop the way a cookbook assumes you can boil water: "deploy it and call `configure`" will always mean steps 2 through 4 with no further commentary. When a chapter shows a transcript, it was produced by this loop; when something fails, you re-enter the loop at step 1 with better information.

## When a Step Refuses: Three Habits

Something in the loop will refuse eventually --- this chapter ends by making sure you have seen it happen. Three habits cover almost every refusal, and they are worth naming once, here, while the failures are still boring.

**Habit one: read the error before touching anything.** Toolchain errors name their problem more often than you would guess, but only if you read past the traceback's last line. Prove it --- stop the network and try to use it:

```console
$ algokit localnet stop
$ poetry run python interact.py
Traceback (most recent call last):
  ...
  File "/usr/lib/python3.12/urllib/request.py", line 1347, in do_open
    raise URLError(err)
urllib.error.URLError: <urlopen error [Errno 111] Connection refused>
```

Nothing about contracts, nothing about your code: it could not *connect*. The refusal happened before a single byte reached a network, because there is no network. Rerunning it, editing the script, or reinstalling anything would all be motion without information; the error already contains the diagnosis.

**Habit two: ask the chain what it actually thinks.** Your mental model of the network's state and the network's actual state drift apart --- that is what debugging *is*, here. `algokit localnet status` answers "is it even running?" (right now: it is not). Lora answers everything else: is the app deployed, what did the last transaction actually do, what is the state right now. When a transcript in this book surprises you, the explorer is how you settle the argument.

**Habit three: know which commands destroy state, and lean on the ones that do not.** Start the network back up and rerun the script --- but first, predict: *of the app ID and the greeting, which will be the same as before the stop? Write both down.*

```console
$ algokit localnet start
$ poetry run python interact.py
hello_world 1002 lives at BYL5256Z4EUKDDVONXU6UVYXUPZEUQ6JDL3D76FLN4BXDGMGHRTQ3SXZXA
returned 'Hello, Ada'
```

Same ID, same address: **stop preserves the ledger.** Now make the same two predictions for `algokit localnet reset`, run it, and rerun `interact.py` once more. It still succeeds --- `factory.deploy()` quietly re-deploys --- but the ID it prints has changed, because the application it printed last time no longer exists anywhere. That is the whole trade LocalNet offers: nothing on it is precious, so no experiment is expensive. Scripts that re-derive IDs, like yours, survive the reset and never lie to you about what exists; scripts that hard-code IDs break a week later with a confusing error. Write the first kind.

## Before You Continue

Everything below should be true, and each line is checkable right now:

- [ ] `algokit doctor` reports no problems
- [ ] `algokit localnet status` shows the network running
- [ ] `algokit project run build` completes, and the artifacts are in `smart_contracts/artifacts/hello_world/`
- [ ] `algokit project deploy localnet` reports your contract answering `hello`
- [ ] `poetry run python interact.py` greets Ada, and rerunning it reports the same app ID
- [ ] `poetry run pytest -q` passes
- [ ] You have found your application in Lora and looked at its creation transaction
- [ ] You can name the five loop steps, the three habits, and the one command in this chapter that destroys state --- without looking

If any line refuses, Appendix A is the troubleshooting reference; fix it now, because Chapter 2 deploys in its first thousand words and never slows down again.

That is the whole toolchain: a compiler, a disposable network, a typed client, a test runner, and a loop that ties them together. What you do not have yet is any idea what that `HelloWorld` class actually *is* --- what the chain stores when you deploy it, who is allowed to call it, what it can see when they do, and how it can possibly hold money. Chapter 2 builds a contract from an empty file to answer exactly those questions, and breaks it three ways to make the answers stick.
