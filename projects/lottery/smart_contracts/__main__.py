import dataclasses
import importlib
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from shutil import rmtree

from algokit_utils.config import config
from dotenv import load_dotenv

config.configure(debug=True, trace_all=False)

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s %(levelname)-10s: %(message)s"
)
logger = logging.getLogger(__name__)
logger.info("Loading .env")
load_dotenv()

root_path = Path(__file__).parent


@dataclasses.dataclass
class SmartContract:
    path: Path
    name: str
    deploy: Callable[[], None] | None = None


def import_contract(folder: Path) -> Path:
    contract_path = folder / "contract.py"
    if contract_path.exists():
        return contract_path
    raise Exception(f"Contract not found in {folder}")


def import_deploy_if_exists(folder: Path) -> Callable[[], None] | None:
    try:
        module_name = f"{folder.parent.name}.{folder.name}.deploy_config"
        deploy_module = importlib.import_module(module_name)
        return deploy_module.deploy  # type: ignore[no-any-return, misc]
    except ImportError:
        return None


def has_contract_file(directory: Path) -> bool:
    return (directory / "contract.py").exists()


contracts: list[SmartContract] = [
    SmartContract(
        path=import_contract(folder),
        name=folder.name,
        deploy=import_deploy_if_exists(folder),
    )
    for folder in root_path.iterdir()
    if (
        folder.is_dir()
        and has_contract_file(folder)
        and not folder.name.startswith("_")
    )
]

deployment_extension = "py"


def _get_output_path(output_dir: Path, deployment_extension: str) -> Path:
    return output_dir / Path(
        "{contract_name}"
        + ("_client" if deployment_extension == "py" else "Client")
        + f".{deployment_extension}"
    )


def _snake_case(name: str) -> str:
    """`BeaconStub` -> `beacon_stub`, matching algokit's naming."""
    out = ""
    for index, char in enumerate(name):
        if char.isupper() and index:
            out += "_"
        out += char.lower()
    return out


def build(output_dir: Path, contract_path: Path) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        rmtree(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    logger.info(f"Exporting {contract_path} to {output_dir}")

    compiler_flags = [
        str(contract_path.resolve()),
        f"--out-dir={output_dir}",
        "--output-source-map",
        # Pinned here rather than left to the compiler default so a reader
        # cannot forget it. PuyaPy 5.x defaults to AVM 11; every contract in
        # this book targets 12.
        "--target-avm-version=13",
    ]

    build_result = subprocess.run(
        ["algokit", "--no-color", "compile", "python", *compiler_flags],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # `algokit compile python` shells out to a pipx-installed PuyaPy. On a
    # machine that has PuyaPy as an ordinary dependency but no pipx -- which
    # is every Poetry-only environment -- it exits 2 before compiling
    # anything. The module entry point takes the same flags, so fall back to
    # it rather than telling the reader to install a second package manager.
    if build_result.returncode and "pipx" in build_result.stdout:
        logger.warning("algokit could not find pipx; using `python -m puyapy`")
        build_result = subprocess.run(
            [sys.executable, "-m", "puyapy", *compiler_flags],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if build_result.stdout:
        print(build_result.stdout)

    if build_result.returncode:
        raise Exception(f"Could not build contract:\n{build_result.stdout}")

    app_spec_file_names: list[str] = [
        file.name for file in output_dir.glob("*.arc56.json")
    ]

    client_file: str | None = None
    if not app_spec_file_names:
        logger.warning(
            "No '*.arc56.json' file found. Skipping client generation."
        )
    else:
        for file_name in app_spec_file_names:
            client_file = file_name
            print(file_name)
            generator_flags = [
                str(output_dir),
                "--output",
                str(_get_output_path(output_dir, deployment_extension)),
            ]
            generate_result = subprocess.run(
                ["algokit", "generate", "client", *generator_flags],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Same pipx dependency as the compiler above, same fallback.
            if generate_result.returncode and "pipx" in generate_result.stdout:
                logger.warning(
                    "algokit could not find pipx; "
                    "using `python -m algokit_client_generator`"
                )
                # The module CLI takes named arguments where the algokit
                # subcommand takes the spec positionally, and it does not
                # expand the `{contract_name}` placeholder that the
                # subcommand substitutes -- left alone it writes a file
                # called `{contract_name}_client.py`.
                contract_class = file_name.removesuffix(".arc56.json")
                generate_result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "algokit_client_generator",
                        "--app_spec",
                        str(output_dir / file_name),
                        "--output",
                        str(
                            _get_output_path(
                                output_dir, deployment_extension
                            )
                        ).replace(
                            "{contract_name}", _snake_case(contract_class)
                        ),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

            if generate_result.stdout:
                print(generate_result.stdout)

            if generate_result.returncode:
                if "No such command" in generate_result.stdout:
                    raise Exception(
                        "Could not generate typed client; update AlgoKit."
                    )
                raise Exception(
                    f"Could not generate typed client:\n{generate_result.stdout}"
                )
    if client_file:
        return output_dir / client_file
    return output_dir


def main(action: str, contract_name: str | None = None) -> None:
    artifact_path = root_path / "artifacts"
    filtered_contracts = [
        contract
        for contract in contracts
        if contract_name is None or contract.name == contract_name
    ]

    match action:
        case "build":
            for contract in filtered_contracts:
                logger.info(f"Building app at {contract.path}")
                build(artifact_path / contract.name, contract.path)
        case "deploy":
            for contract in filtered_contracts:
                output_dir = artifact_path / contract.name
                app_spec_file_name = next(
                    (
                        file.name
                        for file in output_dir.iterdir()
                        if file.is_file() and file.suffixes == [".arc56", ".json"]
                    ),
                    None,
                )
                if app_spec_file_name is None:
                    raise Exception("Could not deploy app; .arc56.json missing")
                if contract.deploy:
                    logger.info(f"Deploying app {contract.name}")
                    contract.deploy()
        case "all":
            for contract in filtered_contracts:
                logger.info(f"Building app at {contract.path}")
                build(artifact_path / contract.name, contract.path)
                if contract.deploy:
                    logger.info(f"Deploying {contract.name}")
                    contract.deploy()
        case _:
            logger.error(f"Unknown action: {action}")


if __name__ == "__main__":
    if len(sys.argv) > 2:
        main(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main("all")
