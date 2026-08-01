import algokit_utils
import pytest
from algosdk.atomic_transaction_composer import TransactionWithSigner

from scripts.localnet_helpers import (
    advance_time,
    create_test_asa,
    fund_account,
    opt_account_into_asset,
    random_note,
    setup_initialized_contract,
    simulate_expecting_logic_error,
    deploy,
)
from smart_contracts.artifacts.simple_vesting.simple_vesting_client import (
    InitializeArgs,
    OptInToAssetArgs,
)


class TestSimpleVesting:
    def test_create_sets_admin(self, algorand, admin) -> None:
        app_client = deploy(algorand, admin)
        result = app_client.send.get_admin(
            params=algokit_utils.CommonAppCallParams(note=random_note())
        )
        assert result.abi_return == admin.address

    def test_initialize_deposits_tokens(self, algorand, admin) -> None:
        total = 1_000_000
        app_client, token_id, _ = setup_initialized_contract(
            algorand, admin, cliff=5, vesting=20, total=total
        )
        info = algorand.client.algod.account_asset_info(
            app_client.app_address, token_id
        )
        assert info["asset-holding"]["amount"] == total

    def test_claim_before_cliff_returns_zero(self, algorand, admin) -> None:
        app_client, _, beneficiary = setup_initialized_contract(
            algorand, admin, cliff=8, vesting=30, total=1_000_000
        )
        result = app_client.send.claim(
            params=algokit_utils.CommonAppCallParams(
                sender=beneficiary.address,
                static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
                note=random_note(),
            )
        )
        assert result.abi_return == 0

    def test_claim_after_cliff_returns_proportional(self, algorand, admin) -> None:
        total = 1_000_000
        app_client, token_id, beneficiary = setup_initialized_contract(
            algorand, admin, cliff=3, vesting=12, total=total
        )
        advance_time(algorand, 5)
        result = app_client.send.claim(
            params=algokit_utils.CommonAppCallParams(
                sender=beneficiary.address,
                static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
                note=random_note(),
            )
        )
        assert result.abi_return > 0
        assert result.abi_return < total
        info = algorand.client.algod.account_asset_info(
            beneficiary.address, token_id
        )
        assert info["asset-holding"]["amount"] == result.abi_return

    def test_claim_after_full_vesting_returns_total(self, algorand, admin) -> None:
        total = 1_000_000
        app_client, _, beneficiary = setup_initialized_contract(
            algorand, admin, cliff=2, vesting=5, total=total
        )
        advance_time(algorand, 6)
        result = app_client.send.claim(
            params=algokit_utils.CommonAppCallParams(
                sender=beneficiary.address,
                static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
                note=random_note(),
            )
        )
        assert result.abi_return == total

    def test_simulate_non_admin_initialize(self, algorand, admin) -> None:
        app_client = deploy(algorand, admin)
        token_id = create_test_asa(algorand, admin)
        imposter = algorand.account.random()
        fund_account(algorand, admin, imposter.address)
        opt_account_into_asset(algorand, imposter, token_id)
        # The imposter needs the tokens the deposit transaction moves. Without
        # them the group dies on an asset-balance underflow in transaction 0
        # and never reaches the admin check this test is about.
        algorand.send.asset_transfer(
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=imposter.address,
                asset_id=token_id,
                amount=1_000_000,
                note=random_note(),
            )
        )

        fund_account(algorand, admin, app_client.app_address, amount=300_000)
        app_client.send.opt_in_to_asset(
            OptInToAssetArgs(asset=token_id),
            params=algokit_utils.CommonAppCallParams(
                static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
                note=random_note(),
            ),
        )

        deposit_txn = algorand.create_transaction.asset_transfer(
            algokit_utils.AssetTransferParams(
                sender=imposter.address,
                receiver=app_client.app_address,
                asset_id=token_id,
                amount=1_000_000,
                note=random_note(),
            )
        )
        deposit_arg = TransactionWithSigner(
            deposit_txn,
            algorand.account.get_signer(imposter.address),
        )

        message = simulate_expecting_logic_error(
            lambda: app_client.new_group()
            .initialize(
                InitializeArgs(
                    asset=token_id,
                    beneficiary=imposter.address,
                    total_amount=1_000_000,
                    cliff_duration=5,
                    vesting_duration=20,
                    deposit_txn=deposit_arg,
                ),
                params=algokit_utils.CommonAppCallParams(
                    sender=imposter.address,
                    static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
                    note=random_note(),
                ),
            )
            .simulate()
        )
        assert "Only admin" in message

    def test_only_beneficiary_can_claim(self, algorand, admin) -> None:
        app_client, _, _ = setup_initialized_contract(
            algorand, admin, cliff=2, vesting=8, total=1_000_000
        )
        advance_time(algorand, 3)

        attacker = algorand.account.random()
        fund_account(algorand, admin, attacker.address)

        with pytest.raises(Exception):
            app_client.send.claim(
                params=algokit_utils.CommonAppCallParams(
                    sender=attacker.address,
                    static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
                    note=random_note(),
                )
            )
