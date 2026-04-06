## FWW-MAINT-003 - Experiment-suite work-item `ready` remains contract-visible but unsupported by execution and packaging
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: experiment suite orchestration

### Problem
The repository still publishes `ready` as a canonical experiment-suite work-item status, but the current orchestration code does not treat it as a first-class persisted state. The planner only creates `planned` work items, stage executors may only return terminal statuses, executor resume logic rejects a persisted `ready` work item as unsupported, and package/result-index rollups still omit `ready` from their status tables. That leaves `ready` simultaneously documented and contract-valid, but not round-trippable through current execution state or packaging.

### Evidence
- [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L101) defines `WORK_ITEM_STATUS_READY`, includes it in `SUPPORTED_WORK_ITEM_STATUSES`, and [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L1894) gives it a distinct resumable status definition.
- [experiment_orchestration_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/experiment_orchestration_design.md#L111) and [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L704) still list `ready` in the canonical work-item taxonomy.
- [experiment_suite_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L2556) and [experiment_suite_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L2603) seed every work item as `planned`; the only `ready` writes in the planner are artifact-reference statuses at [experiment_suite_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L1543), so there is still no work-item producer for `ready`.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L77) excludes `ready` from `_SATISFIED_DEPENDENCY_STATUSES` and `_RETRYABLE_STATUSES`, and [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1270) raises `Unsupported orchestration status` for any persisted work item left in `ready`.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1575) only accepts `succeeded`, `partial`, `failed`, `blocked`, and `skipped` from stage executors, so executors cannot report `ready` even if the contract keeps advertising it.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1407) omits `ready` from state rollups and overall-status selection.
- [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L300) initializes stage-status counts without `ready`, [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L336) indexes those counts by the live stage status, and [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L105) plus [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L1524) also omit `ready` from cell rollup priority and cell-status counts.

### Requested Change
Make work-item status semantics single-sourced across contract, planner, execution-state transitions, and package/result-index rollups. Either remove `ready` from the public work-item taxonomy if it is not meant to persist, or implement it end-to-end as a supported persisted state with one shared transition/status model.

### Acceptance Criteria
- The public contract, docs, planner, executor, and package/result-index code recognize the same complete set of work-item statuses.
- The repository defines whether `ready` is a persisted work-item state, a transient internal decision, or unsupported, and that choice is enforced from one shared status model.
- If `ready` remains supported, persisted execution state and package generation can carry it without unsupported-status errors, missing-count rollups, or status-table failures.
- Regression coverage exercises the chosen `ready` behavior on both execution resume and package/result-index paths.

### Verification
`make test`
