# Review Ticket Backlog

This file is maintained by `scripts/run_review_ticket_backlog.py`.

## APICPL-001 - Manifest validation resolves stimulus bundle paths outside runtime config
- Status: open
- Priority: medium
- Source: api_boundaries_and_coupling review
- Area: manifest validation / runtime config

### Problem
The public `validate-manifest` surface emits bundle-facing stimulus metadata, but it resolves the processed stimulus root from a repo default instead of the runtime config that manifest-driven execution actually uses. That means the repo’s safe validation loop can report a different external bundle path than `run_simulation.py` or other manifest-driven runners for the same manifest.

### Evidence
- `[src/flywire_wave/manifests.py#L156](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/manifests.py#L156)` falls back to `REPO_ROOT / DEFAULT_PROCESSED_STIMULUS_DIR` when no directory is passed.
- `[scripts/04_validate_manifest.py#L17](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/04_validate_manifest.py#L17)` only accepts `--manifest`, `--schema`, and `--design-lock`, so it cannot align validation with `config.paths.processed_stimulus_dir`.
- `[Makefile#L228](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L228)` wires `make validate-manifest` through that config-blind CLI.
- `[src/flywire_wave/simulation_planning.py#L504](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L504)` explicitly passes `cfg["paths"]["processed_stimulus_dir"]` into manifest validation during real plan resolution.
- `[src/flywire_wave/stimulus_bundle.py#L140](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_bundle.py#L140)` already exposes an explicit processed-stimulus override for the manifest-driven stimulus workflow, so the inconsistency is only at this boundary.

### Requested Change
Create one library-owned manifest-input resolver that accepts either `config_path` or explicit processed bundle roots, and route `scripts/04_validate_manifest.py`, manifest-driven stimulus/retinal workflows, and simulation planning through it. If validation keeps returning bundle paths, those paths need to be config-aware.

### Acceptance Criteria
`validate-manifest`, `resolve_manifest_simulation_plan`, and manifest-driven bundle recorders produce the same `stimulus_bundle_reference` and `stimulus_bundle_metadata_path` for the same manifest plus runtime config, including nondefault `processed_stimulus_dir` values.

### Verification
`make validate-manifest`; `python3 -m unittest tests.test_manifest_validation -v`; add a regression test that compares validation output against `resolve_manifest_simulation_plan` under a nondefault `config.paths.processed_stimulus_dir`.

## APICPL-002 - Planner bundle metadata resolution still falls back to filesystem globbing instead of contract-owned lookup
- Status: open
- Priority: high
- Source: api_boundaries_and_coupling review
- Area: experiment analysis / dashboard planning

### Problem
The repository now has more contract support than this ticket originally assumed: simulator result bundles have a direct metadata-path resolver, experiment-analysis and validation contracts have deterministic bundle path builders, and validation planning already uses the identity-based analysis lookup pattern. The remaining issue is that experiment comparison and dashboard planning still bypass those contract surfaces and rescan on-disk directories for `*/...bundle.json`. That keeps discovery policy coupled to folder layout and allows unrelated or stale files under an experiment root to affect planner behavior.

