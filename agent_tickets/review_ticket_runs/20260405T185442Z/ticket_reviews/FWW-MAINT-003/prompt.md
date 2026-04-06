Review work ticket FWW-MAINT-003: Experiment-suite status taxonomy and executor semantics diverge on `ready`.
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
## FWW-MAINT-003 - Experiment-suite status taxonomy and executor semantics diverge on `ready`
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: experiment suite orchestration

### Problem
The experiment-suite contract advertises `ready` as a real work-item status with its own semantics, but the executor and state rollups do not model it. That leaves maintainers unable to tell whether `ready` is a dead status, an intended persisted transition, or something external tooling is allowed to write.

### Evidence
- [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L101) includes `WORK_ITEM_STATUS_READY` in the supported status set.
- [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L1894) gives `ready` a distinct description and marks it resumable, implying it is part of the authoritative orchestration state machine.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L77) excludes `ready` from `_SATISFIED_DEPENDENCY_STATUSES` and `_RETRYABLE_STATUSES`.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1201) therefore treats a persisted `ready` work item as an unsupported status.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1338) omits `ready` from `status_counts` and `overall_status`, while initialization only seeds `planned` items at [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1282).

### Requested Change
Make the status machine single-sourced. Either remove `ready` from the public contract if it is not meant to persist, or implement full executor, dependency, and rollup handling for it from the same transition table.

### Acceptance Criteria
- The public contract and executor recognize the same complete set of work-item statuses.
- Transition, retry, dependency-satisfaction, and rollup rules come from one shared status model.
- If `ready` remains supported, persisted execution state can carry it without raising unsupported-status errors.

### Verification
`make test`
