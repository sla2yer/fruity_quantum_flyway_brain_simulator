## TESTGAP-002 - `validation-ladder package` edge cases and baseline writing still lack direct coverage
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: validation ladder packaging

### Problem
The repository now exercises packaged-ladder success behavior through the deterministic smoke fixture, but it still does not directly test the standalone `package` path or its package-specific failure modes. Current coverage does not prove that shuffled input order is normalized, that duplicate layer bundles are rejected, that missing required layers fail clearly, or that `scripts/27_validation_ladder.py package --write-baseline` writes the expected normalized regression snapshot.

### Evidence
- The package workflow is still documented in [docs/pipeline_notes.md:580](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L580) and exposed as [Makefile:191](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L191).
- The CLI has a distinct `package` subcommand plus standalone `--write-baseline` handling in [scripts/27_validation_ladder.py:69](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/27_validation_ladder.py#L69) and [scripts/27_validation_ladder.py:125](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/27_validation_ladder.py#L125).
- The implementation still contains explicit missing-layer and duplicate-layer checks in [src/flywire_wave/validation_reporting.py:570](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L570) and [src/flywire_wave/validation_reporting.py:705](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L705).
- Current ladder-package test coverage is still only the smoke fixture in [tests/test_validation_reporting.py:24](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_reporting.py#L24), and that workflow calls `package_validation_ladder_outputs()` with a fixed four-layer happy-path input order in [src/flywire_wave/validation_ladder_smoke.py:101](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_ladder_smoke.py#L101).
- `milestone13-readiness` now audits that `validation-ladder-package` is on the documented command surface, but its CLI check only runs `scripts/27_validation_ladder.py --help` and validates the generic help output rather than executing `package` with real bundles in [src/flywire_wave/milestone13_readiness.py:649](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L649) and [src/flywire_wave/milestone13_readiness.py:683](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L683).

### Requested Change
Add focused direct regression coverage for `package_validation_ladder_outputs()` and `scripts/27_validation_ladder.py package`, using tiny local layer bundles. Keep the scope limited to the currently untested package-path behaviors rather than duplicating the existing smoke happy path.

### Acceptance Criteria
- Packaging the same layer bundles in different input orders yields the same `bundle_id`, identical summary bytes, and normalized layer ordering.
- Supplying two bundles for the same `layer_id` fails clearly.
- Requiring the full ladder layer set and omitting one layer fails clearly.
- Running `scripts/27_validation_ladder.py package ... --write-baseline ...` writes the normalized regression baseline derived from the packaged summary.

### Verification
- `python -m unittest tests.test_validation_reporting -v` or `python -m unittest tests.test_validation_ladder_package -v`
- `make test`