Review work ticket TESTGAP-001: Resume-state mismatch rejection is not protected.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

This is a ticket review pass only. Do not implement code.
Earlier backlog tickets may already have changed the surrounding code.
Check whether this ticket is still accurate for the repository's current state and update it if needed.

Rules:
- Keep the same ticket ID.
- Return exactly one ticket in the same markdown ticket format.
- Update the title, priority, area, and sections if the ticket needs refinement.
- If the ticket no longer needs implementation, set `- Status: closed` and explain why.
- Do not create new tickets or broaden this ticket into a larger backlog item.
- Return only the updated single-ticket markdown and do not use code fences.

Existing Ticket:
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
