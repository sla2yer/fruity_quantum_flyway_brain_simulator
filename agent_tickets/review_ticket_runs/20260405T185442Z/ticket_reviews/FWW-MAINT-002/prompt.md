Review work ticket FWW-MAINT-002: Simulation planning duplicates per-root asset authority across multiple record shapes.
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
