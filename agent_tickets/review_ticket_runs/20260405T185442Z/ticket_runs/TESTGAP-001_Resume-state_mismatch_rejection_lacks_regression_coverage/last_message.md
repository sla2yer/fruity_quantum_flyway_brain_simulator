Added deterministic regression coverage in [tests/test_experiment_suite_execution.py#L360](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L360). The new test seeds a valid persisted execution state once, then runs two subcases that mutate `suite_spec_hash` and `work_item_order` respectively. Each subcase asserts `execute_experiment_suite_plan()` raises the expected `ValueError`, that no stage executor runs, that `package_experiment_suite_outputs()` is not called, and that the mutated `experiment_suite_execution_state.json` is left byte-for-byte unchanged after the rejected resume attempt.

No production code changes were needed; the guard already existed and this ticket was purely missing regression coverage.

Verified:
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v` passed
- `make test` passed (`Ran 337 tests in 410.829s`)