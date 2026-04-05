## EFFMOD-FW-002 - Build reusable root-local nearest-neighbor indices for anchor mapping
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: anchor mapping

### Problem
Synapse anchor materialization still does nearest-support lookup by scanning every surface vertex or every skeleton point for each mapped synapse side. The current code already builds one `RootContext` per root and caches the raw geometry arrays, but it does not cache any reusable search structure. That keeps anchor mapping on an O(mapped synapse sides × geometry size) path during coupling materialization even though the support geometry is root-local and reused across many queries.

### Evidence
- [synapse_mapping.py#L240](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L240) builds root contexts once per selected root, and [synapse_mapping.py#L289](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L289) still maps every synapse row through the per-row edge-record path.
- [synapse_mapping.py#L209](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L209) shows `RootContext` storing raw surface and skeleton arrays only, and [synapse_mapping.py#L676](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L676) / [synapse_mapping.py#L709](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L709) populate those arrays without building a reusable lookup index.
- [synapse_mapping.py#L877](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L877) calls `_map_query_to_anchor(...)` twice per synapse row, and [synapse_mapping.py#L957](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L957) dispatches each query into `_surface_patch_mapping()` or `_skeleton_mapping()`.
- [synapse_mapping.py#L1034](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L1034) / [synapse_mapping.py#L1037](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L1037) compute `np.linalg.norm(context.surface_vertices - query_point, axis=1)` on every surface lookup, and [synapse_mapping.py#L1063](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L1063) / [synapse_mapping.py#L1066](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/synapse_mapping.py#L1066) do the same full scan for every skeleton lookup.
- [test_synapse_mapping.py#L35](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_synapse_mapping.py#L35) and [test_coupling_assembly.py#L26](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_coupling_assembly.py#L26) already assert deterministic anchor-map and edge-bundle outputs, so this work remains an internal performance refactor that must preserve current mapping semantics.

### Requested Change
Move nearest-support lookup into reusable root-local search state. Build the surface and skeleton indices once when constructing `RootContext`, then use those indices inside `_surface_patch_mapping()` and `_skeleton_mapping()` so the per-synapse loop no longer rescans full geometry arrays.

Keep the current lookup semantics intact: surface mapping must still choose the patch associated with the nearest surface support vertex, not switch to a different patch-centroid nearest-neighbor rule, and skeleton mapping must still choose the nearest skeleton support point/node.

### Acceptance Criteria
- `RootContext` exposes reusable nearest-neighbor lookup state for surface support vertices and skeleton support points.
- The inner mapping path no longer performs full-array `np.linalg.norm(..., axis=1)` scans for each surface or skeleton query.
- Surface and skeleton mapping preserve the current fallback order, blocked-reason behavior, anchor identity, and support-index semantics.
- Existing serialized root anchor maps and edge coupling bundles remain deterministic for the current fixture coverage.

### Verification
- `.venv/bin/python -m unittest tests.test_synapse_mapping tests.test_coupling_assembly -v`
- `make assets` when local mesh, skeleton, and coupling inputs already exist
