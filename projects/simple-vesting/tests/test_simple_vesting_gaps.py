from pathlib import Path

import pytest


APP_SPEC = Path(
    "smart_contracts/artifacts/simple_vesting/SimpleVesting.arc56.json"
)


UINT64_MAX = 2**64 - 1


class TestSimpleVestingGaps:
    def test_production_scale_vesting_math_would_overflow_uint64(self) -> None:
        total = 100_000_000_000_000
        one_year = 31_536_000
        assert total * one_year > UINT64_MAX

    def test_simplified_contract_has_no_revoke_method(self) -> None:
        if not APP_SPEC.exists():
            pytest.skip("Run `algokit project run build` before artifact checks")
        app_spec = APP_SPEC.read_text()
        assert '"name": "revoke"' not in app_spec

    def test_simplified_contract_uses_global_state_for_one_schedule(self) -> None:
        if not APP_SPEC.exists():
            pytest.skip("Run `algokit project run build` before artifact checks")
        app_spec = APP_SPEC.read_text()
        assert '"box": {}' in app_spec
        assert '"beneficiary"' in app_spec
