## TESTGAP-003 - `--fail-fast` returned failed/partial stop path lacks direct regression coverage
- Status: open
- Priority: low
- Source: testing_and_verification_gaps review
- Area: experiment suite execution

### Problem
The original gap is no longer accurate as written: the repository now has direct regression coverage for exception-driven `fail_fast=True` stop/resume behavior and for packaging the resulting `ready` work items. The remaining untested branch is narrower: when a stage executor returns `failed` or `partial` status, or is normalized to `partial` because downstream artifacts are missing, `--fail-fast` should stop before any later work items run. That branch is separate from the exception path, so a regression could keep scheduling downstream work after a partial result while current fail-fast tests still pass.

### Evidence
- The public CLI still exposes `--fail-fast` and forwards it directly into workflow execution in [scripts/31_run_experiment_suite.py:51](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/31_run_experiment_suite.py#L51) and [scripts/31_run_experiment_suite.py:66](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/31_run_experiment_suite.py#L66).
- The executor has distinct fail-fast branches for exception handling and for returned failed/partial statuses in [src/flywire_wave/experiment_suite_execution.py:299](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L299), [src/flywire_wave/experiment_suite_execution.py:334](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L334), and [src/flywire_wave/experiment_suite_execution.py:349](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L349).
- Current execution coverage already exercises only the exception-driven fail-fast path and resume recovery in [tests/test_experiment_suite_execution.py:249](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L249).
- Current packaging coverage already exercises fail-fast-ready rollups after that same exception-driven stop in [tests/test_experiment_suite_packaging.py:281](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_packaging.py#L281).
- There is still no direct `WORK_ITEM_STATUS_PARTIAL` fail-fast assertion in [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py), [tests/test_experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_packaging.py), or [tests/test_milestone15_readiness.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_milestone15_readiness.py).

### Requested Change
Extend [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) with a deterministic `fail_fast=True` scenario where one stage returns `WORK_ITEM_STATUS_PARTIAL` or reports success with a missing downstream artifact so the executor normalizes it to `partial`. Assert that later work items are not attempted, then confirm a subsequent non-`fail_fast` rerun resumes from the stopped state. A subprocess-style CLI assertion for `scripts/31_run_experiment_suite.py --fail-fast` is optional and should stay limited to flag plumbing if the existing fixture is easy to reuse.

### Acceptance Criteria
- With `fail_fast=True`, execution stops after the first work item that returns `failed` or `partial`.
- The partial-status path created by missing downstream artifacts is covered directly.
- Later work items remain unattempted in persisted execution state.
- The stage call log proves no later executor ran after the first returned failed/partial result.
- A subsequent non-`fail_fast` rerun resumes from the stopped state.

### Verification
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v`
- `.venv/bin/python -m unittest tests.test_experiment_suite_packaging -v`
- `make test`
