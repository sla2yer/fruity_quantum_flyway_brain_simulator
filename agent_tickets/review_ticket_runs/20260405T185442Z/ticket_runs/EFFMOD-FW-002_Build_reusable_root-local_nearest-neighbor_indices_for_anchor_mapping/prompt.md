Work ticket EFFMOD-FW-002: Build reusable root-local nearest-neighbor indices for anchor mapping.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: efficiency_and_modularity review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Synapse anchor materialization still does nearest-support lookup by scanning every surface vertex or every skeleton point for each mapped synapse side. The current code already builds one `RootContext` per root and caches the raw geometry arrays, but it does not cache any reusable search structure. That keeps anchor mapping on an O(mapped synapse sides × geometry size) path during coupling materialization even though the support geometry is root-local and reused across many queries.

Requested Change:
Move nearest-support lookup into reusable root-local search state. Build the surface and skeleton indices once when constructing `RootContext`, then use those indices inside `_surface_patch_mapping()` and `_skeleton_mapping()` so the per-synapse loop no longer rescans full geometry arrays.

Keep the current lookup semantics intact: surface mapping must still choose the patch associated with the nearest surface support vertex, not switch to a different patch-centroid nearest-neighbor rule, and skeleton mapping must still choose the nearest skeleton support point/node.

Acceptance Criteria:
- `RootContext` exposes reusable nearest-neighbor lookup state for surface support vertices and skeleton support points.
- The inner mapping path no longer performs full-array `np.linalg.norm(..., axis=1)` scans for each surface or skeleton query.
- Surface and skeleton mapping preserve the current fallback order, blocked-reason behavior, anchor identity, and support-index semantics.
- Existing serialized root anchor maps and edge coupling bundles remain deterministic for the current fixture coverage.

Verification:
- `.venv/bin/python -m unittest tests.test_synapse_mapping tests.test_coupling_assembly -v`
- `make assets` when local mesh, skeleton, and coupling inputs already exist
