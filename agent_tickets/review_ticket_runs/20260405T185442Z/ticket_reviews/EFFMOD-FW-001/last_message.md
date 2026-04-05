## EFFMOD-FW-001 - Stop rereading the raw synapse snapshot when materializing the current local synapse registry
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: registry/selection

### Problem
`build_registry()` and active-preset subset generation both write the same local synapse-registry artifact under `config.paths.processed_coupling_dir/synapse_registry.csv`. In the current code, both flows reread and renormalize the raw synapse snapshot even when an equivalent normalized table is already available in memory during registry build or when the current local registry plus its provenance could be reused as the `all_rows` input. Because the synapse snapshot is the largest CSV in this pipeline, the extra `pandas` parse and alias-normalization passes add avoidable cost to the standard `make registry -> make select` flow. The current `materialize_synapse_registry()` API also makes reuse awkward because it only accepts config plus optional root-id inputs.

### Evidence
- [registry.py:378](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L378) loads `synapse_df = _load_synapse_table(source_paths.synapses)` for registry construction, but [registry.py:410](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L410) still calls `materialize_synapse_registry(...)` instead of reusing that normalized table.
- [registry.py:307](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L307) shows `materialize_synapse_registry()` only accepting `cfg`, `root_ids`, `root_ids_path`, and `scope_label`; it immediately resolves the source path at [registry.py:317](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L317) and reloads `_load_synapse_table(...)` at [registry.py:319](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L319).
- [registry.py:582](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L582) shows `_load_synapse_table()` doing a fresh `pd.read_csv(path)` plus full alias resolution and schema normalization.
- [selection.py:445](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L445) shows active-preset subset generation always routing through `materialize_synapse_registry()` when coupling/synapse paths are configured, so `make select` can trigger another raw snapshot parse even if the local registry already exists.
- [registry.py:502](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L502) maps both build-time and selection-time writes to the same `processed_coupling_dir/synapse_registry.csv` contract path, so this should be fixed by reusing the current local artifact rather than by broadening the ticket into a storage redesign.
- [registry.py:953](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py#L953) already writes `synapse_registry_provenance.json` with `scope.mode` (`all_rows` vs `root_id_subset`), which is enough to decide whether the current local registry is reusable as the source for subset filtering.

### Requested Change
Split raw-snapshot loading from local synapse-registry writing within the existing single-path coupling contract. `build_registry()` should be able to pass its already-normalized `synapse_df` into the synapse-registry materialization path. Active-preset subset refresh should reuse the current local synapse registry when `synapse_registry_provenance.json` shows it is an `all_rows` materialization with compatible source/version metadata, and only fall back to rereading the raw synapse snapshot when no reusable all-rows local registry is available.

### Acceptance Criteria
- `build_registry()` reads and normalizes the raw synapse snapshot at most once per invocation.
- The synapse-registry materialization path can accept a caller-supplied normalized synapse table without changing the written CSV schema, output path, or provenance shape.
- Active-preset subset refresh can rewrite `config.paths.processed_coupling_dir/synapse_registry.csv` without a raw CSV parse when the current local registry and provenance are reusable `all_rows` inputs.
- If the current local registry is missing, already subset-scoped, or provenance/source/version metadata are incompatible, the code falls back to the raw snapshot path and preserves current behavior.
- `synapse_registry_provenance.json` continues to record correct `scope.mode`, `scope.label`, `root_ids`, `root_ids_path`, and source metadata.
- Regression tests cover both the single-load `build_registry()` path and the reusable-local-registry subset-refresh path.

### Verification
- `make test`
- `.venv/bin/python -m unittest tests.test_registry tests.test_selection -v`