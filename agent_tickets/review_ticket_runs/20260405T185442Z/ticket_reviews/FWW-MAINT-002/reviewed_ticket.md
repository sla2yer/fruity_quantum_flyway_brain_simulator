## FWW-MAINT-002 - Simulation asset resolution still duplicates per-root asset authority
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: simulation asset resolution

### Problem
The original `simulation_planning.py` references for this ticket are stale, but the underlying issue is still present after the planner split. [resolve_circuit_assets()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_asset_resolution.py#L158) expands each selected manifest root into parallel planner-owned shapes: `geometry_asset_records`, `operator_asset_records`, `required_operator_assets`, top-level sidecar shortcuts, `coupling_asset_records`, `required_coupling_assets`, `edge_bundle_paths`, and copied `operator_bundle` / `coupling_bundle`. Downstream helpers then mix and match those copies instead of consuming one authoritative per-root asset contract, so ownership is still split between the manifest row, copied bundle metadata, path-only convenience dicts, and derived runtime asset payloads.

### Evidence
- [build_geometry_manifest_record()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L672) already emits rich per-root manifest structures under `assets`, `operator_bundle`, and `coupling_bundle`, even though legacy convenience paths remain on the record.
- [resolve_circuit_assets()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_asset_resolution.py#L158) rebuilds those manifest records into new per-root maps and copied bundles, including `required_operator_assets`, `descriptor_sidecar_path`, `qa_sidecar_path`, `required_coupling_assets`, and `edge_bundle_paths`.
- [load_mixed_fidelity_descriptor_payload()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_asset_resolution.py#L344) reads the top-level copied `descriptor_sidecar_path` shortcut instead of resolving descriptors from a canonical per-root asset object.
- [resolve_surface_wave_operator_asset()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_asset_resolution.py#L597) depends on both `operator_bundle_status` / `operator_bundle` and `operator_asset_records`, then reloads `operator_metadata_path` from disk and compares the JSON against the copied `operator_bundle` for whole-dict drift.
- [resolve_root_coupling_asset_record()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_asset_resolution.py#L836) reconstructs yet another coupling view from `coupling_bundle`, `coupling_asset_records`, and filtered `edge_bundle_paths`.
- [resolve_surface_wave_mixed_fidelity_plan()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_runtime_planning.py#L475) copies `selected_edge_bundle_paths` again into skeleton runtime assets, showing that the duplication now continues into runtime-facing record shapes.

### Requested Change
Refactor the post-manifest asset handoff so `resolve_circuit_assets()` publishes one normalized per-root asset record and downstream helpers derive path-only or runtime-specific convenience views from that record at the use site. Keep this ticket scoped to planner/runtime asset authority cleanup; do not broaden it into a geometry-manifest schema redesign unless a minimal schema change is required to remove the duplicated ownership.

### Acceptance Criteria
- `resolve_circuit_assets()` returns one canonical per-root asset structure that remains authoritative through mixed-fidelity planning and runtime asset resolution.
- Parallel copies such as `required_operator_assets`, `required_coupling_assets`, top-level `descriptor_sidecar_path` / `qa_sidecar_path`, and repeated `selected_edge_bundle_paths` are removed or reduced to derived-only views.
- `resolve_surface_wave_operator_asset()` and `resolve_root_coupling_asset_record()` consume the canonical record instead of coordinating separate copied bundle metadata and asset-record maps.
- Drift checks validate stable contract fields or asset identifiers from the canonical record rather than whole-dict equality between duplicated copies.

### Verification
`make smoke`
`pytest tests/test_baseline_execution.py tests/test_simulator_execution.py tests/test_hybrid_morphology_runtime.py`
