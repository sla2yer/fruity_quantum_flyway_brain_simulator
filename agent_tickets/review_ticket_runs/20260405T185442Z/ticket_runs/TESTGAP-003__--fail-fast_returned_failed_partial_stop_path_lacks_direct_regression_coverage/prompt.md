Work ticket TESTGAP-003: `--fail-fast` returned failed/partial stop path lacks direct regression coverage.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: low
Source: testing_and_verification_gaps review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The original gap is no longer accurate as written: the repository now has direct regression coverage for exception-driven `fail_fast=True` stop/resume behavior and for packaging the resulting `ready` work items. The remaining untested branch is narrower: when a stage executor returns `failed` or `partial` status, or is normalized to `partial` because downstream artifacts are missing, `--fail-fast` should stop before any later work items run. That branch is separate from the exception path, so a regression could keep scheduling downstream work after a partial result while current fail-fast tests still pass.

Requested Change:
Extend [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) with a deterministic `fail_fast=True` scenario where one stage returns `WORK_ITEM_STATUS_PARTIAL` or reports success with a missing downstream artifact so the executor normalizes it to `partial`. Assert that later work items are not attempted, then confirm a subsequent non-`fail_fast` rerun resumes from the stopped state. A subprocess-style CLI assertion for `scripts/31_run_experiment_suite.py --fail-fast` is optional and should stay limited to flag plumbing if the existing fixture is easy to reuse.

Acceptance Criteria:
- With `fail_fast=True`, execution stops after the first work item that returns `failed` or `partial`.
- The partial-status path created by missing downstream artifacts is covered directly.
- Later work items remain unattempted in persisted execution state.
- The stage call log proves no later executor ran after the first returned failed/partial result.
- A subsequent non-`fail_fast` rerun resumes from the stopped state.

Verification:
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v`
- `.venv/bin/python -m unittest tests.test_experiment_suite_packaging -v`
- `make test`
