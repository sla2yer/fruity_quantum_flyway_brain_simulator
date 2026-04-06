## TESTGAP-001 - Resume-state mismatch rejection lacks regression coverage
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: experiment suite execution

### Problem
`execute_experiment_suite_plan()` already rejects persisted resume state that does not match the current suite identity or normalized work-item ordering. The remaining gap is regression coverage: the test suite does not seed an incompatible `experiment_suite_execution_state.json` and prove that mismatched `suite_spec_hash` and `work_item_order` are rejected before resume side effects begin. If that guard regresses, a stale state file could be accepted and resume the wrong suite history without `make test` catching it.

### Evidence
- The persisted-state validation runs before state initialization, input persistence, and materialized-input preparation in [src/flywire_wave/experiment_suite_execution.py:129](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L129) and [src/flywire_wave/experiment_suite_execution.py:152](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L152).
- The explicit mismatch checks for `suite_spec_hash` and `work_item_order` live in [src/flywire_wave/experiment_suite_execution.py:1427](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1427).
- Existing execution coverage exercises compatible resume behavior and fail-fast resume recovery in [tests/test_experiment_suite_execution.py:60](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L60) and [tests/test_experiment_suite_execution.py:249](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L249), but there is still no negative-path test that seeds an incompatible persisted state and asserts the rejection path.

### Requested Change
Add a deterministic unit test in [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) that creates a valid persisted execution state, then mutates `suite_spec_hash` in one subcase and `work_item_order` in another. Assert that `execute_experiment_suite_plan()` raises immediately, with stub stage executors and a patched packaging hook so the test proves resume is rejected before any executor or packaging side effect runs.

### Acceptance Criteria
- Reusing a state file with a different `suite_spec_hash` raises a clear `ValueError`.
- Reusing a state file with a different `work_item_order` raises a clear `ValueError`.
- No stage executor is called after either mismatch is detected.
- `package_experiment_suite_outputs()` is not called after either mismatch is detected.
- The mismatched state file is left unchanged after the rejected resume attempt.

### Verification
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v`
- `make test`
