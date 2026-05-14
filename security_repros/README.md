# Security Repros

These local repros give the review issues executable before/after examples.
They are deterministic Python models, not public-network scripts, so they are
safe to run in any development environment.

Run the transcript:

```bash
python -m security_repros.repros
```

Run the assertions:

```bash
python -m pytest tests/test_security_repros.py -q
```

The transcript is checked in at
[`security_repros/expected_output.txt`](expected_output.txt). The test suite
compares the live output with that file so the documented outputs stay current.

Covered scenarios:

- #2 AMM grouped-transaction sender mismatch
- #3 NFT resource population / placeholder box reference
- #4 delegated LogicSig network binding
- #6 ZK proof verifier/public-input binding
- #12 reward arithmetic bounds and lifetime accumulator capacity
