Work ticket FWW-MAINT-003: Experiment-suite work-item `ready` remains contract-visible but unsupported by execution and packaging.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: readability_and_maintainability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repository still publishes `ready` as a canonical experiment-suite work-item status, but the current orchestration code does not treat it as a first-class persisted state. The planner only creates `planned` work items, stage executors may only return terminal statuses, executor resume logic rejects a persisted `ready` work item as unsupported, and package/result-index rollups still omit `ready` from their status tables. That leaves `ready` simultaneously documented and contract-valid, but not round-trippable through current execution state or packaging.

Requested Change:
Make work-item status semantics single-sourced across contract, planner, execution-state transitions, and package/result-index rollups. Either remove `ready` from the public work-item taxonomy if it is not meant to persist, or implement it end-to-end as a supported persisted state with one shared transition/status model.

Acceptance Criteria:
- The public contract, docs, planner, executor, and package/result-index code recognize the same complete set of work-item statuses.
- The repository defines whether `ready` is a persisted work-item state, a transient internal decision, or unsupported, and that choice is enforced from one shared status model.
- If `ready` remains supported, persisted execution state and package generation can carry it without unsupported-status errors, missing-count rollups, or status-table failures.
- Regression coverage exercises the chosen `ready` behavior on both execution resume and package/result-index paths.

Verification:
`make test`