### Evidence
- [experiment_comparison_analysis.py:149](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L149) and [experiment_comparison_analysis.py:152](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L152) rebuild `processed_simulator_results_dir/bundles/<experiment_id>/<arm_id>/` and glob `*/simulator_result_bundle.json`.
- Per-seed run plans already carry canonical result bundle metadata via [simulation_planning.py:4888](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4888) and [simulation_planning.py:4907](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4907), and the simulator contract already exposes [simulator_result_contract.py:1034](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_result_contract.py#L1034) for identity-based metadata-path resolution.
- [dashboard_session_planning.py:674](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L674) and [dashboard_session_planning.py:725](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L725) still glob `analysis/<experiment_id>/*/experiment_analysis_bundle.json` and `validation/<experiment_id>/*/validation_bundle.json`.
- Deterministic analysis and validation bundle layout is already owned by [experiment_analysis_contract.py:95](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_analysis_contract.py#L95) and [validation_contract.py:159](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_contract.py#L159), and validation planning already resolves the expected analysis bundle path from plan identity at [validation_planning.py:476](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_planning.py#L476). There is still no comparable shared analysis/validation metadata lookup helper; only simulator currently has one.

### Requested Change
Replace the remaining raw directory scans with contract-owned metadata lookup:
- In `discover_experiment_bundle_set()`, resolve expected simulator bundle metadata from the canonical per-run `result_bundle` identity or `resolve_simulator_result_bundle_metadata_path()` instead of globbing arm bundle directories.
- Add shared experiment-analysis and validation bundle metadata lookup helpers that accept plan identity when available and bundle-reference inputs when only upstream bundle ids are available, then route dashboard session planning through those helpers instead of direct `glob("*/...bundle.json")` calls.
- Keep ambiguity handling inside the shared resolver layer so planner modules stop owning filename and folder policy.

### Acceptance Criteria
High-level planners no longer call `glob("*/simulator_result_bundle.json")`, `glob("*/experiment_analysis_bundle.json")`, or `glob("*/validation_bundle.json")` to resolve bundle metadata. Experiment comparison and dashboard planning resolve bundle metadata through contract-owned identity/path helpers, and stray or stale directories under `bundles/`, `analysis/`, or `validation/` do not change which bundle is selected.

### Verification
`python3 -m unittest tests.test_experiment_comparison_analysis -v`; `python3 -m unittest tests.test_validation_planning -v`; `python3 -m unittest tests.test_dashboard_session_planning -v` after installing `trimesh` (that suite currently fails to import in this environment with `ModuleNotFoundError: trimesh`).

## APICPL-003 - Geometry manifest `_coupling_contract` is sampled from the lowest sorted root's `coupling_bundle` instead of manifest inputs
- Status: open
- Priority: high
- Source: api_boundaries_and_coupling review
- Area: geometry manifest / coupling contract

### Problem
The manifest-level coupling header is no longer sensitive to dict insertion order, because roots are sorted numerically before sampling. But it is still synthesized from exactly one per-root `coupling_bundle`: the lowest root ID that has one. That makes the global contract depend on sampled per-root metadata instead of explicit manifest-owned inputs. Because the header builder reconstructs `processed_coupling_dir` from that sampled bundle's `local_synapse_registry.path`, stale or mixed per-root coupling metadata can silently override the caller-provided coupling directory and rewrite the manifest-wide registry path/status that simulation planning treats as authoritative.

### Evidence
- [src/flywire_wave/geometry_contract.py#L732](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L732) seeds `_coupling_contract` from `_first_coupling_bundle_metadata`, and [src/flywire_wave/geometry_contract.py#L855](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L855) selects the first `coupling_bundle` after sorting root IDs numerically.
- [src/flywire_wave/coupling_contract.py#L213](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L213) parses the sampled bundle, [src/flywire_wave/coupling_contract.py#L216](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L216) rebuilds the manifest header directory from that bundle's `local_synapse_registry.path`, and [src/flywire_wave/coupling_contract.py#L300](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L300) shows that each per-root bundle carries its own `local_synapse_registry` path/status.
- [src/flywire_wave/simulation_planning.py#L2983](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2983) loads `_coupling_contract`, [src/flywire_wave/simulation_planning.py#L2993](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2993) resolves `_coupling_contract.local_synapse_registry.path`, and [src/flywire_wave/simulation_planning.py#L3003](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3003) gates planning on that header status rather than a cross-root consistency check.
- [tests/test_geometry_contract.py#L119](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_geometry_contract.py#L119) and [tests/test_coupling_contract.py#L130](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_coupling_contract.py#L130) cover single-root happy paths only; there is no regression that exercises conflicting per-root coupling metadata or verifies that explicit `processed_coupling_dir` wins.

### Requested Change
Make `_coupling_contract` a manifest-owned record derived from explicit manifest inputs. The manifest writer should not infer the global `local_synapse_registry` location/status from a sampled root bundle, and an explicit `processed_coupling_dir` must not be overridden by per-root metadata. If per-root `coupling_bundle.assets.local_synapse_registry` entries disagree with the manifest-wide coupling location or readiness status, fail manifest construction with a clear error instead of serializing the lowest root's bundle into the header.

### Acceptance Criteria
- `_coupling_contract.local_synapse_registry.path` is derived from explicit manifest input when `processed_coupling_dir` is supplied, even if per-root `coupling_bundle_metadata` is present.
- Adding or removing a lower-root record with stale `coupling_bundle.assets.local_synapse_registry` metadata does not rewrite the manifest-wide coupling header.
- Conflicting per-root `local_synapse_registry` path or status values cause geometry manifest writing to fail clearly.
- Regression coverage includes a multi-root manifest with conflicting bundle metadata and a case where sampled bundle metadata disagrees with the explicit `processed_coupling_dir`.

### Verification
`python3 -m unittest tests.test_geometry_contract -v`; `python3 -m unittest tests.test_coupling_contract -v`; `python3 -m unittest tests.test_simulation_planning -v`

## APICPL-004 - Subset handoff contract remains duplicated in planners and readiness fixtures
- Status: open
- Priority: medium
- Source: api_boundaries_and_coupling review
- Area: selection / subset handoff

### Problem
`selection.py` already exposes `SubsetArtifactPaths` and `build_subset_artifact_paths()`, so the original "introduce a helper" framing is outdated. The remaining gap is that runtime planners and readiness fixtures still bypass that shared surface and rebuild subset directory naming, manifest lookup, or manifest serialization themselves. This is now a real drift risk, not just duplication: selection derives the safe subset directory directly from the preset name, while planners normalize subset identifiers differently before resolving paths. A subset name with case or punctuation differences can therefore resolve to different locations depending on which module touches it.

### Evidence
- [src/flywire_wave/selection.py#L131](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L131), [src/flywire_wave/selection.py#L142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L142), [src/flywire_wave/selection.py#L413](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L413), and [src/flywire_wave/selection.py#L582](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L582) already define the shared subset artifact paths, safe-name rule, and canonical subset manifest payload.
- [src/flywire_wave/whole_brain_context_planning.py#L1018](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1018) already consumes `build_subset_artifact_paths()`, showing that the shared contract is in active use elsewhere.
- [src/flywire_wave/simulation_planning.py#L2748](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2748) and [src/flywire_wave/simulation_planning.py#L2815](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2815) still open-code selected-root roster validation, subset path resolution, `subset_manifest.json` lookup, and manifest `root_ids` parsing.
- [src/flywire_wave/experiment_suite_planning.py#L1799](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L1799) and [src/flywire_wave/experiment_suite_planning.py#L1805](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L1805) independently derive the active-subset manifest path instead of using the selection-side helper.
- Readiness fixture builders still hand-write the same handoff artifacts in [src/flywire_wave/milestone9_readiness.py#L312](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone9_readiness.py#L312), [src/flywire_wave/milestone10_readiness.py#L389](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone10_readiness.py#L389), [src/flywire_wave/milestone11_readiness.py#L469](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone11_readiness.py#L469), [src/flywire_wave/milestone12_readiness.py#L603](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone12_readiness.py#L603), and [src/flywire_wave/milestone13_readiness.py#L834](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L834).

### Requested Change
Extend the existing selection-side subset helper, or add a small companion contract module beside it, so one library surface owns subset artifact path derivation plus subset-manifest read/write/validation and selected-root roster read/write routines. Route `simulation_planning.py`, `experiment_suite_planning.py`, and the milestone 9-13 readiness fixture builders through that surface instead of re-implementing filenames, safe-name handling, or manifest serialization.

### Acceptance Criteria
- The selection boundary is the only place that defines subset artifact filenames and preset-to-directory derivation.
- `simulation_planning.py` and `experiment_suite_planning.py` stop hardcoding `subset_manifest.json` or independently constructing subset manifest paths.
- Milestone 9-13 readiness fixtures stop hand-writing subset manifest JSON and selected-root roster text.
- A subset name containing mixed case or punctuation resolves to the same artifact directory when generated by selection code and later consumed by planners/readiness helpers.

### Verification
- `python3 -m unittest tests.test_selection tests.test_simulation_planning tests.test_whole_brain_context_planning tests.test_milestone9_readiness tests.test_milestone10_readiness tests.test_milestone11_readiness tests.test_milestone12_readiness tests.test_milestone13_readiness -v`
- Add or update a regression that builds subset artifacts from a mixed-case or punctuation-containing preset name and verifies selection generation, simulation planning, suite planning, and readiness fixture setup all resolve the same subset manifest path and root roster.

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

## EFFMOD-FW-003 - Reuse one resolved materialized simulation plan across experiment-suite stage execution
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: experiment suite execution

### Problem
The repository now already computes and persists a suite-level `base_simulation_plan`, but runtime work-item execution still drives stage entrypoints from materialized manifest/config file paths instead of a reusable resolved plan object. That means a single materialized suite cell can reparse config/manifest inputs and rebuild the same simulation plan several times during one run.

The duplication is broader than the original ticket text described. The simulation stage still resolves once to discover model modes and then resolves again inside `execute_manifest_simulation()` for each mode. The analysis stage also replans the same inputs to recover both the simulation plan and the embedded readout-analysis plan. The validation stage resolves a plan up front, then its layer workflows resolve the same plan again internally. For surface-wave cells, those extra resolutions still reopen operator bundles and rerun spectral-radius estimation, so the wasted work remains materially expensive.

### Evidence
- [experiment_suite_planning.py:359](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L359) resolves a suite `base_simulation_plan`, and [experiment_suite_execution.py:998](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L998) persists it, but the stage context built at [experiment_suite_execution.py:961](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L961) still carries materialized file paths rather than a resolved per-work-item plan.
- [experiment_suite_execution.py:552](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L552) resolves `simulation_plan` once for the simulation stage, then [experiment_suite_execution.py:571](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L571) calls `execute_manifest_simulation(...)` per `model_mode`; [simulator_execution.py:172](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L172) shows that helper immediately resolving the same plan again.
- [experiment_suite_execution.py:653](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L653) routes the analysis stage through `execute_experiment_comparison_workflow(...)`, which resolves the simulation plan at [experiment_comparison_analysis.py:464](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L464) and then calls `resolve_manifest_readout_analysis_plan(...)` at [experiment_comparison_analysis.py:470](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L470), which re-enters `resolve_manifest_simulation_plan(...)` at [simulation_planning.py:736](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L736).
- [experiment_suite_execution.py:742](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L742) resolves the validation stage `simulation_plan`, but layer workflows still replan internally: [validation_numerics.py:428](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_numerics.py#L428) and [validation_numerics.py:435](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_numerics.py#L435), [validation_circuit.py:326](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_circuit.py#L326), [validation_task.py:417](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_task.py#L417), and [validation_morphology.py:366](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_morphology.py#L366). If morphology has to backfill simulator metadata, it falls through to [validation_morphology.py:1099](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_morphology.py#L1099), which uses the same path-based simulator entrypoint.
- [simulation_planning.py:496](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L496) and [simulation_planning.py:508](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L508) show config/manifest/schema/design-lock loading on every plan resolution. For surface-wave arms, [simulation_planning.py:4313](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4313) triggers spectral-radius estimation, which reopens the operator payload at [simulation_planning.py:4776](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4776) and runs `eigsh` at [simulation_planning.py:4803](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4803).

### Requested Change
Refine this ticket around a per-work-item execution context rather than a new planner surface. After materialized inputs are written for a suite work item, resolve that materialized simulation plan once and carry it through stage execution. Extend simulation, analysis, and validation entrypoints so they can consume a pre-resolved `simulation_plan` directly, and let analysis/validation reuse embedded derived state such as `readout_analysis_plan`, resolved arm plans, and validation-plan inputs instead of round-tripping back through file-based resolvers.

Keep the existing path-based entrypoints as thin CLI wrappers, but make suite execution use the object path end-to-end. Memoize or persist surface-wave operator stability metadata within the resolved work-item plan so repeated stage/layer execution does not recompute spectral radius for the same operator bundle.

### Acceptance Criteria
- A suite work item resolves its materialized simulation plan once and reuses it across simulation, analysis, and validation stage execution for that cell.
- Executing multiple model modes for one materialized work item does not call `resolve_manifest_simulation_plan()` again after stage execution has started.
- Analysis execution consumes `simulation_plan["readout_analysis_plan"]` directly instead of calling `resolve_manifest_readout_analysis_plan()` for the same inputs.
- Validation layer workflows can consume the already resolved stage plan/context without reparsing the same manifest/config pair.
- Surface-wave spectral-radius estimation is computed once per unique operator bundle within a resolved work-item plan, or loaded from memoized plan metadata.

### Verification
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution tests.test_experiment_comparison_analysis tests.test_simulator_execution tests.test_validation_circuit tests.test_validation_morphology tests.test_validation_numerics tests.test_validation_task tests.test_validation_planning -v`
- `make smoke`

## OPS-001 - `make verify` does not validate the active `make meshes` prerequisite set
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: `scripts/00_verify_access.py` / mesh preflight parity

### Problem
`make verify` is still the documented preflight before `make meshes`, but it is not authoritative for the mesh step the repo actually runs today. The verifier can still throw an uncaught exception after CAVE client construction during the `client.info` lookup, it still downgrades `.env` token-sync failures to warnings, and it never checks the `navis` dependency that the default `meshing.fetch_skeletons: true` path requires. An operator can therefore see `Access looks good.` and then fail immediately in `make meshes` on missing `cloudvolume`, `fafbseg`, `navis`, or an unshaped info-service error.

### Evidence
- [README.md:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L59), [README.md:65](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L65), and [README.md:88](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L88) still present `make verify` as the access check before `make meshes` and as the first step of `make all`.
- [Makefile:108](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L108), [Makefile:117](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L117), and [Makefile:241](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L241) still wire `verify` as a separate preflight script ahead of the mesh-fetch target and the `all` pipeline.
- [scripts/00_verify_access.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L118) and [scripts/00_verify_access.py:119](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L119) call the info service outside the request error shaping used for client construction and materialize retries.
- [scripts/00_verify_access.py:166](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L166), [scripts/00_verify_access.py:180](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L180), [scripts/00_verify_access.py:184](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L184), and [scripts/00_verify_access.py:187](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L187) still catch mesh-client setup failures as warnings, then can emit a success path and return `0`.
- [src/flywire_wave/auth.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py#L16) and [src/flywire_wave/auth.py:29](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py#L29) show the `.env` token sync path depends on `cloudvolume` and `fafbseg`, which [scripts/02_fetch_meshes.py:83](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L83) and [scripts/02_fetch_meshes.py:89](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L89) still treat as fatal for `make meshes`.
- [config/local.yaml:104](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/config/local.yaml#L104) enables skeleton fetching by default, and [src/flywire_wave/mesh_pipeline.py:83](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L83), [src/flywire_wave/mesh_pipeline.py:91](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L91), and [src/flywire_wave/mesh_pipeline.py:341](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L341) show the default mesh path requires both `fafbseg` and `navis`, but `verify` never probes `navis` at all.

### Requested Change
Make `verify` authoritative for the active `make meshes` preflight instead of a looser CAVE/materialize probe. It should shape post-client `client.info` failures into explicit operator-facing errors, consult the current meshing config, and fail by default whenever the next `make meshes` step would immediately fail on missing auth/dependency setup. That includes the `.env` token-sync path from [src/flywire_wave/auth.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py) and `navis` when `meshing.fetch_skeletons` is enabled. If a lighter auth-only check is still wanted, require an explicit opt-in flag and label the result as partial/auth-only instead of printing `Access looks good.`

### Acceptance Criteria
- `make verify` exits non-zero for post-client info-service failures and prints a shaped auth/network/config error instead of a traceback.
- When `FLYWIRE_TOKEN` is provided, `make verify` exits non-zero if the token-sync path is unusable, including missing `cloudvolume`, missing `fafbseg`, or other secret-sync failures.
- When `meshing.fetch_skeletons` is `true`, `make verify` exits non-zero if `navis` is unavailable; when `meshing.fetch_skeletons` is `false`, `navis` is not treated as required.
- The full success path is only emitted after the same immediate dependency/auth setup that `make meshes` needs has been validated, or when the operator explicitly requested a partial/auth-only check.
- Each failing subcheck prints one actionable next step, such as install/bootstrap guidance for missing packages or token/network/config guidance for FlyWire access failures.

### Verification
- Run `make verify CONFIG=config/local.yaml` in an environment with working CAVE access and `FLYWIRE_TOKEN` set, but without `fafbseg` or with broken `cloudvolume` secret handling; it should exit non-zero with a targeted fix message.
- Run `make verify CONFIG=config/local.yaml` in an environment where the default `meshing.fetch_skeletons: true` config is active but `navis` is missing; it should exit non-zero before `make meshes` would fail.
- Run `make verify CONFIG=config/local.yaml` with an invalid datastack or forced info-service failure; it should return a shaped error, not a traceback.
- Run `make verify` against a config copy with `meshing.fetch_skeletons: false` in the same missing-`navis` environment; it should still succeed if the remaining mesh prerequisites are valid.
- Run `make verify CONFIG=config/local.yaml` in a fully provisioned environment; it should exit `0`.

## OPS-002 - Core CLI entrypoints still raise raw startup `ModuleNotFoundError` instead of bootstrap guidance
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: CLI startup dependency handling

### Problem
The repo now has partial dependency shaping inside `verify`, but the core preflight and pipeline scripts still import declared packages before any operator-facing error handling runs. When the active interpreter has not been bootstrapped into the repo environment, operators still get raw `ModuleNotFoundError` tracebacks instead of a concise message naming the missing package and pointing back to `make bootstrap`. Because the Makefile prefers `.venv/bin/python` when it exists, this is now mainly a first-run or bypassed-interpreter failure mode, but it still affects the documented recovery path.

### Evidence
- [Makefile:1](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L1) prefers `.venv/bin/python` when available, and [Makefile:103](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L103), [Makefile:108](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L108), [Makefile:114](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L114), [Makefile:117](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L117), and [Makefile:120](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L120) still dispatch directly to the vulnerable entrypoints.
- [scripts/00_verify_access.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L12) imports `dotenv` at module load even though the same script later defines `_fail_missing_dependency`, so missing `python-dotenv` bypasses the shaped error path.
- [scripts/01_select_subset.py:14](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/01_select_subset.py#L14) imports [src/flywire_wave/selection.py:14](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L14), which imports `networkx` at module load.
- [scripts/02_fetch_meshes.py:11](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L11), [scripts/02_fetch_meshes.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L12), and [scripts/02_fetch_meshes.py:32](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L32) import `dotenv`, `tqdm`, and [src/flywire_wave/mesh_pipeline.py:11](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L11) before any CLI guidance can run.
- [scripts/03_build_wave_assets.py:10](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L10) and [scripts/03_build_wave_assets.py:31](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L31) make `tqdm` and `trimesh` startup dependencies before any shaped failure path.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/00_verify_access.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'dotenv'`.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/01_select_subset.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'networkx'`.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/02_fetch_meshes.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'dotenv'`.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/03_build_wave_assets.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'tqdm'`.
- [tests/test_verify_access.py:15](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L15) covers shaped failures after `verify` is already importable, but there is no automated coverage for the startup missing-import path on `verify`, `select`, `meshes`, or `assets`.

### Requested Change
Add a shared startup dependency guard for the core operator entrypoints so missing declared packages are caught before module-level imports explode. At minimum, `verify`, `select`, `meshes`, and `assets` should fail with one concise operator-facing message that names the missing package and points to `make bootstrap`, regardless of whether the missing dependency is `python-dotenv`, `networkx`, `tqdm`, or `trimesh`.

### Acceptance Criteria
`make verify`, `make select`, `make meshes`, and `make assets` fail with concise operator messages when the active interpreter is missing required Python packages.

Those ordinary missing-package cases exit nonzero without emitting a Python traceback.

The shaped message names the missing package and points operators to `make bootstrap` or the equivalent install command.

At least one automated test covers the startup missing-import path for `verify`, and at least one automated test covers the same behavior for a pipeline command such as `select`, `meshes`, or `assets`.

### Verification
In an interpreter without `python-dotenv`, run `PYTHON=python3 make verify CONFIG=config/local.yaml` or `python3 scripts/00_verify_access.py --config config/local.yaml`; the command should fail without a traceback and should point to `make bootstrap`.

In an interpreter without `networkx`, run `PYTHON=python3 make select CONFIG=config/local.yaml`; the command should fail with an actionable dependency message instead of a raw import traceback.

In an interpreter without `python-dotenv`, `tqdm`, or `trimesh`, run `PYTHON=python3 make meshes CONFIG=config/local.yaml` and `PYTHON=python3 make assets CONFIG=config/local.yaml`; both commands should fail without a traceback and should point to `make bootstrap`.

Re-run `./.venv/bin/python -m unittest tests.test_verify_access -v` together with the new missing-dependency startup tests and confirm the shaped error path is covered.

## OPS-003 - `make preview` still aborts on the first missing required asset and writes no blocked report
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/05_preview_geometry.py` / `src/flywire_wave/geometry_preview.py` / `tests/test_geometry_preview.py`

### Problem
`make preview` is still the outlier among the local inspection/report commands. If any requested root is missing a required preview input, the CLI raises a traceback before it writes the deterministic preview bundle, so operators get neither a blocked summary nor an aggregate view of which roots are incomplete after a partial `make assets` run.

### Evidence
- [Makefile:123](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L123) and [Makefile:124](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L124) wire `make preview` directly to the preview CLI with no wrapper-level missing-asset handling.
- [scripts/05_preview_geometry.py:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/05_preview_geometry.py#L59) calls `generate_geometry_preview_report(...)` directly and only prints a summary after that returns.
- [src/flywire_wave/geometry_preview.py:64](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L64) builds all per-root entries before output writing; [src/flywire_wave/geometry_preview.py:100](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L100) and [src/flywire_wave/geometry_preview.py:101](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L101) only write `index.html` and `summary.json` after all entries succeed.
- [src/flywire_wave/geometry_preview.py:142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L142), [src/flywire_wave/geometry_preview.py:143](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L143), [src/flywire_wave/geometry_preview.py:144](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L144), and [src/flywire_wave/geometry_preview.py:145](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L145) hard-require the raw mesh, simplified mesh, surface graph, and patch graph; [src/flywire_wave/geometry_preview.py:799](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L799) raises `FileNotFoundError` on the first missing path.
- [tests/test_geometry_preview.py:20](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_geometry_preview.py#L20) covers only the deterministic happy path. There is no missing-prerequisite regression test for preview.
- Current repro on 2026-04-05: after generating assets for root `101` and deleting `101_patch_graph.npz`, running `scripts/05_preview_geometry.py --config <tmp>/config.yaml --root-id 101` exited with status `1`, printed a traceback ending in `FileNotFoundError: Missing preview input asset: .../101_patch_graph.npz`, and wrote neither `summary.json` nor `index.html`.
- The repo already has a blocked-report pattern for ordinary missing prerequisites in [src/flywire_wave/operator_qa.py:404](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/operator_qa.py#L404), [src/flywire_wave/coupling_inspection.py:493](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_inspection.py#L493), and [tests/test_operator_qa.py:125](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_operator_qa.py#L125).

### Requested Change
Align geometry preview with the repo’s existing blocked-report behavior for ordinary missing local prerequisites. The preview command should collect missing required preview inputs per root, write the deterministic output bundle anyway, and return a structured blocked summary instead of propagating `FileNotFoundError` to stderr.

### Acceptance Criteria
`make preview CONFIG=...` writes `summary.json` and `root_ids.txt` even when one or more requested roots are missing required preview inputs.
Ordinary missing-prerequisite cases do not emit a Python traceback; the command returns a structured blocked result instead of crashing.
The summary identifies blocked roots, missing asset keys, and resolved file paths, and it aggregates all missing prerequisites across the requested root set rather than stopping at the first miss.
The output tells the operator whether the missing prerequisite implies rerunning `make meshes`, `make assets`, or both.
A fully built root still produces the current happy-path preview output, and `tests/test_geometry_preview.py` gains a missing-prerequisite regression case.

### Verification
Create a local preview bundle with `make assets CONFIG=config/local.yaml`, remove one required preview input such as `<root_id>_patch_graph.npz`, then run `make preview CONFIG=config/local.yaml`.
Confirm that the command writes the deterministic preview output directory and a structured blocked summary naming the missing asset path and affected root IDs, without a traceback.
Repeat with multiple incomplete roots or multiple missing required assets to confirm the report aggregates all blocked prerequisites instead of aborting on the first miss.
Confirm that a fully built asset set still produces the existing happy-path preview HTML and summary.

## OPS-004 - Failed `make review-tickets` jobs still leave misleading `stderr.log` artifacts and hide the real failure logs
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/run_review_prompt_tickets.py` / `src/flywire_wave/review_prompt_tickets.py` / review-ticket tests

### Problem
The original ticket needs refinement, not closure. The README no longer promises per-job `stderr.log` artifacts, so this is no longer a docs-contract bug. The remaining issue is operational: `run_prompt_job()` still declares `stderr.log`, but it routes child stderr into stdout and then creates an empty `stderr.log`. When specialization or review fails, `make review-tickets` exits non-zero and prints stage progress plus `Summary written to ...`, but it still does not print a final per-failure artifact summary. Operators must open `summary.json` and then chase `stdout.jsonl` by hand to find the real diagnostics.

### Evidence
- [README.md:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L133) now documents only top-level review-run outputs, so OPS-004 should no longer claim that the README advertises per-job `stderr.log`.
- [src/flywire_wave/review_prompt_tickets.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L16) still lists `stderr.log` as a standard prompt-job artifact.
- [src/flywire_wave/review_prompt_tickets.py:261](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L261), [src/flywire_wave/review_prompt_tickets.py:293](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L293), and [src/flywire_wave/review_prompt_tickets.py:309](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L309) show the runner creates `stderr.log`, launches child jobs with `stderr=subprocess.STDOUT`, and backfills an empty `stderr.log` when none exists.
- [src/flywire_wave/review_prompt_tickets.py:688](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L688) and [src/flywire_wave/review_prompt_tickets.py:689](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L689) record stage results in `summary.json`, but the console surface does not expose those artifact paths directly.
- [scripts/run_review_prompt_tickets.py:176](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_review_prompt_tickets.py#L176) and [scripts/run_review_prompt_tickets.py:177](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_review_prompt_tickets.py#L177) only print the summary path and optional combined ticket path after the run.
- [tests/test_review_prompt_tickets.py:134](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_review_prompt_tickets.py#L134) and [tests/test_review_prompt_tickets.py:253](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_review_prompt_tickets.py#L253) cover successful workflow and refresh paths only, and [tests/test_run_review_prompt_tickets.py:29](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_run_review_prompt_tickets.py#L29) covers only `--dry-run`.
- Observed on April 5, 2026: running `python3 scripts/run_review_prompt_tickets.py --prompt-set efficiency_and_modularity --runner <failing-stub> --output-dir /tmp/...` exited `1`, printed only `Summary written to ...`, and left empty `specialization/efficiency_and_modularity/stderr.log` and `last_message.md` while the only failure text lived in `stdout.jsonl`.

### Requested Change
Keep scope limited to `make review-tickets`. Make the failure artifacts truthful and directly discoverable for specialization and review jobs. Either capture real child stderr separately, or stop materializing `stderr.log` and clearly document and report the combined log that actually contains diagnostics. Add an end-of-run failure summary that prints each failed prompt-set slug, stage, return code, and the exact artifact path or paths to inspect.

### Acceptance Criteria
A failed specialization or review job leaves at least one clearly named, non-empty diagnostic artifact whose filename matches the stream it actually contains.
The end-of-run console output lists every failed prompt set with its stage, return code, and the relevant artifact paths instead of only pointing to `summary.json`.
Automated coverage includes at least one failing `review-tickets` path and asserts both the non-zero exit and the failure-summary and artifact behavior.
Successful runs still write the documented review-run outputs under `agent_tickets/review_runs/<timestamp>/` without regressing combined ticket generation.

### Verification
Run `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set efficiency_and_modularity --runner <failing-stub> --output-dir /tmp/review-tickets-fail'`.
Confirm the command exits non-zero, prints the failing prompt set, stage, return code, and artifact path or paths to inspect, and that the named diagnostic artifact is non-empty and trustworthy.
Confirm a successful run still writes `specialization/<prompt-set>/specialized_prompt.md`, `reviews/<prompt-set>/tickets.md`, `combined_tickets.md`, and `summary.json` under the chosen review-run directory.

## FILECOH-001 - Reduce `simulation_planning.py` to manifest orchestration by extracting analysis and asset/runtime planning
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: simulation planning

### Problem
`simulation_planning.py` is still the single owner for manifest validation and normalization, readout-analysis planning, geometry/coupling asset readiness, surface-wave execution planning, and mixed-fidelity resolution. The module remains a central dependency for multiple planning and validation workflows, so routine changes to one seam still pull unrelated planning logic into the same file and review surface. The same cohesion problem shows up in tests: cross-suite fixture writers are still embedded in `test_simulation_planning.py` and imported by other test modules.

### Evidence
[simulation_planning.py:485](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L485) still loads config, validates the manifest, normalizes runtime config, resolves inputs, calls `_resolve_circuit_assets`, and assembles arm plans in one top-level path. Readout-analysis planning still begins at [simulation_planning.py:750](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L750), while circuit asset readiness and surface-wave execution or mixed-fidelity planning remain in [simulation_planning.py:2953](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2953), [simulation_planning.py:3409](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3409), and [simulation_planning.py:3670](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3670). Derived planning entrypoints also still live in the same module at [simulation_planning.py:729](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L729) and [simulation_planning.py:2318](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2318). Shared test helpers remain defined in [test_simulation_planning.py:979](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L979), [test_simulation_planning.py:1104](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L1104), [test_simulation_planning.py:1188](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L1188), and [test_simulation_planning.py:1479](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L1479), and are still imported by [test_simulator_execution.py:57](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L57), [test_experiment_suite_aggregation.py:37](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_aggregation.py#L37), [test_validation_circuit.py:76](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_circuit.py#L76), and [test_experiment_comparison_analysis.py:57](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L57).

### Requested Change
Keep `resolve_manifest_simulation_plan` as the manifest-orchestration entrypoint, but move readout-analysis planning into a dedicated analysis-planning module, move geometry/coupling readiness and asset resolution into a dedicated asset-resolution module, and move surface-wave execution plus mixed-fidelity planning into a dedicated runtime-planning module. `resolve_manifest_readout_analysis_plan` and `resolve_manifest_mixed_fidelity_plan` should remain available as thin entrypoints or compatibility wrappers so downstream callers do not need a flag-day import change.

### Acceptance Criteria
`simulation_planning.py` is reduced to manifest-level orchestration, shared normalization, and thin public wrappers, while readout-analysis planning, circuit asset readiness, and surface-wave or mixed-fidelity planning live in narrower modules with explicit imports. The public planning entrypoints continue to return the same shapes expected by current callers. Shared fixture writers are moved out of `test_simulation_planning.py` into a dedicated test support module, and tests that currently import from another test file switch to that support module instead.

### Verification
`make test`
`make validate-manifest`
`make smoke`

## FILECOH-002 - Reduce showcase session planning to orchestration by separating source resolution, narrative authoring, validation, and packaging
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: showcase session orchestration

### Problem
`showcase_session_planning.py` is still the main concentration point for four distinct concerns: resolving upstream showcase inputs, authoring narrative and preset content, validating rehearsal and dashboard-state patches, and assembling or writing package outputs. The repo now has a dedicated `showcase_session_contract.py`, so the remaining cohesion issue is specifically in the planner or orchestration layer rather than the contract-definition layer.

### Evidence
Contract and metadata helpers already live outside the planner in [showcase_session_contract.py:1168](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_contract.py#L1168) and [showcase_session_contract.py:1527](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_contract.py#L1527), but [showcase_session_planning.py:288](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L288) still resolves source mode, suite or dashboard or analysis or validation inputs, builds narrative context, presets, steps, artifact references, presentation state, script payload, preset catalog, export manifest, and output locations in one flow before returning a plan. Source and upstream artifact resolution remain inline at [showcase_session_planning.py:622](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L622), [showcase_session_planning.py:683](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L683), [showcase_session_planning.py:908](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L908), [showcase_session_planning.py:946](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L946), and [showcase_session_planning.py:1012](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L1012). Narrative and preset authoring remain inline at [showcase_session_planning.py:1497](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L1497), [showcase_session_planning.py:1982](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L1982), and [showcase_session_planning.py:3341](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3341). Package or output assembly is still owned by the same module at [showcase_session_planning.py:540](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L540), [showcase_session_planning.py:3756](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3756), [showcase_session_planning.py:3977](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3977), [showcase_session_planning.py:4019](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4019), [showcase_session_planning.py:4079](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4079), [showcase_session_planning.py:4128](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4128), and [showcase_session_planning.py:4162](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4162). Low-level presentation validation also remains in that file at [showcase_session_planning.py:4409](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4409), [showcase_session_planning.py:4479](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4479), and [showcase_session_planning.py:4817](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4817). The test coupling signal also still holds: [test_showcase_session_planning.py:70](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_showcase_session_planning.py#L70) and [test_showcase_session_planning.py:89](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_showcase_session_planning.py#L89) import fixture builders from peer test modules.

### Requested Change
Keep `showcase_session_contract.py` as the authority for contract and metadata helpers, and refactor `showcase_session_planning.py` so the top-level planner only composes separate collaborators for source and upstream artifact resolution, narrative or preset or step authoring, presentation-state and rehearsal/dashboard patch validation, and output or export-manifest assembly plus package writing. Move reusable showcase fixture materialization into a dedicated helper surface instead of importing it from peer test modules.

### Acceptance Criteria
A top-level showcase planner remains, but source resolution lives outside the narrative and packaging code path. Preset, narrative-context, and step generation no longer live in the same module as output-location, export-manifest, and package-writing helpers. Presentation-state, rehearsal-metadata, and dashboard-state patch validation live in a validation-focused module or helper surface instead of beside story authoring. Showcase tests no longer import `_materialize_dashboard_fixture` or `_materialize_packaged_suite_fixture` from peer test modules. The refactor does not move or duplicate contract metadata logic that is already owned by `showcase_session_contract.py`.

### Verification
`make test`
`make smoke`

## FILECOH-003 - Move whole-brain context query orchestration, preset hydration, and packaging out of the planning catch-all
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: whole-brain context session planning

### Problem
`whole_brain_context_planning.py` is still a 3,700+ line catch-all. The low-level query engine already lives in `whole_brain_context_query.py`, but the planning module still resolves source artifacts, constructs execution inputs, invokes the query engine inline, re-executes queries for every preset, injects downstream handoff targets, builds packaged session payload/catalog/state objects, and writes the bundle. Planning, preset hydration, presentation shaping, and package I/O remain collapsed into one module.

### Evidence
[whole_brain_context_query.py:243](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_query.py#L243) already owns `execute_whole_brain_context_query`, but [whole_brain_context_planning.py:188](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L188) still drives the full session flow and calls that executor inline at [whole_brain_context_planning.py:330](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L330), then immediately builds preset and packaged outputs at [whole_brain_context_planning.py:342](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L342), [whole_brain_context_planning.py:355](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L355), [whole_brain_context_planning.py:365](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L365), [whole_brain_context_planning.py:378](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L378), [whole_brain_context_planning.py:390](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L390), and [whole_brain_context_planning.py:407](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L407). `_build_query_preset_library` in the same file re-runs the query engine per preset at [whole_brain_context_planning.py:1928](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1928) and [whole_brain_context_planning.py:2025](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2025), then builds preset payloads there at [whole_brain_context_planning.py:2052](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2052). Packaging also remains in the planning module: [whole_brain_context_planning.py:448](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L448) conditionally packages linked dashboard state at [whole_brain_context_planning.py:470](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L470) and writes `context_view_payload`, `context_query_catalog`, and `context_view_state` JSON artifacts at [whole_brain_context_planning.py:489](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L489) and [whole_brain_context_planning.py:493](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L493). Downstream handoff mutation and packaged view assembly still live beside that logic at [whole_brain_context_planning.py:2536](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2536), [whole_brain_context_planning.py:2561](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2561), [whole_brain_context_planning.py:2751](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2751), [whole_brain_context_planning.py:2815](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2815), and [whole_brain_context_planning.py:2876](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2876). Planning tests continue to cover preset packaging and handoff lineage end-to-end in [test_whole_brain_context_planning.py:284](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_whole_brain_context_planning.py#L284) and [test_whole_brain_context_planning.py:485](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_whole_brain_context_planning.py#L485).

### Requested Change
Keep source-mode resolution, artifact discovery and override handling, selection resolution, and contract/query-profile selection in `whole_brain_context_planning.py`. Move session-level query orchestration behind a narrower query-facing layer that accepts resolved inputs and returns `query_execution`, hydrated preset results, and handoff-enriched query artifacts. Move `context_query_catalog`, `context_view_payload`, `context_view_state`, and bundle-write behavior behind a packaging-oriented module or service. The planner should orchestrate those components instead of re-running preset queries, mutating handoff payloads, and writing packaged artifacts itself.

### Acceptance Criteria
`resolve_whole_brain_context_session_plan` remains responsible for config, source context, artifact reference, selection, and query-state resolution, but it no longer calls `execute_whole_brain_context_query` or performs preset hydration inline inside `whole_brain_context_planning.py`. Per-preset execution is no longer implemented inside `_build_query_preset_library` in the planning module; preset hydration is owned by a narrower query or preset module whose name matches that responsibility. Downstream handoff enrichment for query results and preset payloads no longer lives in `whole_brain_context_planning.py`. `package_whole_brain_context_session` no longer performs dashboard sub-packaging or writes session JSON artifacts directly from the planning module; that work is owned by a packaging-oriented module. `whole_brain_context_planning.py` stops defining the builders for `context_query_catalog`, `context_view_payload`, and `context_view_state`, and planning tests focus on orchestration boundaries rather than preset packaging and handoff lineage.

### Verification
`make test`
`make validate-manifest`
`make smoke`

## FILECOH-004 - Separate experiment comparison discovery, core scoring, and analysis-bundle packaging behind a stable facade
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: experiment comparison workflow

### Problem
`experiment_comparison_analysis.py` is still a monolithic public entrypoint that mixes three distinct responsibilities: simulator bundle discovery and plan-alignment validation, core experiment comparison scoring or null-test evaluation, and analysis-bundle packaging for UI or offline report artifacts. The file has also become an integration surface for other workflows, so the refactor now needs to preserve the current import facade instead of treating this as a purely internal move.

### Evidence
The module is still 2,998 lines long and pulls in packaging dependencies at import time through [experiment_comparison_analysis.py:13](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L13) and [experiment_comparison_analysis.py:27](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L27). It defines bundle discovery at [experiment_comparison_analysis.py:87](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L87), core summary computation at [experiment_comparison_analysis.py:260](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L260), workflow coordination at [experiment_comparison_analysis.py:456](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L456), bundle packaging at [experiment_comparison_analysis.py:521](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L521), UI payload assembly at [experiment_comparison_analysis.py:871](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L871), bundle-vs-plan validation helpers starting at [experiment_comparison_analysis.py:1297](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L1297), null-test evaluation at [experiment_comparison_analysis.py:2300](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2300), task scoring at [experiment_comparison_analysis.py:2614](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2614), and output-summary assembly at [experiment_comparison_analysis.py:2771](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2771).

This module is also imported directly by downstream code, so callers currently depend on its public surface: the CLI at [20_experiment_comparison_analysis.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/20_experiment_comparison_analysis.py#L16), planning code at [validation_planning.py:17](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_planning.py#L17) and [dashboard_session_planning.py:88](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L88), validation code at [validation_circuit.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_circuit.py#L16), and suite execution at [experiment_suite_execution.py:651](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L651) and [experiment_suite_execution.py:741](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L741). Current tests also lock in packaging behavior and workflow reuse at [test_experiment_comparison_analysis.py:120](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L120), [test_experiment_comparison_analysis.py:195](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L195), and [test_experiment_comparison_analysis.py:346](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L346).

### Requested Change
Keep `experiment_comparison_analysis.py` as the stable public facade, but move its implementation seams into focused modules:
- a discovery module for bundle-set discovery, condition inference, and bundle-vs-plan validation
- a core comparison module for metric aggregation, null tests, task scoring, and output-summary assembly
- a packaging module for bundle metadata writing, export payload builders, visualization catalog assembly, UI payload assembly, and offline report handoff

`execute_experiment_comparison_workflow` should remain a thin coordinator over those modules, and existing public imports should continue to work for current callers.

### Acceptance Criteria
`discover_experiment_bundle_set` and its helper stack no longer live in the same implementation file as packaging or UI export builders.

`compute_experiment_comparison_summary` lives in a core analysis module that does not import report-generation or experiment-analysis bundle packaging helpers at module import time.

Packaging code consumes normalized summary or bundle inputs and owns export writing, UI payload generation, visualization catalog generation, and offline report packaging without re-owning comparison math.

`experiment_comparison_analysis.py` remains a compatibility facade exposing the current public entrypoints used by scripts, validation flows, dashboard planning, and suite execution.

Existing workflow behavior remains intact, including package generation, offline report regeneration from local artifacts, and accepting pre-resolved plans.

### Verification
`make test`
`make smoke`

## FILECOH-005 - Split simulator CLI and result-bundle packaging behind a stable execution facade
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: simulator execution workflow

### Problem
`simulator_execution.py` is still the stable public entrypoint for manifest-driven simulator runs, but it remains a 1,872-line mixed module that owns CLI parsing, baseline and surface-wave execution orchestration, extension artifact definitions, bundle writing, provenance serialization, and UI-facing comparison payload assembly. The original ticket is still accurate, but the current repo state makes the requirement sharper: preserve the execution API while extracting CLI and result-bundle packaging into dedicated seams.

### Evidence
[scripts/run_simulation.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_simulation.py#L12) still only imports `main` from the library, while [src/flywire_wave/simulator_execution.py:161](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L161) exposes the reusable workflow and [src/flywire_wave/simulator_execution.py:226](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L226) still owns `argparse` parsing. The same module defines extension artifact specs at [src/flywire_wave/simulator_execution.py:597](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L597) and [src/flywire_wave/simulator_execution.py:623](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L623), writes baseline and wave bundle outputs at [src/flywire_wave/simulator_execution.py:290](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L290) and [src/flywire_wave/simulator_execution.py:359](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L359), and builds provenance and UI/export payloads at [src/flywire_wave/simulator_execution.py:1587](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1587) and [src/flywire_wave/simulator_execution.py:1640](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1640). This is now a compatibility-sensitive surface: [src/flywire_wave/experiment_suite_execution.py:570](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L570) calls `execute_manifest_simulation` directly, [src/flywire_wave/dashboard_session_planning.py:1545](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1545) consumes the packaged `ui_comparison_payload` artifact from simulator bundle metadata, and [src/flywire_wave/wave_structure_analysis.py:834](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/wave_structure_analysis.py#L834) resolves `surface_wave_summary` and patch-trace artifacts from the same bundle inventory. Packaging behavior is also still locked into execution tests at [tests/test_simulator_execution.py:102](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L102), [tests/test_simulator_execution.py:266](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L266), [tests/test_simulator_execution.py:280](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L280), and [tests/test_simulator_execution.py:306](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L306). The bundle contract already has dedicated metadata/path helpers in [src/flywire_wave/simulator_result_contract.py:149](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_result_contract.py#L149), [src/flywire_wave/simulator_result_contract.py:378](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_result_contract.py#L378), and [src/flywire_wave/simulator_result_contract.py:817](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_result_contract.py#L817), so the remaining artifact packaging logic no longer belongs in the execution catch-all.

### Requested Change
Keep `execute_manifest_simulation` as the stable library facade and keep its return shape intact. Move CLI parsing and stdout formatting into `scripts/run_simulation.py` or a dedicated simulator CLI module. Move extension artifact-spec builders, bundle writes, provenance assembly, UI comparison payload construction, and wave-only extension serialization into a simulator packaging module that consumes normalized execution results plus the existing `simulator_result_contract` helpers. Preserve current artifact IDs, file formats, and executed-run summary fields so readiness, dashboard, wave-analysis, validation, and suite flows do not need a contract migration.

### Acceptance Criteria
`scripts/run_simulation.py` or a dedicated CLI sibling becomes the real CLI entrypoint, and `src/flywire_wave/simulator_execution.py` no longer imports `argparse` or owns command-line parsing. `execute_manifest_simulation` remains import-compatible for current callers, but artifact-spec declaration and package writing for `structured_log`, `execution_provenance`, `ui_comparison_payload`, `surface_wave_summary`, `surface_wave_patch_traces`, `surface_wave_coupling_events`, and `mixed_morphology_state_bundle` live outside `simulator_execution.py`. The current artifact IDs, bundle formats, and run-summary fields remain unchanged, and execution-focused tests can exercise orchestration without asserting all packaging payload details in the same module surface.

### Verification
`make test`
`make smoke`

## OVR-001 - Close stale duplicate resolver cleanup for `compare-analysis`
- Status: closed
- Priority: low
- Source: overengineering_and_abstraction_load review
- Area: experiment comparison analysis / simulation planning

### Problem
In the current workspace state, `compare-analysis` no longer has the duplicate manifest-resolution path this ticket described. `execute_experiment_comparison_workflow()` resolves `simulation_plan` once and reads `readout_analysis_plan` directly from that plan. The remaining `resolve_manifest_readout_analysis_plan()` helper is still present as a shared planning shim, but removing that helper repo-wide would be a different cleanup than the original `compare-analysis` bug.

### Evidence
- [src/flywire_wave/experiment_comparison_analysis.py#L36](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L36) resolves `simulation_plan` once, and [src/flywire_wave/experiment_comparison_analysis.py#L46](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L46) extracts `readout_analysis_plan` from `resolved_simulation_plan` instead of calling a second resolver.
- [Makefile#L150](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L150) routes `compare-analysis` through [scripts/20_experiment_comparison_analysis.py#L43](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/20_experiment_comparison_analysis.py#L43), which directly invokes `execute_experiment_comparison_workflow()`.
- [src/flywire_wave/simulation_planning.py#L729](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L729) still defines `resolve_manifest_readout_analysis_plan()`, but the current comparison workflow no longer uses it.
- [tests/test_experiment_comparison_analysis.py#L368](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_comparison_analysis.py#L368) covers the no-replanning path for a pre-resolved `simulation_plan`; `.venv/bin/python -m pytest -q tests/test_experiment_comparison_analysis.py` passes in the current workspace.

### Requested Change
No implementation work is needed under `OVR-001`. Close this ticket as already satisfied by the current `compare-analysis` workflow. If the team still wants to retire `resolve_manifest_readout_analysis_plan()` from shared APIs, that should be tracked separately rather than reopening this ticket.

### Acceptance Criteria
- `make compare-analysis` continues to execute through a single top-level simulation-plan resolution in `execute_experiment_comparison_workflow()`.
- `readout_analysis_plan` continues to be read from the resolved simulation plan rather than obtained by a second full resolver pass.
- `OVR-001` is closed with no code change required.

### Verification
- `.venv/bin/python -m pytest -q tests/test_experiment_comparison_analysis.py`

## OVR-002 - Duplicate review-side CLI-runner orchestration is already collapsed
- Status: closed
- Priority: low
- Source: overengineering_and_abstraction_load review
- Area: `agent_tickets` / `review_prompt_tickets`

### Problem
This ticket is stale. The repo no longer maintains multiple independent review-job launchers. Review flows already share one prompt-job executor, and the review path already reuses the shared stream/process setup from `agent_tickets`. The only remaining overlap is the smaller split between `run_ticket()` and `run_prompt_job()`, and that split still carries an intentional stderr-handling difference, so it is not the same cleanup this ticket originally described.

### Evidence
- [src/flywire_wave/review_prompt_tickets.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L12), [src/flywire_wave/review_prompt_tickets.py:358](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L358), and [src/flywire_wave/review_prompt_tickets.py:365](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L365) show the review runner already reuses the shared process-group and stream-handling helpers from `agent_tickets` instead of carrying its own copies.
- Review execution is already centralized on [src/flywire_wave/review_prompt_tickets.py:306](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L306) via [src/flywire_wave/review_prompt_tickets.py:514](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L514), [src/flywire_wave/review_prompt_tickets.py:618](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L618), and [src/flywire_wave/review_ticket_backlog.py:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_ticket_backlog.py#L133), so specialization, review, refresh, and backlog-review passes already go through one review-side launcher.
- The only remaining overlap is the narrower staging/artifact setup between [src/flywire_wave/agent_tickets.py:299](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L299) and [src/flywire_wave/review_prompt_tickets.py:306](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L306), but those paths still intentionally differ in stderr behavior at [src/flywire_wave/agent_tickets.py:365](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L365) and [src/flywire_wave/review_prompt_tickets.py:351](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L351).

### Requested Change
No implementation work remains for this ticket as written. Keep the current split unless a concrete bug or a new launcher path shows that the remaining ticket-vs-review differences are causing real drift.

### Acceptance Criteria
- Ticket stays closed because the duplicate review-side orchestration identified here has already been removed.
- No code change is required under OVR-002.

### Verification
- Inspect [src/flywire_wave/review_prompt_tickets.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L12), [src/flywire_wave/review_prompt_tickets.py:306](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L306), [src/flywire_wave/review_prompt_tickets.py:514](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L514), [src/flywire_wave/review_prompt_tickets.py:618](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L618), and [src/flywire_wave/review_ticket_backlog.py:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_ticket_backlog.py#L133).
- Inspect [src/flywire_wave/agent_tickets.py:299](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L299) and [src/flywire_wave/review_prompt_tickets.py:351](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L351) to confirm the only remaining overlap is the intentionally different ticket-vs-review execution behavior.

## OVR-003 - Remove the unused result-bundle metadata reconstruction path
- Status: open
- Priority: medium
- Source: overengineering_and_abstraction_load review
- Area: simulator packaging / manifest execution

### Problem
The original ticket target is now too broad and slightly misplaced. Top-level manifest execution no longer reconstructs bundle metadata itself, but simulator packaging still supports a second "partial arm plan" shape where `result_bundle.metadata` is missing and must be rebuilt from loose arm-plan fields. Current repo-owned planners always materialize normalized bundle metadata, and downstream consumers already assume that normalized shape directly. Keeping the packaging fallback preserves an unused second source of truth for bundle ids, artifact paths, and processed-results-dir resolution in the baseline and surface-wave manifest execution path.

### Evidence
- [src/flywire_wave/simulation_planning.py:681](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L681), [src/flywire_wave/simulation_planning.py:694](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L694), and [src/flywire_wave/simulation_planning.py:696](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L696) build and attach `result_bundle.metadata` for every planned arm.
- [src/flywire_wave/simulation_planning.py:1817](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L1817), [src/flywire_wave/simulation_planning.py:1840](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L1840), and [src/flywire_wave/simulation_planning.py:1841](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L1841) do the same when seed-sweep expansion produces per-seed run plans.
- [src/flywire_wave/simulator_execution.py:115](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L115) feeds planner-produced arm plans into execution, while [src/flywire_wave/simulator_packaging.py:287](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_packaging.py#L287) resolves bundle metadata during result packaging.
- [src/flywire_wave/simulator_packaging.py:336](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_packaging.py#L336), [src/flywire_wave/simulator_packaging.py:344](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_packaging.py#L344), [src/flywire_wave/simulator_packaging.py:373](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_packaging.py#L373), and [src/flywire_wave/simulator_packaging.py:385](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_packaging.py#L385) still support missing `result_bundle.metadata` by rebuilding metadata and carrying extra processed-results-dir resolution for that fallback.
- [src/flywire_wave/simulation_analysis_planning.py:1369](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_analysis_planning.py#L1369) and [src/flywire_wave/validation_morphology.py:1230](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_morphology.py#L1230) already require `arm_plan.result_bundle.metadata`, so downstream repo code is standardized on the normalized shape.
- [src/flywire_wave/milestone9_readiness.py:585](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone9_readiness.py#L585), [src/flywire_wave/milestone10_readiness.py:1107](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone10_readiness.py#L1107), [tests/test_simulator_execution.py:190](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L190), and [tests/test_simulator_execution.py:372](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L372) all treat the planner-produced bundle reference as the canonical execution identity.

### Requested Change
Require normalized `arm_plan.result_bundle.metadata` in manifest execution packaging and remove the fallback metadata reconstruction branch. Missing bundle metadata should raise a targeted error instead of synthesizing a second metadata representation from `manifest_reference`, `arm_reference`, `determinism`, `selected_assets`, and runtime fields. Keep this scoped to metadata reconstruction; low-level helpers that only tolerate an absent `result_bundle.reference` are out of scope unless they also rebuild metadata.

### Acceptance Criteria
- Manifest-driven packaging requires normalized `arm_plan.result_bundle.metadata`.
- Result packaging no longer rebuilds simulator-result bundle metadata from loose arm-plan fields.
- Missing bundle metadata fails clearly and early.
- Baseline and surface-wave manifest runs preserve the same `bundle_id`, `run_spec_hash`, and artifact paths recorded in planner-produced `result_bundle.reference` / `result_bundle.metadata`.

### Verification
- `make test`
- `make milestone9-readiness`
- `make milestone10-readiness`

## OVR-004 - Close: dashboard build API already reflects the repo’s supported multi-entry planning surface
- Status: closed
- Priority: low
- Source: overengineering_and_abstraction_load review
- Area: dashboard session planning / CLI / downstream integration

### Problem
The original ticket is no longer accurate for the repo’s current state. It assumes manifest-driven dashboard packaging is the only real public entry path and treats experiment-driven or metadata-driven planning as accidental abstraction. In the current repository, manifest-driven build is still the default `make` workflow, but the broader dashboard planning surface is now a documented, regression-tested, and downstream-used part of the shipped API.

### Evidence
- The default operator path is still manifest-driven via [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L153) and [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L156), but that is only the default entrypoint, not the full supported surface.
- The public CLI intentionally exposes manifest, experiment, and explicit metadata inputs at [scripts/29_dashboard_shell.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L62), [scripts/29_dashboard_shell.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L68), and [scripts/29_dashboard_shell.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L70).
- The planner still defines three source modes and already includes a manifest-specific wrapper, so a narrow manifest helper exists without removing the broader API at [src/flywire_wave/dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L137), [src/flywire_wave/dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L142), and [src/flywire_wave/dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L159).
- The current pipeline notes explicitly define `scripts/29_dashboard_shell.py build` as the canonical CLI for manifest-, experiment-, or bundle-driven inputs at [docs/pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L651).
- The shipped Milestone 14 readiness audit deliberately compares manifest-driven and experiment-driven planning through the public API at [src/flywire_wave/milestone14_readiness.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone14_readiness.py#L325).
- Downstream flows rely on these alternate modes: showcase planning resolves dashboard context from `experiment_id` at [src/flywire_wave/showcase_session_sources.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_sources.py#L511), and suite dashboard packaging injects packaged analysis and validation metadata paths into the planner at [src/flywire_wave/experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L924).
- Tests still lock in experiment/explicit convergence and precedence as supported behavior at [tests/test_dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L193) and [tests/test_dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L243).

### Requested Change
Close this ticket without implementation. Keep manifest-driven `make dashboard` and `make dashboard-open` as the default repo workflow, but do not narrow the public dashboard CLI or planner surface unless a future design change first removes multi-entry planning from the documented contract, readiness audit, downstream call sites, and regression tests.

### Acceptance Criteria
- The ticket is closed because the current repository intentionally supports manifest-, experiment-, and metadata-driven dashboard planning.
- Any future narrowing starts with a design and contract decision, followed by coordinated updates to docs, readiness coverage, downstream integrations, and tests.

### Verification
- Review current Make targets, CLI parser, planner API, pipeline notes, readiness audit, downstream dashboard consumers, and dashboard planning tests.

## FWW-MAINT-001 - Canonical active-subset publication and coupling refresh remain implicit in subset generation
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: selection pipeline

### Problem
`generate_subsets_from_config()` still mixes two responsibilities: generating subset artifacts for requested presets and publishing the canonical active subset used by the mesh/assets pipeline. The `active_preset` branch quietly writes `paths.selected_root_ids` and may rematerialize the subset-scoped synapse registry, while the CLI wrapper exposes only "generate subsets" as a single action. Newer whole-brain planning code now cross-checks subset artifacts against `paths.selected_root_ids`, so the ambiguity is narrower than the original ticket implied, but the selection-to-mesh/assets handoff still depends on hidden active-preset behavior.

### Evidence
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L382) defines `generate_subsets_from_config()` as the single entry point for both preset generation and active-subset publication.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L438) writes `paths.selected_root_ids` only inside the `name == active_preset` branch after per-preset artifacts have already been built.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L445) refreshes the synapse registry based on `processed_coupling_dir` or `synapse_source_csv` path-key presence, rather than an explicit publish step or named selection-pipeline action.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L475) returns only `active_preset` plus `generated_presets`; it does not report whether canonical root IDs or coupling artifacts were published.
- [scripts/01_select_subset.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/01_select_subset.py#L44) exposes only `generate_subsets_from_config()`, so the operator-facing selection command still has no distinct publish phase.
- [scripts/02_fetch_meshes.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L110) and [scripts/03_build_wave_assets.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L106) still consume `paths.selected_root_ids` as the canonical downstream roster.
- [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L21) and [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L116) still lock the root-id alias write and subset-scoped synapse-registry refresh into the selection contract.
- [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L856) already validates subset artifact root IDs against `paths.selected_root_ids`, which narrows this ticket to the selection/asset-prep flow rather than the broader planning/runtime stack.

### Requested Change
Refactor the selection pipeline so "build preset artifacts" and "publish canonical active subset" are separate, explicitly named steps, while preserving current output files and CLI behavior. The publish step should own any `selected_root_ids` alias update and any subset-scoped synapse-registry refresh, and the returned summary should say what was actually published.

### Acceptance Criteria
- The code has one explicit helper, phase, or orchestration step that publishes the canonical active subset used by downstream `meshes` and `assets` commands.
- Synapse-registry refresh is triggered as named publish behavior, not as incidental path-key checks embedded in the preset-generation loop.
- The selection summary/index records whether `paths.selected_root_ids` was updated and whether subset-scoped coupling artifacts were refreshed for the active preset.
- Existing selection outputs for generated preset artifacts remain unchanged apart from the addition of explicit publication metadata.

### Verification
`make test`

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

## FWW-MAINT-003 - Experiment-suite work-item `ready` remains contract-visible but unsupported by execution and packaging
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: experiment suite orchestration

### Problem
The repository still publishes `ready` as a canonical experiment-suite work-item status, but the current orchestration code does not treat it as a first-class persisted state. The planner only creates `planned` work items, stage executors may only return terminal statuses, executor resume logic rejects a persisted `ready` work item as unsupported, and package/result-index rollups still omit `ready` from their status tables. That leaves `ready` simultaneously documented and contract-valid, but not round-trippable through current execution state or packaging.

### Evidence
- [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L101) defines `WORK_ITEM_STATUS_READY`, includes it in `SUPPORTED_WORK_ITEM_STATUSES`, and [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L1894) gives it a distinct resumable status definition.
- [experiment_orchestration_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/experiment_orchestration_design.md#L111) and [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L704) still list `ready` in the canonical work-item taxonomy.
- [experiment_suite_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L2556) and [experiment_suite_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L2603) seed every work item as `planned`; the only `ready` writes in the planner are artifact-reference statuses at [experiment_suite_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L1543), so there is still no work-item producer for `ready`.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L77) excludes `ready` from `_SATISFIED_DEPENDENCY_STATUSES` and `_RETRYABLE_STATUSES`, and [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1270) raises `Unsupported orchestration status` for any persisted work item left in `ready`.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1575) only accepts `succeeded`, `partial`, `failed`, `blocked`, and `skipped` from stage executors, so executors cannot report `ready` even if the contract keeps advertising it.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1407) omits `ready` from state rollups and overall-status selection.
- [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L300) initializes stage-status counts without `ready`, [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L336) indexes those counts by the live stage status, and [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L105) plus [experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_packaging.py#L1524) also omit `ready` from cell rollup priority and cell-status counts.

### Requested Change
Make work-item status semantics single-sourced across contract, planner, execution-state transitions, and package/result-index rollups. Either remove `ready` from the public work-item taxonomy if it is not meant to persist, or implement it end-to-end as a supported persisted state with one shared transition/status model.

### Acceptance Criteria
- The public contract, docs, planner, executor, and package/result-index code recognize the same complete set of work-item statuses.
- The repository defines whether `ready` is a persisted work-item state, a transient internal decision, or unsupported, and that choice is enforced from one shared status model.
- If `ready` remains supported, persisted execution state and package generation can carry it without unsupported-status errors, missing-count rollups, or status-table failures.
- Regression coverage exercises the chosen `ready` behavior on both execution resume and package/result-index paths.

### Verification
`make test`

## FWW-MAINT-004 - Review-surface source resolvers still duplicate artifact-reference lifting and packaged bundle-alignment checks
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: review surface source resolution

### Problem
The original ticket’s `showcase_session_planning.py` citations are stale, because showcase upstream-reference assembly has been moved behind a helper. The underlying issue is still present, though: dashboard, showcase-source resolution, and whole-brain-context planning still each hand-lift bundle metadata into review-surface artifact references with repeated `bundle_id` / `artifact_id` / `format` / `artifact_scope` / `status` plumbing, and packaged dashboard alignment checks are still duplicated across loaders and validators. Contract metadata already carries artifact-hook catalogs for these surfaces, but the current source-resolution paths do not share one helper for “lift bundle metadata into artifact references,” “merge explicit overrides against hook defaults,” and “validate packaged bundle alignment.”

### Evidence
- [showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L130) now delegates upstream reference assembly to [showcase_session_sources.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_sources.py#L162), so the old showcase line references are outdated, but the helper still hand-builds dashboard, analysis, validation, and suite artifact references role by role through [showcase_session_sources.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_sources.py#L366).
- [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1333) still enumerates every upstream dashboard reference manually, including simulator UI payloads, offline reports, and linked whole-brain-context artifacts through [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1542).
- [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1051) separately rebuilds discovered subset, dashboard, and showcase references, and its dashboard/showcase-specific lift logic is duplicated again in [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1122).
- Explicit override merging is reimplemented in both [showcase_session_sources.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_sources.py#L959) and [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1205), each reading `contract_metadata["artifact_hook_catalog"]` and rebuilding the same fallback rules with slightly different status handling.
- Packaged dashboard bundle-alignment checks are duplicated in [showcase_session_sources.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_sources.py#L659), in packaged-context loading at [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1013), and again in whole-brain-context reference loaders at [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2174) and [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2265).
- Dashboard contract metadata already defines the authoritative role-to-artifact mapping in [dashboard_session_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_contract.py#L2169), but dashboard planning still bypasses that catalog when constructing upstream references in [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1333).

### Requested Change
Introduce shared review-surface helpers that use contract hook metadata to lift packaged bundle metadata and discovered paths into artifact references, merge explicit artifact overrides, and validate packaged dashboard/showcase bundle alignment. Keep this ticket scoped to the duplicated source-resolution and packaged-surface validation paths in dashboard, showcase-source resolution, and whole-brain-context planning; do not broaden it into a larger contract-schema rewrite unless a minimal hook-shape adjustment is required.

### Acceptance Criteria
- `dashboard_session_planning`, `showcase_session_sources`, and `whole_brain_context_planning` no longer each maintain separate role-by-role blocks for the same packaged dashboard/showcase-style artifact-reference lifting.
- Explicit artifact override merging is handled by a shared helper or shared abstraction reused by showcase and whole-brain-context paths.
- Packaged dashboard/showcase `bundle_id` alignment checks are centralized and reused wherever metadata, payload, and state are loaded or validated.
- Updating an upstream role’s `artifact_id`, scope, or required contract version requires changing one shared mapping/lift path rather than planner-specific copy blocks.

### Verification
`make test`
`pytest tests/test_dashboard_session_planning.py tests/test_showcase_session_planning.py tests/test_whole_brain_context_planning.py`

## TESTGAP-001 - Resume-state mismatch rejection lacks regression coverage
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: experiment suite execution

### Problem
`execute_experiment_suite_plan()` already rejects persisted resume state that does not match the current suite identity or normalized work-item ordering. The remaining gap is regression coverage: the test suite does not seed an incompatible `experiment_suite_execution_state.json` and prove that mismatched `suite_spec_hash` and `work_item_order` are rejected before resume side effects begin. If that guard regresses, a stale state file could be accepted and resume the wrong suite history without `make test` catching it.

### Evidence
- The persisted-state validation runs before state initialization, input persistence, and materialized-input preparation in [src/flywire_wave/experiment_suite_execution.py:129](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L129) and [src/flywire_wave/experiment_suite_execution.py:152](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L152).
- The explicit mismatch checks for `suite_spec_hash` and `work_item_order` live in [src/flywire_wave/experiment_suite_execution.py:1427](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1427).
- Existing execution coverage exercises compatible resume behavior and fail-fast resume recovery in [tests/test_experiment_suite_execution.py:60](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L60) and [tests/test_experiment_suite_execution.py:249](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L249), but there is still no negative-path test that seeds an incompatible persisted state and asserts the rejection path.

### Requested Change
Add a deterministic unit test in [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) that creates a valid persisted execution state, then mutates `suite_spec_hash` in one subcase and `work_item_order` in another. Assert that `execute_experiment_suite_plan()` raises immediately, with stub stage executors and a patched packaging hook so the test proves resume is rejected before any executor or packaging side effect runs.

### Acceptance Criteria
- Reusing a state file with a different `suite_spec_hash` raises a clear `ValueError`.
- Reusing a state file with a different `work_item_order` raises a clear `ValueError`.
- No stage executor is called after either mismatch is detected.
- `package_experiment_suite_outputs()` is not called after either mismatch is detected.
- The mismatched state file is left unchanged after the rejected resume attempt.

### Verification
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v`
- `make test`

## TESTGAP-002 - `validation-ladder package` edge cases and baseline writing still lack direct coverage
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: validation ladder packaging

### Problem
The repository now exercises packaged-ladder success behavior through the deterministic smoke fixture, but it still does not directly test the standalone `package` path or its package-specific failure modes. Current coverage does not prove that shuffled input order is normalized, that duplicate layer bundles are rejected, that missing required layers fail clearly, or that `scripts/27_validation_ladder.py package --write-baseline` writes the expected normalized regression snapshot.

### Evidence
- The package workflow is still documented in [docs/pipeline_notes.md:580](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L580) and exposed as [Makefile:191](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L191).
- The CLI has a distinct `package` subcommand plus standalone `--write-baseline` handling in [scripts/27_validation_ladder.py:69](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/27_validation_ladder.py#L69) and [scripts/27_validation_ladder.py:125](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/27_validation_ladder.py#L125).
- The implementation still contains explicit missing-layer and duplicate-layer checks in [src/flywire_wave/validation_reporting.py:570](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L570) and [src/flywire_wave/validation_reporting.py:705](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L705).
- Current ladder-package test coverage is still only the smoke fixture in [tests/test_validation_reporting.py:24](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_reporting.py#L24), and that workflow calls `package_validation_ladder_outputs()` with a fixed four-layer happy-path input order in [src/flywire_wave/validation_ladder_smoke.py:101](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_ladder_smoke.py#L101).
- `milestone13-readiness` now audits that `validation-ladder-package` is on the documented command surface, but its CLI check only runs `scripts/27_validation_ladder.py --help` and validates the generic help output rather than executing `package` with real bundles in [src/flywire_wave/milestone13_readiness.py:649](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L649) and [src/flywire_wave/milestone13_readiness.py:683](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L683).

### Requested Change
Add focused direct regression coverage for `package_validation_ladder_outputs()` and `scripts/27_validation_ladder.py package`, using tiny local layer bundles. Keep the scope limited to the currently untested package-path behaviors rather than duplicating the existing smoke happy path.

### Acceptance Criteria
- Packaging the same layer bundles in different input orders yields the same `bundle_id`, identical summary bytes, and normalized layer ordering.
- Supplying two bundles for the same `layer_id` fails clearly.
- Requiring the full ladder layer set and omitting one layer fails clearly.
- Running `scripts/27_validation_ladder.py package ... --write-baseline ...` writes the normalized regression baseline derived from the packaged summary.

### Verification
- `python -m unittest tests.test_validation_reporting -v` or `python -m unittest tests.test_validation_ladder_package -v`
- `make test`

## TESTGAP-003 - `--fail-fast` returned failed/partial stop path lacks direct regression coverage
- Status: open
- Priority: low
- Source: testing_and_verification_gaps review
- Area: experiment suite execution

### Problem
The original gap is no longer accurate as written: the repository now has direct regression coverage for exception-driven `fail_fast=True` stop/resume behavior and for packaging the resulting `ready` work items. The remaining untested branch is narrower: when a stage executor returns `failed` or `partial` status, or is normalized to `partial` because downstream artifacts are missing, `--fail-fast` should stop before any later work items run. That branch is separate from the exception path, so a regression could keep scheduling downstream work after a partial result while current fail-fast tests still pass.

### Evidence
- The public CLI still exposes `--fail-fast` and forwards it directly into workflow execution in [scripts/31_run_experiment_suite.py:51](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/31_run_experiment_suite.py#L51) and [scripts/31_run_experiment_suite.py:66](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/31_run_experiment_suite.py#L66).
- The executor has distinct fail-fast branches for exception handling and for returned failed/partial statuses in [src/flywire_wave/experiment_suite_execution.py:299](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L299), [src/flywire_wave/experiment_suite_execution.py:334](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L334), and [src/flywire_wave/experiment_suite_execution.py:349](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L349).
- Current execution coverage already exercises only the exception-driven fail-fast path and resume recovery in [tests/test_experiment_suite_execution.py:249](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L249).
- Current packaging coverage already exercises fail-fast-ready rollups after that same exception-driven stop in [tests/test_experiment_suite_packaging.py:281](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_packaging.py#L281).
- There is still no direct `WORK_ITEM_STATUS_PARTIAL` fail-fast assertion in [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py), [tests/test_experiment_suite_packaging.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_packaging.py), or [tests/test_milestone15_readiness.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_milestone15_readiness.py).

### Requested Change
Extend [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) with a deterministic `fail_fast=True` scenario where one stage returns `WORK_ITEM_STATUS_PARTIAL` or reports success with a missing downstream artifact so the executor normalizes it to `partial`. Assert that later work items are not attempted, then confirm a subsequent non-`fail_fast` rerun resumes from the stopped state. A subprocess-style CLI assertion for `scripts/31_run_experiment_suite.py --fail-fast` is optional and should stay limited to flag plumbing if the existing fixture is easy to reuse.

### Acceptance Criteria
- With `fail_fast=True`, execution stops after the first work item that returns `failed` or `partial`.
- The partial-status path created by missing downstream artifacts is covered directly.
- Later work items remain unattempted in persisted execution state.
- The stage call log proves no later executor ran after the first returned failed/partial result.
- A subsequent non-`fail_fast` rerun resumes from the stopped state.

### Verification
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution -v`
- `.venv/bin/python -m unittest tests.test_experiment_suite_packaging -v`
- `make test`

## TESTGAP-004 - `tests/test_verify_access.py` misses auth and `--require-materialize` regression branches
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: preprocessing readiness

### Problem
The original ticket is stale: this repo now has a local stubbed regression suite for `scripts/00_verify_access.py`, so the gap is no longer "no tests." The remaining issue is narrower. Current coverage exercises startup shaping, dependency failures, `--auth-only`, and a happy mesh-preflight path, but it does not drive the `CAVEclient` auth/init failure branches, the optional `--require-materialize` outage and invisible-version branches, or the successful token-sync messages. Regressions in those paths would still pass `make test` even though `make verify` remains the first step in `make all`.

### Evidence
- `make verify` still invokes the verify script, and `make all` still starts with `verify`, in [Makefile:108](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L108) and [Makefile:241](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L241).
- A stubbed verify suite already exists in [tests/test_verify_access.py:20](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L20), covering info-lookup failure shaping [tests/test_verify_access.py:34](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L34), auth-only mode [tests/test_verify_access.py:111](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L111), and a happy path [tests/test_verify_access.py:163](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L163).
- The helper always defaults `VERIFY_STUB_CAVE_INIT_MODE` to `ok` in [tests/test_verify_access.py:193](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L193), and although the stubbed `CAVEclient` supports `http401`, network, timeout, and generic init modes in [tests/test_verify_access.py:349](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L349), no test overrides them.
- The stubbed materialize client only returns a successful version/table response in [tests/test_verify_access.py:340](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L340), and no existing test passes `--require-materialize` through `_run_verify()` in [tests/test_verify_access.py:207](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L207).
- The unexercised production branches are the auth-specific HTTP handling in [scripts/00_verify_access.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L118), optional materialize probing in [scripts/00_verify_access.py:143](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L143) and [scripts/00_verify_access.py:378](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L378), invisible-version rejection in [scripts/00_verify_access.py:181](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L181), and token-sync success reporting in [scripts/00_verify_access.py:217](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L217), [scripts/00_verify_access.py:219](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L219), and [src/flywire_wave/auth.py:9](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py#L9).

### Requested Change
Extend [tests/test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py) rather than adding a new module. Add explicit stubbed cases for `CAVEclient` auth/init failures and for the `--require-materialize` path by making the materialize stub configurable for transient HTTP/network failures, invisible versions, and success. Add a success case with `FLYWIRE_TOKEN` plus `cloudvolume` and `fafbseg` stubs that asserts the token-sync outcome message.

### Acceptance Criteria
- A stubbed `CAVEclient` initialization or info lookup `401`/`403` returns exit code `1` and prints the auth-specific guidance about refreshing `FLYWIRE_TOKEN` or the local caveclient token.
- With `--require-materialize`, a transient materialize HTTP or network failure returns exit code `1` and prints the temporary-unavailability guidance.
- With `--require-materialize`, a requested materialization version that is not in the visible version list returns exit code `1` and names the requested version.
- A successful `--require-materialize` path prints `Requested version`, `Materialization versions visible`, `Tables`, and `Materialize access: OK`.
- A successful token-sync path prints either `FlyWire token sync: updated local secret storage` or `FlyWire token sync: already configured`, along with the existing `fafbseg setup: OK` success output.
- All cases run locally with stubs only and require no live FlyWire access.

### Verification
- `./.venv/bin/python -m unittest tests.test_verify_access -v`
- `make test`
