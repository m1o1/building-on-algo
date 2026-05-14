from security_repros import repros


def test_amm_sender_binding_repro() -> None:
    alice_a = repros.AssetTransfer("alice", "amm_app", 1, 500)
    alice_b = repros.AssetTransfer("alice", "amm_app", 2, 500)
    bob_call = repros.AppCall("bob", 42)

    vulnerable = repros.amm_vulnerable_initial_liquidity(
        alice_a,
        alice_b,
        bob_call,
    )
    hardened = repros.amm_hardened_initial_liquidity(
        alice_a,
        alice_b,
        bob_call,
    )

    assert vulnerable.accepted
    assert "LP tokens to bob" in vulnerable.detail
    assert not hardened.accepted
    assert "asset A sender alice != app sender bob" == hardened.detail


def test_nft_resource_population_repro() -> None:
    vulnerable = repros.nft_create_schedule(False, b"schedule:0")
    hardened = repros.nft_create_schedule(True, b"schedule:0")

    assert not vulnerable.accepted
    assert vulnerable.detail == "missing schedule box for inner-created asset 1001"
    assert hardened.accepted


def test_logicsig_network_binding_repro() -> None:
    vulnerable = repros.logicsig_without_network_binding(77, 77)
    hardened = repros.logicsig_with_network_binding(77, 77, "mainnet", "testnet")

    assert vulnerable.accepted
    assert not hardened.accepted
    assert hardened.detail == "genesis hash mismatch"


def test_zk_proof_binding_repro() -> None:
    vulnerable = repros.proof_vulnerable_admin_hook("admin", "admin", False, False)
    hardened = repros.proof_hardened_binding(False, False, 9)

    assert vulnerable.accepted
    assert not hardened.accepted
    assert hardened.detail == "missing verifier transaction"


def test_reward_bounds_repro() -> None:
    vulnerable = repros.reward_vulnerable_schedule(
        585,
        repros.MAX_REWARD_DURATION,
        0,
    )
    hardened_rate = repros.reward_hardened_schedule(
        585,
        repros.MAX_REWARD_DURATION,
        0,
    )
    hardened_lifetime = repros.reward_hardened_schedule(
        repros.MAX_REWARD_RATE,
        repros.MAX_REWARD_DURATION,
        repros.MAX_REWARD_RATE * repros.MAX_REWARD_DURATION * repros.PRECISION,
    )

    assert vulnerable.accepted
    assert "later accumulator update overflows" in vulnerable.detail
    assert not hardened_rate.accepted
    assert hardened_rate.detail == "reward rate too high"
    assert not hardened_lifetime.accepted
    assert hardened_lifetime.detail == "accumulator capacity overflow"


def test_expected_transcript_is_current() -> None:
    assert repros.render_transcript() == repros.expected_output_path().read_text()
