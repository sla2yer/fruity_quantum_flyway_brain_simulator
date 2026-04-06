Work ticket TESTGAP-001: Resume-state mismatch rejection lacks regression coverage.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: testing_and_verification_gaps review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`execute_experiment_suite_plan()` already rejects persisted resume state that does not match the current suite identity or normalized work-item ordering. The remaining gap is regression coverage: the test suite does not seed an incompatible `experiment_suite_execution_state.json` and prove that mismatched `suite_spec_hash` and `work_item_order` are rejected before resume side effects begin. If that guard regresses, a stale state file could be accepted and resume the wrong suite history without `make test` catching it.

Requested Change:
Add a deterministic unit test in [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) that creates a valid persisted execution state, then mutates `suite_spec_hash` in one subcase and `work_item_order` in another. Assert that `execute_experiment_suite_plan()` raises immediately, with stub stage executors and a patched packaging hook so the test proves resume is rejected before any executor or packaging side effect runs.

Acceptance Criteria:
- Reusing a state file with a different `suite_spec_hash` raises a clear `ValueError`.
- Reusing a state file with a different `work_item_order` raises a clear `ValueError`.
- No stage executor is called after either mismatch is detected.
- `package_experiment_suite_outputs()` is not called after either mismatch is detected.
- The mismatched state file is left unchanged after the rejected resume attempt.

Verification:
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v`
- `make test`
