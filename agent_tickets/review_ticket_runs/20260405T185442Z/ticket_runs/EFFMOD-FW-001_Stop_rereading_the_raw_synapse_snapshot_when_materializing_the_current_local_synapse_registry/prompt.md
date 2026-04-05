Work ticket EFFMOD-FW-001: Stop rereading the raw synapse snapshot when materializing the current local synapse registry.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: efficiency_and_modularity review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`build_registry()` and active-preset subset generation both write the same local synapse-registry artifact under `config.paths.processed_coupling_dir/synapse_registry.csv`. In the current code, both flows reread and renormalize the raw synapse snapshot even when an equivalent normalized table is already available in memory during registry build or when the current local registry plus its provenance could be reused as the `all_rows` input. Because the synapse snapshot is the largest CSV in this pipeline, the extra `pandas` parse and alias-normalization passes add avoidable cost to the standard `make registry -> make select` flow. The current `materialize_synapse_registry()` API also makes reuse awkward because it only accepts config plus optional root-id inputs.

Requested Change:
Split raw-snapshot loading from local synapse-registry writing within the existing single-path coupling contract. `build_registry()` should be able to pass its already-normalized `synapse_df` into the synapse-registry materialization path. Active-preset subset refresh should reuse the current local synapse registry when `synapse_registry_provenance.json` shows it is an `all_rows` materialization with compatible source/version metadata, and only fall back to rereading the raw synapse snapshot when no reusable all-rows local registry is available.

Acceptance Criteria:
- `build_registry()` reads and normalizes the raw synapse snapshot at most once per invocation.
- The synapse-registry materialization path can accept a caller-supplied normalized synapse table without changing the written CSV schema, output path, or provenance shape.
- Active-preset subset refresh can rewrite `config.paths.processed_coupling_dir/synapse_registry.csv` without a raw CSV parse when the current local registry and provenance are reusable `all_rows` inputs.
- If the current local registry is missing, already subset-scoped, or provenance/source/version metadata are incompatible, the code falls back to the raw snapshot path and preserves current behavior.
- `synapse_registry_provenance.json` continues to record correct `scope.mode`, `scope.label`, `root_ids`, `root_ids_path`, and source metadata.
- Regression tests cover both the single-load `build_registry()` path and the reusable-local-registry subset-refresh path.

Verification:
- `make test`
- `.venv/bin/python -m unittest tests.test_registry tests.test_selection -v`
