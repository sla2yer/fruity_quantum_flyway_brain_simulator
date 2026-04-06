Work ticket FWW-MAINT-002: Simulation asset resolution still duplicates per-root asset authority.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: readability_and_maintainability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The original `simulation_planning.py` references for this ticket are stale, but the underlying issue is still present after the planner split. [resolve_circuit_assets()](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_asset_resolution.py#L158) expands each selected manifest root into parallel planner-owned shapes: `geometry_asset_records`, `operator_asset_records`, `required_operator_assets`, top-level sidecar shortcuts, `coupling_asset_records`, `required_coupling_assets`, `edge_bundle_paths`, and copied `operator_bundle` / `coupling_bundle`. Downstream helpers then mix and match those copies instead of consuming one authoritative per-root asset contract, so ownership is still split between the manifest row, copied bundle metadata, path-only convenience dicts, and derived runtime asset payloads.

Requested Change:
Refactor the post-manifest asset handoff so `resolve_circuit_assets()` publishes one normalized per-root asset record and downstream helpers derive path-only or runtime-specific convenience views from that record at the use site. Keep this ticket scoped to planner/runtime asset authority cleanup; do not broaden it into a geometry-manifest schema redesign unless a minimal schema change is required to remove the duplicated ownership.

Acceptance Criteria:
- `resolve_circuit_assets()` returns one canonical per-root asset structure that remains authoritative through mixed-fidelity planning and runtime asset resolution.
- Parallel copies such as `required_operator_assets`, `required_coupling_assets`, top-level `descriptor_sidecar_path` / `qa_sidecar_path`, and repeated `selected_edge_bundle_paths` are removed or reduced to derived-only views.
- `resolve_surface_wave_operator_asset()` and `resolve_root_coupling_asset_record()` consume the canonical record instead of coordinating separate copied bundle metadata and asset-record maps.
- Drift checks validate stable contract fields or asset identifiers from the canonical record rather than whole-dict equality between duplicated copies.

Verification:
`make smoke`
`pytest tests/test_baseline_execution.py tests/test_simulator_execution.py tests/test_hybrid_morphology_runtime.py`
