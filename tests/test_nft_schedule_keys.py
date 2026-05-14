"""Regression tests for Chapter 4's NFT schedule box-key design."""

import struct
from pathlib import Path


BOX_PREFIX = b"v_"
SCHEDULE_VALUE_BYTES = 49
SCHEDULE_BOX_NAME_BYTES = 10
SCHEDULE_BOX_MBR = 2_500 + 400 * (
    SCHEDULE_BOX_NAME_BYTES + SCHEDULE_VALUE_BYTES
)
NFT_ASSET_MBR = 100_000


def schedule_box_key(schedule_id: int) -> bytes:
    return BOX_PREFIX + struct.pack(">Q", schedule_id)


def modeled_created_asset_id(block_txn_counter: int, position: int) -> int:
    """Model the asset-id allocation rule from the ledger semantics."""
    return block_txn_counter + position + 1


def test_schedule_box_key_is_known_before_nft_is_created() -> None:
    schedule_id = 42
    predicted_nft_id = modeled_created_asset_id(1_000, 0)
    actual_nft_id = modeled_created_asset_id(1_001, 0)

    assert predicted_nft_id != actual_nft_id
    assert schedule_box_key(schedule_id) == b"v_" + struct.pack(">Q", 42)


def test_asset_id_derived_box_key_can_drift_between_simulate_and_send() -> None:
    simulated_nft_id = modeled_created_asset_id(10_000, 0)
    actual_nft_id = modeled_created_asset_id(10_001, 0)

    assert schedule_box_key(simulated_nft_id) != schedule_box_key(actual_nft_id)


def test_chapter_mbr_constants_match_schedule_struct_size() -> None:
    assert SCHEDULE_BOX_MBR == 26_100
    assert SCHEDULE_BOX_MBR + NFT_ASSET_MBR == 126_100


def test_chapter_uses_explicit_schedule_box_references() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    chapter = (repo_root / "chapters/04-nfts.md").read_text(encoding="utf-8")

    assert "placeholder_box_key" not in chapter
    assert "box_key(0)" not in chapter
    assert "box_key(nft_id)" not in chapter
    assert "return b\"v_\" + struct.pack(\">Q\", schedule_id)" in chapter
    assert "box_references=[schedule_box]" in chapter
    assert "asset_references=[token_id]" in chapter
    assert "populate_app_call_resources=True" in chapter
