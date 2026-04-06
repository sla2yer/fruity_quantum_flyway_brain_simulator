Review work ticket TESTGAP-003: `--fail-fast` suite execution behavior is untested.
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
