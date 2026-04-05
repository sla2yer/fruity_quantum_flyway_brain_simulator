# Testing And Verification Gaps Review Tickets

## TESTGAP-001 - Resume-state mismatch rejection is not protected
- Status: open
- Priority: high
- Source: testing_and_verification_gaps review
- Area: experiment suite execution

### Problem
A stale `experiment_suite_execution_state.json` can only be resumed safely if it still matches the current suite identity and work-item ordering. That guard exists in code, but there is no test that seeds an incompatible state file and proves the workflow refuses to reuse it. A regression here could silently resume the wrong suite, skip the wrong work items, or reuse stale packaged outputs without `make test` or `make milestone15-readiness` catching it.

### Evidence
- The mismatch checks for `suite_id`, `suite_spec_hash`, and `work_item_order` live in [src/flywire_wave/experiment_suite_execution.py:1366](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1366).
- Existing coverage only exercises the happy-path resume flow in [tests/test_experiment_suite_execution.py:58](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L58).
- The Milestone 15 readiness test only verifies the default readiness report path and does not seed an incompatible persisted state in [tests/test_milestone15_readiness.py:21](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_milestone15_readiness.py#L21).

### Requested Change
Add a deterministic unit test in [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) that writes a persisted execution-state fixture with a mismatched `suite_spec_hash` and a separate fixture with a mismatched `work_item_order`, then asserts `execute_experiment_suite_plan()` fails before any stage executor runs or package output is refreshed.

### Acceptance Criteria
- Reusing a state file with a different `suite_spec_hash` raises a clear `ValueError`.
- Reusing a state file with a different `work_item_order` raises a clear `ValueError`.
- No stage executor is called after either mismatch is detected.
- The mismatched state file is left unchanged after the rejected resume attempt.

### Verification
- `python -m unittest tests.test_experiment_suite_execution -v`
- `make test`

## TESTGAP-002 - `validation-ladder-package` is only covered indirectly through the smoke fixture
- Status: open
- Priority: high
- Source: testing_and_verification_gaps review
- Area: validation ladder packaging

### Problem
The repo documents `scripts/27_validation_ladder.py package` and `make validation-ladder-package` as the path for packaging existing per-layer `validation_bundle.json` artifacts. Current verification only covers the synthetic smoke workflow, not the package path that real numerical, morphology, circuit, and task runs hand off into. A regression in duplicate-layer rejection, required-layer enforcement, input-order normalization, or baseline writing could break real ladder packaging while `make validation-ladder-smoke` and `make milestone13-readiness` still pass.

### Evidence
- The documented package workflow is in [docs/pipeline_notes.md:576](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L576) and the Make target is in [Makefile:186](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L186).
- The package implementation has explicit checks for required layers and duplicate layer IDs in [src/flywire_wave/validation_reporting.py:558](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L558) and [src/flywire_wave/validation_reporting.py:681](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L681).
- Current test coverage only runs the smoke fixture in [tests/test_validation_reporting.py:24](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_reporting.py#L24).
- Milestone 13 readiness also shells only the `smoke` subcommand in [src/flywire_wave/milestone13_readiness.py:487](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L487).

### Requested Change
Add a deterministic packaging test module, preferably [tests/test_validation_ladder_package.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_ladder_package.py), that materializes tiny local layer bundles and directly exercises `package_validation_ladder_outputs()` plus `scripts/27_validation_ladder.py package`. Include one shuffled-order success case, one duplicate-layer failure case, one missing-required-layer failure case, and one `--write-baseline` assertion.

### Acceptance Criteria
- Packaging the same layer bundles in different input orders yields the same `bundle_id`, summary bytes, and layer ordering.
- Supplying two bundles for the same `layer_id` fails clearly.
- Requiring all four ladder layers and omitting one fails clearly.
- `--write-baseline` writes a normalized regression baseline from the packaged summary.

### Verification
- `python -m unittest tests.test_validation_ladder_package -v`
- `make test`

## TESTGAP-003 - `--fail-fast` suite execution behavior is untested
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: experiment suite execution CLI

### Problem
The suite runner exposes a `--fail-fast` mode that should stop scheduling after the first failed or partial work item. That branch is separate from the default resume path and is not exercised by current tests or readiness. A regression could keep launching downstream stages after the first failure, contaminating persisted state and review packages, while the existing orchestration tests still pass.

### Evidence
- The CLI flag is part of the public command surface in [scripts/31_run_experiment_suite.py:50](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/31_run_experiment_suite.py#L50).
- The executor has dedicated `fail_fast` break logic on exceptions and failed or partial statuses in [src/flywire_wave/experiment_suite_execution.py:334](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L334) and [src/flywire_wave/experiment_suite_execution.py:349](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L349).
- No test references `fail_fast`; current suite execution coverage only uses the default behavior in [tests/test_experiment_suite_execution.py:58](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L58).
- Milestone 15 readiness also exercises only the default workflow path in [tests/test_milestone15_readiness.py:41](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_milestone15_readiness.py#L41).

### Requested Change
Extend [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) with a deterministic `fail_fast=True` scenario that forces one simulation work item to fail, then asserts later work items are not attempted. Add one subprocess-style assertion against `scripts/31_run_experiment_suite.py --fail-fast` if the CLI surface is easy to reuse from the same fixture.

### Acceptance Criteria
- With `fail_fast=True`, execution stops after the first failed or partial work item.
- Later work items remain unattempted in the persisted execution state.
- The stage call log proves no downstream executor ran after the first failing item.
- A subsequent non-`fail_fast` rerun can resume from the stopped state.

### Verification
- `python -m unittest tests.test_experiment_suite_execution -v`
- `make test`

## TESTGAP-004 - `make verify` has no stubbed regression coverage for auth, outage, or version handling
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: preprocessing readiness

### Problem
`make all` starts with `make verify`, and `scripts/00_verify_access.py` contains nontrivial classification logic for auth failures, transient materialize outages, `--require-materialize`, missing materialization version `783`, and fafbseg token syncing. None of that is protected by a local deterministic test. A regression could misclassify token failure as a temporary outage or allow the wrong materialization version through without `make test`, `make smoke`, or any readiness command noticing.

### Evidence
- The setup docs make `make verify` part of the normal access check and `make all` entry sequence in [README.md:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L59) and [README.md:88](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L88).
- The verify script contains retry and exit-code logic for auth, transient HTTP/network errors, and materialization visibility in [scripts/00_verify_access.py:36](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L36), [scripts/00_verify_access.py:102](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L102), and [scripts/00_verify_access.py:127](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L127).
- Secret-sync behavior is implemented separately in [src/flywire_wave/auth.py:9](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py#L9).
- No test file references `scripts/00_verify_access.py` or `ensure_flywire_secret`.

### Requested Change
Add a fully local test module, preferably [tests/test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py), that stubs `caveclient`, `requests`, `fafbseg`, and `cloudvolume` and executes `scripts/00_verify_access.py` or `main()` directly. Cover at least: 401 auth failure, transient materialize outage with and without `--require-materialize`, requested materialization version not visible, and successful token-sync plus dataset selection.

### Acceptance Criteria
- Auth failure returns exit code `1` with the auth-specific guidance text.
- Transient materialize unavailability returns `0` by default and `2` with `--require-materialize`.
- Invisible materialization version returns `1` and names the requested version.
- Success path prints the configured datastack, materialization version, and fafbseg token-sync outcome.
- All of the above run without live FlyWire access.

### Verification
- `python -m unittest tests.test_verify_access -v`
- `make test`