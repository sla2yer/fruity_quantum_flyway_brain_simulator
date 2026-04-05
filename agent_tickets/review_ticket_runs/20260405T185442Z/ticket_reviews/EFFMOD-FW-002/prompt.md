Review work ticket EFFMOD-FW-002: Replace per-synapse full-geometry scans with reusable spatial indices in anchor mapping.
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
## EFFMOD-FW-002 - Replace per-synapse full-geometry scans with reusable spatial indices in anchor mapping
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: coupling

### Problem
Synapse anchor materialization does nearest-anchor search by scanning every surface vertex or every skeleton node for every mapped synapse side. On selected circuits with many synapses, this turns coupling materialization into an O(synapse count × geometry size) hot path. The root context caches raw arrays, but not the search structure needed to reuse them efficiently.

### Evidence
- [synapse_mapping.py:240](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L240) builds one `RootContext` per root, then [synapse_mapping.py:289](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L289) maps every synapse row through `_build_edge_record(...)`.
- [synapse_mapping.py:957](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L957) calls `_surface_patch_mapping()` or `_skeleton_mapping()` for each query.
- [synapse_mapping.py:1034](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L1034) computes `np.linalg.norm(context.surface_vertices - query_point, axis=1)` on every surface lookup.
- [synapse_mapping.py:1063](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L1063) computes `np.linalg.norm(context.skeleton_points - query_point, axis=1)` on every skeleton lookup.

### Requested Change
Move nearest-anchor search into a reusable root-local search abstraction. Build the surface and skeleton lookup index once when constructing `RootContext`, then use that index inside `_map_query_to_anchor()` so the per-synapse loop no longer rescans full geometry arrays.

### Acceptance Criteria
- Root contexts expose reusable nearest-neighbor search state for surface and skeleton anchors.
- The inner mapping path no longer performs full-array distance scans for each synapse side.
- Existing serialized anchor-map and edge-bundle outputs remain deterministic.

### Verification
- `.venv/bin/python -m unittest tests.test_synapse_mapping tests.test_coupling_assembly -v`
- `make assets` when local mesh/coupling inputs already exist
