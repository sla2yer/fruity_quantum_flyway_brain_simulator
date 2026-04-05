# Readability And Maintainability Review Tickets

## FWW-MAINT-001 - Active subset publication is hidden inside preset generation
- Status: open
- Priority: high
- Source: readability_and_maintainability review
- Area: subset selection

### Problem
The canonical selected-root roster for the rest of the pipeline is not modeled as its own step. Instead, `generate_subsets_from_config()` quietly publishes one preset as the authoritative `selected_root_ids` alias and may also refresh the subset-scoped synapse registry as a side effect of iterating generated presets. That makes it hard to tell which subset output is authoritative for `select -> meshes -> assets -> simulation`, and maintainers have to remember that the active preset has extra behavior that other generated presets do not.

### Evidence
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L257) loops over all requested presets, but only the `active_preset` branch writes `paths.selected_root_ids` and conditionally calls `materialize_synapse_registry()`.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L283) ties synapse-registry refresh to the presence of `processed_coupling_dir` or `synapse_source_csv`, so the canonical coupling side effect is controlled by path-key presence rather than an explicit publish step.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L313) returns only `active_preset` plus generated artifact paths; it does not record whether the canonical alias or subset-scoped coupling registry was actually refreshed.
- [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L19) and [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L114) show that this hidden side effect is part of the external contract.

### Requested Change
Separate “build preset artifacts” from “publish canonical active subset” into explicit steps or helpers, and return structured metadata showing which preset became the authoritative root roster and whether subset-scoped coupling artifacts were refreshed.

### Acceptance Criteria
- The code has one explicit helper or phase that publishes the canonical active subset used downstream.
- The conditions for refreshing the subset-scoped synapse registry are expressed as named selection-pipeline behavior, not as incidental path-key checks inside the preset loop.
- The returned summary clearly states which preset, if any, updated `selected_root_ids` and coupling-side artifacts.

### Verification
`make test`

## FWW-MAINT-002 - Simulation planning duplicates per-root asset authority across multiple record shapes
- Status: open
- Priority: high
- Source: readability_and_maintainability review
- Area: surface-wave planning

### Problem
The planner does not carry one authoritative per-root asset contract forward from the geometry manifest. Instead it expands the same root into parallel structures such as `geometry_asset_records`, `operator_asset_records`, `required_operator_assets`, shortcut sidecar paths, copied `operator_bundle`, copied `coupling_bundle`, and later runtime-specific asset records. Future maintainers have to infer whether the source of truth is the manifest row, the bundle metadata JSON on disk, or one of the planner’s copied dicts.

### Evidence
- [geometry_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L316) already defines operator bundle metadata with canonical per-asset records and rich contract fields.
- [simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3013) rebuilds each selected root into new ad hoc maps: `geometry_asset_records`, `operator_asset_records`, `required_operator_assets`, duplicated sidecar paths, `coupling_asset_records`, `required_coupling_assets`, `edge_bundle_paths`, plus full copied `operator_bundle` and `coupling_bundle`.
- [simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4240) reopens `operator_metadata_path` and compares the loaded JSON to the copied `operator_bundle` for drift, which is a strong sign that ownership is split between duplicated records.
- [simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4433) then reconstructs yet another coupling view from `coupling_asset_records` rather than consuming a single normalized root asset object.

### Requested Change
Introduce one normalized per-root circuit-asset record that remains authoritative from geometry-manifest loading through mixed-fidelity and runtime resolution, and derive path-only convenience views at the use site instead of storing parallel copied bookkeeping.

### Acceptance Criteria
- Selected roots are represented by one canonical normalized asset structure through planner-to-runtime handoff.
- Duplicated fields such as `required_operator_assets`, shortcut sidecar paths, and copied bundle dicts are removed or made derived-only.
- Drift validation compares stable identifiers or contract fields from the canonical record, not whole-dict equality between duplicated copies.

### Verification
`make smoke`

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

## FWW-MAINT-004 - Review-surface packagers hand-build the same artifact-reference logic in multiple modules
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: packaged review surfaces

### Problem
Dashboard, showcase, and whole-brain-context planners repeatedly hand-assemble artifact-reference payloads from upstream bundle metadata and then re-check the same bundle-alignment invariants. That obscures which fields are authoritative for packaged review surfaces: discovered bundle paths, metadata `artifacts`, explicit overrides, or copied session references. Any contract change to artifact IDs, scopes, or required alignment now needs synchronized edits across several large modules.

### Evidence
- [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1359) manually maps each upstream artifact into dashboard references by repeating `bundle_id`, `artifact_id`, `format`, `artifact_scope`, and `status`.
- [showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3756) repeats the same pattern for dashboard, analysis, validation, and suite artifacts, then maintains a separate explicit-override merge path at [showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4203).
- [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1185) builds yet another artifact-reference catalog for subset, dashboard, showcase, and connectivity artifacts.
- The same `bundle_id` alignment rule for dashboard metadata/payload/state is duplicated in [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1134), [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3336), [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3419), and [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3443).

### Requested Change
Introduce shared helpers for “lift bundle metadata into artifact references” and “validate packaged bundle alignment”, with declarative role-to-artifact mappings reused by dashboard, showcase, and whole-brain-context planners.

### Acceptance Criteria
- Artifact-reference construction for packaged review surfaces is driven by shared helpers or declarative maps rather than repeated hand-written blocks.
- Bundle-alignment checks for packaged dashboard/showcase/session records are centralized.
- A contract change to an upstream artifact role or artifact ID requires updating one shared mapping path, not each planner separately.

### Verification
`make test`
