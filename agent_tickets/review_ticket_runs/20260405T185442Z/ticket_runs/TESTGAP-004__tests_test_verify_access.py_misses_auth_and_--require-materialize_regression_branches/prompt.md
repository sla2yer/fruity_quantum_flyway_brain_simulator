Work ticket TESTGAP-004: `tests/test_verify_access.py` misses auth and `--require-materialize` regression branches.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: testing_and_verification_gaps review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The original ticket is stale: this repo now has a local stubbed regression suite for `scripts/00_verify_access.py`, so the gap is no longer "no tests." The remaining issue is narrower. Current coverage exercises startup shaping, dependency failures, `--auth-only`, and a happy mesh-preflight path, but it does not drive the `CAVEclient` auth/init failure branches, the optional `--require-materialize` outage and invisible-version branches, or the successful token-sync messages. Regressions in those paths would still pass `make test` even though `make verify` remains the first step in `make all`.

Requested Change:
Extend [tests/test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py) rather than adding a new module. Add explicit stubbed cases for `CAVEclient` auth/init failures and for the `--require-materialize` path by making the materialize stub configurable for transient HTTP/network failures, invisible versions, and success. Add a success case with `FLYWIRE_TOKEN` plus `cloudvolume` and `fafbseg` stubs that asserts the token-sync outcome message.

Acceptance Criteria:
- A stubbed `CAVEclient` initialization or info lookup `401`/`403` returns exit code `1` and prints the auth-specific guidance about refreshing `FLYWIRE_TOKEN` or the local caveclient token.
- With `--require-materialize`, a transient materialize HTTP or network failure returns exit code `1` and prints the temporary-unavailability guidance.
- With `--require-materialize`, a requested materialization version that is not in the visible version list returns exit code `1` and names the requested version.
- A successful `--require-materialize` path prints `Requested version`, `Materialization versions visible`, `Tables`, and `Materialize access: OK`.
- A successful token-sync path prints either `FlyWire token sync: updated local secret storage` or `FlyWire token sync: already configured`, along with the existing `fafbseg setup: OK` success output.
- All cases run locally with stubs only and require no live FlyWire access.

Verification:
- `./.venv/bin/python -m unittest tests.test_verify_access -v`
- `make test`
