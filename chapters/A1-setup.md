\newpage



\part{Appendices}

The appendices are the parts of the book you come back to rather than read through. Appendix A gets a working toolchain onto your machine and takes one contract all the way to a deployed, callable application. Appendix B is the one-page protocol reference — every limit, cost, and budget that constrains what a contract can do. Appendix C collects every gotcha in the book into a single list, grouped by topic and linked back to the chapter that explains it. Appendix D is a cookbook of standalone examples, organized by topic.

# Setting Up Your Development Environment

Everything in this book assumes a working Algorand toolchain: a compiler, a local network to deploy against, and a client library to call contracts from. This appendix installs all three and then proves they work by taking a template contract from source to a deployed application you can call. It takes about twenty minutes on a machine that already has Docker.

Do this once, before {{ch:mental-model}}. Every chapter after it assumes the loop described at the end of this appendix — edit, compile, deploy, interact, test — is already familiar.

The Algorand toolchain is centered on [AlgoKit](https://dev.algorand.co/algokit/algokit-intro/), a CLI that orchestrates project scaffolding, local network management, contract compilation, client generation, and deployment. Think of it as the `cargo` or `create-react-app` of Algorand --- one entry point to the entire toolchain. (See the [AlgoKit Quick Start](https://dev.algorand.co/getting-started/algokit-quick-start/) for installation.)

::: {.note}
For AI-assisted development, the ecosystem also offers **VibeKit** (`vibekit init`), a CLI that configures AI coding agents (Claude Code, Cursor, VS Code Copilot) for Algorand development. VibeKit installs agent skills, documentation lookup tools, and blockchain interaction tools so your AI assistant can write, compile, deploy, and debug contracts within a single conversation --- with private keys kept safely isolated from the language model. VibeKit is complementary to AlgoKit: AlgoKit is the build system, VibeKit teaches your AI how to use it. See [VibeKit](https://getvibekit.ai) for setup.
:::

## What You Need Installed

You need three things: **Python 3.12** (the version validated for this book), **Docker with Compose v2.5.0 or later** (for running a local Algorand network in containers), and **AlgoKit itself**.

AlgoKit supports Python 3.12 or later, but use Python 3.12 for the walkthroughs first. If your system default is newer, install Python 3.12 and tell the generated project to use it before bootstrapping.

Use this setup checklist on Windows, macOS, or Linux.

Install once:

1. Install Python 3.12.

   Verify the interpreter you will use: `python3 --version` on many macOS/Linux setups, `python --version` where configured, or `py -3.12 --version` on Windows.
2. If you install AlgoKit with `pipx`, install `pipx` and make sure its scripts directory is on your `PATH`.
3. Install Git and Docker Desktop or Docker Engine with Compose v2.5.0 or later.
4. Install AlgoKit with `pipx install algokit` or your platform package manager.
5. Run `algokit doctor` and fix every reported dependency problem.
6. Start LocalNet with `algokit localnet start`.

For each new project:

1. Scaffold with `algokit init`.
2. Navigate into the generated contract project directory.
3. If the project uses Poetry and your default Python is not 3.12, run `poetry env use 3.12` or `poetry env use <path-to-python-3.12>`.
4. Run `algokit project bootstrap all`.
5. Verify the active project environment is using Python 3.12 before running tests or scripts.

## Installing AlgoKit

```bash
# macOS (via Homebrew)
brew install algorandfoundation/tap/algokit

# Any platform (via pipx --- recommended if you already manage Python tools this way)
pipx install algokit

# Verify the installation
algokit --version    # Validated with 2.10.2; newer patch/minor versions may work
```

If a later AlgoKit release changes scaffolded files or walkthrough behavior, return to the Preface's validated baseline while debugging.

Run the doctor to check that all dependencies are present and correctly configured:

```bash
algokit doctor
```

This checks for Python, Docker, Docker Compose, git, and other prerequisites. Fix anything it flags before proceeding.

## Starting LocalNet

**LocalNet** is a private Algorand network running in Docker with an algod node, an indexer, and a Key Management Daemon (KMD):

```bash
algokit localnet start
algokit localnet status    # Verify all containers are running
algokit localnet explore   # Open a block explorer UI for your local network
```

The `explore` command opens Lora (a web-based block explorer) pointed at your LocalNet, which is useful for inspecting transactions, accounts, and application state as you develop.

LocalNet gives you instant block finality, pre-funded test accounts (accessible via KMD), and zero dependence on TestNet faucets. Blocks are produced on-demand when transactions are submitted, so there is no waiting. You can reset the entire network to a clean state at any time:

```bash
algokit localnet reset     # Wipes all state, restarts fresh
```

::: {.gotcha #localnet-state-is-disposable topic="Compilation, tooling, and shipping" title="LocalNet reset invalidates every hard-coded app ID"}
`algokit localnet reset` wipes app IDs along with everything else. Any script that hard-codes an application ID --- including the `app_id=1001` shown later in this appendix --- stops working the moment you reset, and the error you get back is a confusing "application does not exist" rather than anything about the reset. Re-deploy after every reset, or read the ID from `deploy_result` instead of pasting it.
:::

## Scaffolding Your First Project

```bash
mkdir algorand-book && cd algorand-book
algokit init -t python --name my-first-contract
```

The template wizard may ask a few questions even with `-t python` --- it may prompt for the language (select Python), and whether to run `algokit project bootstrap`. Accept the defaults for now. AlgoKit generates a *workspace* structure with your contract project nested inside:

```text
my-first-contract/                     # Workspace root
  .algokit.toml                        # Workspace configuration
  my-first-contract.code-workspace     # VS Code workspace file
  projects/
    my-first-contract/                 # Your contract project
      smart_contracts/
        hello_world/
          contract.py                  # Your Algorand Python contract
          deploy_config.py             # Deployment configuration
      .algokit.toml                    # Project configuration
      pyproject.toml                   # Python dependencies
```

The key directory is `projects/my-first-contract/smart_contracts/hello_world/` --- this is where your contract code lives. In subsequent chapters, you will rename this directory to match each project (e.g., `smart_contracts/token_vesting/`, `smart_contracts/constant_product_pool/`). You can also create additional contract directories in the same project. Navigate into the contract project before continuing:

```bash
cd my-first-contract/projects/my-first-contract
```

Install the project's Python dependencies:

```bash
algokit project bootstrap all
```

After bootstrapping, verify the project environment before you run scripts or tests. Use the command style for the environment AlgoKit generated on your platform, such as `python --version`, `python3 --version`, or `py -3.12 --version`; it should report Python 3.12.

This command installs all project dependencies by running the appropriate package manager (Poetry, in the default Python template). It installs `algorand-python` (the type stubs that provide IDE autocompletion and type checking), `puyapy` (the compiler that transforms your Python code into TEAL bytecode), `algokit-utils` (the client library for interacting with Algorand), and testing dependencies. If you already ran bootstrap during `algokit init`, you can skip this step.

::: {.tip}
**VS Code tip.** If VS Code shows import errors (yellow or red squiggly lines under `import algokit_utils`), it does not know which Python environment to use. Open the Command Palette (`Cmd+Shift+P` on macOS, `Ctrl+Shift+P` on Windows/Linux), run **Python: Select Interpreter**, and choose the `.venv` inside your `projects/my-first-contract/` directory. This points VS Code at the virtual environment where `algokit project bootstrap all` installed your dependencies, giving you autocompletion and type checking. Alternatively, open the `projects/my-first-contract/` folder directly in VS Code instead of the workspace root --- its `.vscode/settings.json` is already configured by AlgoKit to use the correct interpreter.
:::

::: {.note}
This book uses Algorand Python (PuyaPy) exclusively, but Algorand smart contracts can also be written in **Algorand TypeScript**, which shares the same Puya compiler backend and produces the same TEAL. If your team prefers TypeScript, scaffold with `algokit init -t typescript`. (TEALScript, an older TypeScript option, is legacy and has been superseded by Algorand TypeScript.) The AVM concepts, security patterns, and architectural decisions taught in this book apply identically regardless of which language you choose --- only the syntax differs.
:::

## Compiling the Contract

Verify the compilation pipeline works by compiling the template contract:

```bash
algokit project run build
```

This should produce files in `smart_contracts/artifacts/hello_world/`: a `.approval.teal` file, a `.clear.teal` file, an `.arc56.json` application specification, and a generated typed client (`_client.py`). The artifacts are placed in a subdirectory matching the contract directory name. If compilation succeeds without errors, your environment is ready.

::: {.gotcha #compile-py-vs-project-build topic="Compilation, tooling, and shipping" title="`algokit compile py` is not `algokit project run build`"}
`algokit compile py` and `algokit project run build` are not interchangeable. `compile py` compiles a standalone file and drops its artifacts wherever you point it; `project run build` runs the whole pipeline defined in `.algokit.toml`, which also places artifacts in the location the template's scripts expect and generates the typed client. Use `compile py` and your deploy script will fail to find the app spec at the path every example in this book assumes.
:::

## Deploying and Calling It

Now deploy the compiled contract to LocalNet and call its method. Create a file called `interact.py` in the project root (next to `pyproject.toml`):

```python
from pathlib import Path
import algokit_utils

# Connect to LocalNet and get a pre-funded account
algorand = algokit_utils.AlgorandClient.default_localnet()
deployer = algorand.account.localnet_dispenser()

# Deploy the contract using the compiled ARC-56 app spec
app_spec_path = Path("smart_contracts/artifacts/hello_world/HelloWorld.arc56.json")
app_spec = app_spec_path.read_text()
factory = algorand.client.get_app_factory(
    app_spec=app_spec,
    default_sender=deployer.address,
)
app_client, deploy_result = factory.deploy()
print(f"Deployed app ID: {app_client.app_id}")
print(f"App address:     {app_client.app_address}")

# Call the hello method
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="hello",
        args=["World"],
    )
)
print(f"Return value:    {result.abi_return}")  # "Hello, World"
```

Run it (make sure LocalNet is running):

```bash
poetry run python interact.py
```

You should see output like:

```text
Deployed app ID: 1001
App address:     W3EP...
Return value:    Hello, World
```

That is the complete development loop: write a contract in Python, compile it to TEAL, deploy it to a running network, and call its methods from a client script. Every project in this book follows the same cycle --- **edit** the contract in `contract.py`, **compile** with `algokit project run build`, **deploy** using AlgoKit Utils, **interact** by calling methods, and **test** with pytest.

## Connecting to an Already-Deployed Contract

The preceding script deploys a fresh contract every time it runs. In practice, you will often want to interact with a contract that is already deployed --- for example, calling a contract on TestNet or MainNet, or reconnecting to a LocalNet contract you deployed earlier. Use `get_app_client_by_id` with the application ID instead of the factory:

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
caller = algorand.account.localnet_dispenser()

# Connect to an already-deployed contract by its application ID
app_spec_path = Path("smart_contracts/artifacts/hello_world/HelloWorld.arc56.json")
app_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec_path.read_text(),
    app_id=1001,  # replace with your contract's app ID
    default_sender=caller.address,
)

# Call methods exactly the same way as before
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="hello",
        args=["World"],
    )
)
print(result.abi_return)  # "Hello, World"
```

You still need the ARC-56 app spec so the client knows the contract's method signatures and ABI encoding, but deployment is skipped entirely. This is the pattern you would use to build a frontend or backend service that talks to a live contract.

The two clients used here --- `get_app_factory` and `get_app_client_by_id` --- are the *generic* clients, where method names are strings and arguments are untyped. {{ch:mental-model}} explains what an ABI call looks like on the wire and why a generated *typed* client is usually the better choice once a contract's API has settled.
