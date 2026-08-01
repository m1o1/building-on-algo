from algopy import (
    ARC4Contract,
    Application,
    Asset,
    BoxMap,
    Bytes,
    Global,
    Txn,
    UInt64,
    arc4,
    compile_contract,
    gtxn,
    itxn,
    op,
    subroutine,
)

from smart_contracts.factory_pool.contract import FactoryPool

FACTORY_CREATE_SEED = 1_500_000
POOL_BOOTSTRAP_FUNDING = 500_000


@subroutine
def _pair_key(asset_a_id: UInt64, asset_b_id: UInt64) -> Bytes:
    return op.itob(asset_a_id) + op.itob(asset_b_id)


class AMMFactory(ARC4Contract):
    def __init__(self) -> None:
        self.pools = BoxMap(Bytes, UInt64, key_prefix=b"p_")
        self.lp_tokens = BoxMap(Bytes, UInt64, key_prefix=b"l_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        pass

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod
    def create_pool(
        self,
        seed_payment: gtxn.PaymentTransaction,
        asset_a: Asset,
        asset_b: Asset,
    ) -> tuple[UInt64, UInt64]:
        """Create and register the canonical pool for an ordered asset pair."""
        assert Global.group_size == UInt64(2), "Create pool group must be size 2"
        assert asset_a.id < asset_b.id, "Assets must be in canonical order"
        assert seed_payment.sender == Txn.sender, "Seed sender mismatch"
        assert seed_payment.receiver == Global.current_application_address
        assert seed_payment.amount >= UInt64(FACTORY_CREATE_SEED), "Seed too small"

        key = _pair_key(asset_a.id, asset_b.id)
        existing_pool, exists = self.pools.maybe(key)
        assert not exists, "Pool already exists"

        compiled_pool = compile_contract(FactoryPool)
        create_txn = itxn.ApplicationCall(
            approval_program=compiled_pool.approval_program,
            clear_state_program=compiled_pool.clear_state_program,
            global_num_uint=compiled_pool.global_uints,
            global_num_bytes=compiled_pool.global_bytes,
            local_num_uint=compiled_pool.local_uints,
            local_num_bytes=compiled_pool.local_bytes,
            extra_program_pages=compiled_pool.extra_program_pages,
            fee=UInt64(0),
        ).submit()
        pool_app = create_txn.created_app

        itxn.Payment(
            receiver=pool_app.address,
            amount=UInt64(POOL_BOOTSTRAP_FUNDING),
            fee=UInt64(0),
        ).submit()

        bootstrap_txn = itxn.ApplicationCall(
            app_id=pool_app,
            app_args=(
                arc4.arc4_signature("bootstrap(uint64,uint64)uint64"),
                arc4.UInt64(asset_a.id),
                arc4.UInt64(asset_b.id),
            ),
            assets=(asset_a, asset_b),
            fee=UInt64(0),
        ).submit()
        lp_token_id = arc4.UInt64.from_log(bootstrap_txn.last_log).as_uint64()

        self.pools[key] = pool_app.id
        self.lp_tokens[key] = lp_token_id
        return pool_app.id, lp_token_id

    @arc4.abimethod(readonly=True)
    def get_pool(self, asset_a: Asset, asset_b: Asset) -> UInt64:
        assert asset_a.id < asset_b.id, "Assets must be in canonical order"
        return self.pools.get(_pair_key(asset_a.id, asset_b.id), default=UInt64(0))

    @arc4.abimethod(readonly=True)
    def get_lp_token(self, asset_a: Asset, asset_b: Asset) -> UInt64:
        assert asset_a.id < asset_b.id, "Assets must be in canonical order"
        return self.lp_tokens.get(
            _pair_key(asset_a.id, asset_b.id),
            default=UInt64(0),
        )

    @arc4.abimethod(readonly=True)
    def verify_pool(
        self,
        candidate_pool: Application,
        asset_a: Asset,
        asset_b: Asset,
    ) -> bool:
        """Return true only when a pool is factory-created and registered."""
        if asset_a.id >= asset_b.id:
            return False

        key = _pair_key(asset_a.id, asset_b.id)
        registered_pool = self.pools.get(key, default=UInt64(0))
        if registered_pool != candidate_pool.id:
            return False

        if candidate_pool.creator != Global.current_application_address:
            return False

        pool_asset_a, has_asset_a = op.AppGlobal.get_ex_uint64(
            candidate_pool, Bytes(b"asset_a")
        )
        pool_asset_b, has_asset_b = op.AppGlobal.get_ex_uint64(
            candidate_pool, Bytes(b"asset_b")
        )
        pool_factory, has_factory = op.AppGlobal.get_ex_uint64(
            candidate_pool, Bytes(b"factory_app_id")
        )
        pool_lp_token, has_lp_token = op.AppGlobal.get_ex_uint64(
            candidate_pool, Bytes(b"lp_token_id")
        )

        return (
            has_asset_a
            and has_asset_b
            and has_factory
            and has_lp_token
            and pool_asset_a == asset_a.id
            and pool_asset_b == asset_b.id
            and pool_factory == Global.current_application_id.id
            and pool_lp_token == self.lp_tokens.get(key, default=UInt64(0))
        )
