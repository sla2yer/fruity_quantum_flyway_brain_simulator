# Efficiency And Modularity Review Tickets

## EFFMOD-FW-001 - Stop rereading the raw synapse snapshot during registry and subset materialization
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: registry

### Problem
The normal `make registry -> make select` flow reparses the raw synapse snapshot multiple times even though the code already has a normalized synapse table in memory or on disk. That is the largest CSV in this pipeline, so repeated `pandas` loads and normalization passes directly increase local preprocessing cost. The current API shape also makes reuse hard because `materialize_synapse_registry()` only accepts config and always reloads the raw source.

### Evidence
- [registry.py:360](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L360) loads `synapse_df = _load_synapse_table(source_paths.synapses)` and then still calls `materialize_synapse_registry(...)` at [registry.py:410](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L410).
- [registry.py:307](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L307) shows `materialize_synapse_registry()` immediately calling `_load_synapse_table(...)` again at [registry.py:319](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L319).
- [registry.py:582](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L582) shows `_load_synapse_table()` doing a full `pd.read_csv(path)` plus schema normalization.
- [selection.py:279](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L279) calls `materialize_synapse_registry()` again for the active preset, so `make select` can trigger another full raw-snapshot read just to refresh the subset-scoped registry.

### Requested Change
Split synapse-registry loading from synapse-registry scoping/writing. `build_registry()` should be able to pass the already-normalized synapse table into the materialization path, and active subset refresh should filter either that canonical table or the already-written canonical registry instead of rereading the raw snapshot.

### Acceptance Criteria
- `build_registry()` reads and normalizes the raw synapse snapshot at most once per invocation.
- Active-preset subset refresh can rewrite the scoped synapse registry without forcing another raw CSV parse when the canonical local registry already exists.
- Provenance and scope metadata stay unchanged.

### Verification
- `make test`
- `.venv/bin/python -m unittest tests.test_registry tests.test_selection -v`

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

## EFFMOD-FW-003 - Let experiment-suite stages execute from a resolved simulation plan instead of replanning per stage and model mode
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: experiment suites

### Problem
Suite execution is wired around file paths instead of a reusable planning object, so the same materialized cell can reparse config/manifest inputs and rerun expensive planning work multiple times. In the simulation stage, the suite resolves a plan to discover model modes, then `execute_manifest_simulation()` resolves the same plan again for each mode. That planning path also loads fine-operator archives and runs an eigensolver to estimate spectral radius, so the duplicated work is materially expensive for surface-wave cells.

### Evidence
- [experiment_suite_execution.py:548](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L548) resolves `simulation_plan` once, then loops over `model_modes` and calls `execute_manifest_simulation(...)` at [experiment_suite_execution.py:570](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L570).
- [simulator_execution.py:161](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L161) shows `execute_manifest_simulation()` immediately calling `resolve_manifest_simulation_plan(...)` again at [simulator_execution.py:172](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L172).
- [simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) reloads config, manifest, schema, and design lock on each plan resolution.
- [simulation_planning.py:4315](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4315) and [simulation_planning.py:4771](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4771) compute spectral radius by reopening the operator archive and running `eigsh`.
- [experiment_suite_execution.py:731](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L731) shows the validation stage resolving the full simulation plan again for the same work item.

### Requested Change
Introduce a reusable suite execution context that carries a resolved simulation plan, resolved arm plans, and cached operator-stability metadata. Update simulator and validation entrypoints so they can consume that object directly instead of forcing a path-based round-trip back through `resolve_manifest_simulation_plan()`.

### Acceptance Criteria
- A suite work item resolves its manifest/config-driven simulation plan once and reuses it across simulation and validation stages.
- Executing multiple model modes for one materialized cell does not call `resolve_manifest_simulation_plan()` repeatedly.
- Spectral-radius estimation is computed once per unique operator bundle per plan, or loaded from cached plan/metadata state.

### Verification
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution tests.test_simulation_planning tests.test_simulator_execution -v`
- `make smoke`
