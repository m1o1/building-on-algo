from __future__ import annotations

import pytest

from scripts.localnet_helpers import (
    PROOF_FILE,
    PUBLIC_INPUTS_FILE,
    VERIFIER_TEAL,
    MissingArtifact,
    get_localnet_algorand,
    load_vote_manifest,
)


@pytest.fixture
def algorand():
    try:
        return get_localnet_algorand()
    except RuntimeError as exc:
        pytest.skip(str(exc))


@pytest.fixture
def zk_artifacts():
    """The generated verifier and one proof, or a skip that says what is missing.

    A reader who has not installed Go has no proof to submit and no verifier to
    submit it to. That is a supported state --- the chapter's Python-only track
    is exactly this --- so the ZK tests skip rather than fail, and they name the
    file they wanted so the skip is actionable.
    """
    missing = [p.name for p in (VERIFIER_TEAL, PROOF_FILE, PUBLIC_INPUTS_FILE) if not p.exists()]
    if missing:
        pytest.skip(
            f"Missing ZK artifacts ({', '.join(missing)}). "
            "See the README's 'Regenerating the ZK artifacts' section."
        )
    try:
        manifest = load_vote_manifest()
    except MissingArtifact as exc:
        pytest.skip(str(exc))

    return {
        "manifest": manifest,
        "proof": PROOF_FILE.read_bytes(),
        "public_inputs": PUBLIC_INPUTS_FILE.read_bytes(),
    }
