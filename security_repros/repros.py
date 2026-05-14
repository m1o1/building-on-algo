"""Runnable local reproductions for book security review issues.

These are deterministic models of the vulnerable and hardened checks. They are
not a substitute for LocalNet walkthroughs, but they make each security
property executable and keep the expected before/after behavior stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SECONDS_PER_DAY = 86_400
PRECISION = 10**9
MAX_UINT64 = 2**64 - 1
MAX_REWARD_DURATION = 365 * SECONDS_PER_DAY
MAX_REWARD_RATE = 584


@dataclass(frozen=True)
class Result:
    accepted: bool
    detail: str

    @property
    def status(self) -> str:
        return "ACCEPTED" if self.accepted else "REJECTED"


@dataclass(frozen=True)
class AssetTransfer:
    sender: str
    receiver: str
    asset_id: int
    amount: int


@dataclass(frozen=True)
class AppCall:
    sender: str
    app_id: int


def amm_vulnerable_initial_liquidity(
    a_txn: AssetTransfer,
    b_txn: AssetTransfer,
    app_call: AppCall,
) -> Result:
    if a_txn.receiver != "amm_app" or b_txn.receiver != "amm_app":
        return Result(False, "deposit receiver is not the AMM app")
    return Result(
        True,
        f"minted LP tokens to {app_call.sender}; deposits funded by {a_txn.sender}",
    )


def amm_hardened_initial_liquidity(
    a_txn: AssetTransfer,
    b_txn: AssetTransfer,
    app_call: AppCall,
) -> Result:
    if a_txn.sender != app_call.sender:
        return Result(
            False,
            f"asset A sender {a_txn.sender} != app sender {app_call.sender}",
        )
    if b_txn.sender != app_call.sender:
        return Result(
            False,
            f"asset B sender {b_txn.sender} != app sender {app_call.sender}",
        )
    return amm_vulnerable_initial_liquidity(a_txn, b_txn, app_call)


def nft_create_schedule(populate_resources: bool, placeholder_box: bytes) -> Result:
    created_asset_id = 1_001
    required_box = f"schedule:{created_asset_id}".encode()
    boxes = {placeholder_box}
    if populate_resources:
        boxes.add(required_box)
    if required_box not in boxes:
        return Result(
            False,
            "missing schedule box for inner-created asset 1001",
        )
    return Result(True, "resource population added schedule:1001 box reference")


def logicsig_without_network_binding(
    expected_app_id: int,
    txn_app_id: int,
) -> Result:
    if txn_app_id != expected_app_id:
        return Result(False, "wrong app id")
    return Result(True, "app id matched, but network was not checked")


def logicsig_with_network_binding(
    expected_app_id: int,
    txn_app_id: int,
    expected_genesis: str,
    actual_genesis: str,
) -> Result:
    if txn_app_id != expected_app_id:
        return Result(False, "wrong app id")
    if actual_genesis != expected_genesis:
        return Result(False, "genesis hash mismatch")
    return Result(True, "app id and genesis hash matched")


def proof_vulnerable_admin_hook(
    sender: str,
    admin: str,
    verifier_present: bool,
    public_inputs_match: bool,
) -> Result:
    if sender != admin:
        return Result(False, "only admin")
    return Result(
        True,
        "admin marked proof verified without checking verifier/public inputs",
    )


def proof_hardened_binding(
    verifier_present: bool,
    public_inputs_match: bool,
    group_size: int,
) -> Result:
    if group_size != 9:
        return Result(False, "unexpected proof group size")
    if not verifier_present:
        return Result(False, "missing verifier transaction")
    if not public_inputs_match:
        return Result(False, "public inputs do not match on-chain state")
    return Result(True, "verifier group and public inputs matched")


def reward_vulnerable_schedule(rate: int, duration: int, accumulator: int) -> Result:
    increment = rate * duration * PRECISION
    if accumulator + increment > MAX_UINT64:
        return Result(
            True,
            "deposit accepted, but later accumulator update overflows",
        )
    return Result(True, "deposit accepted")


def reward_hardened_schedule(rate: int, duration: int, accumulator: int) -> Result:
    if duration > MAX_REWARD_DURATION:
        return Result(False, "reward duration too long")
    if rate > MAX_REWARD_RATE:
        return Result(False, "reward rate too high")
    increment = rate * duration * PRECISION
    if accumulator + increment > MAX_UINT64:
        return Result(False, "accumulator capacity overflow")
    return Result(True, "reward schedule accepted")


def transcript_lines() -> list[str]:
    alice_a = AssetTransfer("alice", "amm_app", 1, 500)
    alice_b = AssetTransfer("alice", "amm_app", 2, 500)
    bob_call = AppCall("bob", 42)

    cases = [
        (
            "#2 AMM sender binding vulnerable",
            amm_vulnerable_initial_liquidity(alice_a, alice_b, bob_call),
        ),
        (
            "#2 AMM sender binding hardened",
            amm_hardened_initial_liquidity(alice_a, alice_b, bob_call),
        ),
        (
            "#3 NFT resource population vulnerable",
            nft_create_schedule(False, b"schedule:0"),
        ),
        (
            "#3 NFT resource population hardened",
            nft_create_schedule(True, b"schedule:0"),
        ),
        (
            "#4 LogicSig network binding vulnerable",
            logicsig_without_network_binding(77, 77),
        ),
        (
            "#4 LogicSig network binding hardened",
            logicsig_with_network_binding(77, 77, "mainnet", "testnet"),
        ),
        (
            "#6 ZK proof binding vulnerable",
            proof_vulnerable_admin_hook("admin", "admin", False, False),
        ),
        (
            "#6 ZK proof binding hardened",
            proof_hardened_binding(False, False, 9),
        ),
        (
            "#12 reward bounds vulnerable",
            reward_vulnerable_schedule(585, MAX_REWARD_DURATION, 0),
        ),
        (
            "#12 reward bounds hardened",
            reward_hardened_schedule(585, MAX_REWARD_DURATION, 0),
        ),
        (
            "#12 reward lifetime capacity hardened",
            reward_hardened_schedule(
                MAX_REWARD_RATE,
                MAX_REWARD_DURATION,
                MAX_REWARD_RATE * MAX_REWARD_DURATION * PRECISION,
            ),
        ),
    ]

    return [f"{name}: {result.status} - {result.detail}" for name, result in cases]


def render_transcript() -> str:
    return "\n".join(transcript_lines()) + "\n"


def expected_output_path() -> Path:
    return Path(__file__).with_name("expected_output.txt")


def main() -> None:
    print(render_transcript(), end="")


if __name__ == "__main__":
    main()
