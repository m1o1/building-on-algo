\newpage



\part{Appendices}

The appendices are the parts of the book you come back to rather than read through. Appendix A is the environment reference --- troubleshooting, connecting to already-deployed applications, and the exact versions this book was validated against. Appendix B is the one-page protocol reference --- every limit, cost, and budget that constrains what a contract can do. Appendix C collects every gotcha in the book into a single list, grouped by topic and linked back to the chapter that explains it. Appendix D is the Example Finder: every numbered example in the book, listed by the task it performs rather than by its caption, so you can look one up by what you are trying to do.

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Appendix A: Environment Reference {-}

Chapter 1 is the walkthrough --- empty directory to deployed, tested contract. This appendix is what you come back to when something in that walkthrough (or any later chapter) refuses: the failure modes we know about, the recipe for talking to a contract you did not deploy, and the exact toolchain versions the book was validated against.

## The Validated Baseline {-}

Every walkthrough and example in this book was validated with the versions in Table A-1.

: Table A-1. Validated toolchain versions

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 | Exactly 3.12 for walkthroughs; the toolchain accepts newer, the book pins |
| AlgoKit | 2.10.2 | Newer patch/minor versions usually work |
| Docker Compose | v2.5.0+ | LocalNet requirement |
| Poetry | 2.x | Installed separately; bootstrap drives it |
| PuyaPy | 5.8.1 | The pinned compiler; the repository's harness compiles every example with it |
| `algorand-python` | 3.5.0 | Installed by the template; the book pins this exact version |
| `algokit-utils` | 4.2.3 | Installed by the template |
| `algorand-python-testing` | 1.1.0 | Unit-test emulator (Chapter 8) |

If a later AlgoKit release changes scaffolded files or command behavior mid-chapter, pin back to this baseline, finish the chapter, then experiment. Pinning back: `pipx install --force 'algokit==2.10.2'`, and for a scaffolded project, set the dependency versions above in `pyproject.toml` and re-run `algokit project bootstrap all`.

AlgoKit supports Python 3.12 or later. If your system default is newer, install 3.12 alongside it and point the project at it before bootstrapping: `poetry env use 3.12` (or `poetry env use <path-to-python-3.12>`) from the contract project directory.

## Troubleshooting the Toolchain {-}

Work down this list in order; each entry names the symptom first.

**`algokit doctor` flags a dependency.** Fix every flagged line before doing anything else. The doctor checks Python, Docker, Docker Compose, and Git; a flag here is the root cause of most downstream failures.

**`algokit project bootstrap all` fails immediately.** The most common cause is Poetry not being installed or not on your PATH --- the template's build and deploy commands all run through `poetry run`. Install it (`pipx install poetry`) and re-run bootstrap. Bootstrap is safe to re-run at any time.

**`Connection refused` (URLError, errno 111) from any script or test.** Nothing is listening where the client is pointing --- almost always LocalNet not running. `algokit localnet start`, then `algokit localnet status` to confirm all containers are up. If containers refuse to start, check Docker itself is running, then check for port conflicts: LocalNet needs 4001 (algod), 4002 (kmd), and 8980 (indexer).

**"application does not exist" after a working session.** You (or `algokit localnet reset`) destroyed the application, and something is still holding its ID --- a hard-coded constant, a stale `.env` entry, a cached client. Re-deploy and re-derive the ID. Scripts that call `factory.deploy()` on every run (Chapter 1's `interact.py` pattern) self-heal; scripts with pasted IDs do not.

**VS Code underlines `import algokit_utils` (or any project import).** The editor is pointed at the wrong Python environment. Open the Command Palette, run **Python: Select Interpreter**, and choose the `.venv` inside your contract project directory (where bootstrap installed dependencies). Alternatively, open the contract project folder directly instead of the workspace root; AlgoKit's generated `.vscode/settings.json` already points at the right interpreter.

**The template asks wizard questions the book did not mention.** Template versions evolve. Accept defaults unless a chapter says otherwise; the book's walkthroughs assume default answers.

**Artifacts are missing from `smart_contracts/artifacts/`.** You compiled with `algokit compile py` instead of `algokit project run build`, or the build failed above the fold. `compile py` compiles one file and drops artifacts wherever you point it; `project run build` runs the template's pipeline and puts artifacts where every script in this book expects them. Scroll up to the first error, fix it, re-run the build.

## Connecting to an Already-Deployed Contract {-}

Chapter 1's `interact.py` deploys-or-finds a contract *you* built, using the typed client the build generated. The other situation --- a frontend, a backend service, an integration --- is connecting to a contract that is already on chain, possibly deployed by someone else. Then you have an application ID and (if the deployer published it) an app spec, and you skip deployment entirely:

```python
from pathlib import Path

import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
caller = algorand.account.localnet_dispenser()

app_spec = Path("HelloWorld.arc56.json").read_text()
app_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec,
    app_id=1002,  # the deployed contract's application ID
    default_sender=caller.address,
)

result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(method="hello", args=["World"])
)
print(result.abi_return)  # Hello, World
```

This is the *generic* client: method names are strings, arguments are untyped, and typos surface at runtime. It is the one place this book departs from typed clients, and the reason is structural --- when you did not build the contract, there may be no generated client to import, and the app spec is the only interface you have. If the deployer published a generated client (or you can run `algokit generate client` against their app spec), prefer it and use `get_typed_app_client_by_id` the same way.

Swap `default_localnet()` for `AlgorandClient.testnet()` or `.mainnet()` --- or `from_environment()` with the right variables set --- and the same recipe talks to public networks.

## Other Languages and AI Tooling {-}

This book uses Algorand Python (PuyaPy) exclusively, but the same Puya compiler backend also accepts **Algorand TypeScript**: scaffold with `algokit init -t typescript` and every AVM concept, security pattern, and architectural decision in this book applies unchanged --- only syntax differs. (TEALScript, an older TypeScript option, is legacy.)

For AI-assisted development, **VibeKit** (`vibekit init`) configures AI coding agents (Claude Code, Cursor, VS Code Copilot) for Algorand work: agent skills, documentation lookup, and blockchain interaction tools, with private keys kept isolated from the language model. It complements AlgoKit rather than replacing it --- AlgoKit is the build system; VibeKit teaches your AI assistant to drive it. See [getvibekit.ai](https://getvibekit.ai).
