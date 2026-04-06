## TESTGAP-004 - `tests/test_verify_access.py` misses auth and `--require-materialize` regression branches
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: preprocessing readiness

### Problem
The original ticket is stale: this repo now has a local stubbed regression suite for `scripts/00_verify_access.py`, so the gap is no longer "no tests." The remaining issue is narrower. Current coverage exercises startup shaping, dependency failures, `--auth-only`, and a happy mesh-preflight path, but it does not drive the `CAVEclient` auth/init failure branches, the optional `--require-materialize` outage and invisible-version branches, or the successful token-sync messages. Regressions in those paths would still pass `make test` even though `make verify` remains the first step in `make all`.

### Evidence
- `make verify` still invokes the verify script, and `make all` still starts with `verify`, in [Makefile:108](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L108) and [Makefile:241](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L241).
- A stubbed verify suite already exists in [tests/test_verify_access.py:20](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L20), covering info-lookup failure shaping [tests/test_verify_access.py:34](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L34), auth-only mode [tests/test_verify_access.py:111](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L111), and a happy path [tests/test_verify_access.py:163](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L163).
- The helper always defaults `VERIFY_STUB_CAVE_INIT_MODE` to `ok` in [tests/test_verify_access.py:193](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L193), and although the stubbed `CAVEclient` supports `http401`, network, timeout, and generic init modes in [tests/test_verify_access.py:349](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L349), no test overrides them.
- The stubbed materialize client only returns a successful version/table response in [tests/test_verify_access.py:340](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L340), and no existing test passes `--require-materialize` through `_run_verify()` in [tests/test_verify_access.py:207](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L207).
- The unexercised production branches are the auth-specific HTTP handling in [scripts/00_verify_access.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L118), optional materialize probing in [scripts/00_verify_access.py:143](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L143) and [scripts/00_verify_access.py:378](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L378), invisible-version rejection in [scripts/00_verify_access.py:181](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L181), and token-sync success reporting in [scripts/00_verify_access.py:217](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L217), [scripts/00_verify_access.py:219](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L219), and [src/flywire_wave/auth.py:9](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py#L9).

### Requested Change
Extend [tests/test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py) rather than adding a new module. Add explicit stubbed cases for `CAVEclient` auth/init failures and for the `--require-materialize` path by making the materialize stub configurable for transient HTTP/network failures, invisible versions, and success. Add a success case with `FLYWIRE_TOKEN` plus `cloudvolume` and `fafbseg` stubs that asserts the token-sync outcome message.

### Acceptance Criteria
- A stubbed `CAVEclient` initialization or info lookup `401`/`403` returns exit code `1` and prints the auth-specific guidance about refreshing `FLYWIRE_TOKEN` or the local caveclient token.
- With `--require-materialize`, a transient materialize HTTP or network failure returns exit code `1` and prints the temporary-unavailability guidance.
- With `--require-materialize`, a requested materialization version that is not in the visible version list returns exit code `1` and names the requested version.
- A successful `--require-materialize` path prints `Requested version`, `Materialization versions visible`, `Tables`, and `Materialize access: OK`.
- A successful token-sync path prints either `FlyWire token sync: updated local secret storage` or `FlyWire token sync: already configured`, along with the existing `fafbseg setup: OK` success output.
- All cases run locally with stubs only and require no live FlyWire access.

### Verification
- `./.venv/bin/python -m unittest tests.test_verify_access -v`
- `make test`