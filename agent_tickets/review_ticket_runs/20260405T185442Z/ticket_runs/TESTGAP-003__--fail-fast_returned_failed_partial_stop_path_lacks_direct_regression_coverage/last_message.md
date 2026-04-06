Added two regression tests in [tests/test_experiment_suite_execution.py#L361](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L361) and [tests/test_experiment_suite_execution.py#L498](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L498). One covers `fail_fast=True` stopping on a stage executor that directly returns `partial`; the other covers the success-with-missing-artifact path that is normalized to `partial`. Both tests assert that only the first work item runs, later persisted work items remain unattempted, and a later non-`fail_fast` rerun resumes from that stopped state and completes the schedule.

Verified:
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v`
- `.venv/bin/python -m unittest tests.test_experiment_suite_packaging -v`
- `make test` passed (`343` tests, `416.196s`)