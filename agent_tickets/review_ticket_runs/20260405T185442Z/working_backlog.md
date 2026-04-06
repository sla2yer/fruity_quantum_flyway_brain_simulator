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

## FILECOH-004 - Split experiment comparison discovery, scoring, and export packaging
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: experiment comparison analysis

### Problem
`experiment_comparison_analysis.py` mixes filesystem bundle discovery, bundle-vs-plan validation, core comparison rollups, null-test evaluation, workflow orchestration, and UI or export packaging. That makes metric or null-test changes harder to review because the same file also owns report generation and artifact writing.

### Evidence
The file begins with bundle discovery at [experiment_comparison_analysis.py:84](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L84), computes the main summary at [experiment_comparison_analysis.py:255](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L255), orchestrates the full workflow at [experiment_comparison_analysis.py:451](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L451), packages bundle artifacts at [experiment_comparison_analysis.py:503](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L503), builds UI payloads at [experiment_comparison_analysis.py:853](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L853), evaluates null tests at [experiment_comparison_analysis.py:2142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2142), and assembles output summaries at [experiment_comparison_analysis.py:2613](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2613). Those are separate seams in this repo: discovery or validation, analysis, and packaging or export.

### Requested Change
Split the module into a bundle discovery or validation module, a core comparison computation module, and a packaging or export module for UI payloads and report artifacts. `execute_experiment_comparison_workflow` should remain as a thin coordinator across those boundaries.

### Acceptance Criteria
Bundle discovery and plan-alignment validation no longer live in the same file as null-test scoring and export payload builders. The analysis summary can be computed without importing packaging helpers, and the packaging path consumes a normalized summary object rather than re-owning analysis logic.

### Verification
`make test`
`make smoke`

## FILECOH-005 - Remove CLI and UI/export packaging concerns from simulator execution
- Status: open
- Priority: medium
- Source: file_length_and_cohesion review
- Area: simulator execution

### Problem
`simulator_execution.py` mixes a library workflow API, an argparse CLI entrypoint, baseline and surface-wave execution, bundle writing, provenance generation, and UI comparison payload assembly. That blurs the boundary between execution/runtime code and packaging or presentation code, and it leaves `scripts/run_simulation.py` as a trivial shim instead of the actual CLI surface.

### Evidence
[scripts/run_simulation.py:1](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_simulation.py#L1) only imports `main` from the library, while [simulator_execution.py:161](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L161) exposes the reusable execution workflow and [simulator_execution.py:221](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L221) still owns argparse parsing. The same module writes bundle artifacts in [simulator_execution.py:285](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L285) and [simulator_execution.py:354](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L354), then switches to provenance and UI payload shaping at [simulator_execution.py:1582](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1582) and [simulator_execution.py:1635](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1635). The tests also depend on simulation-planning fixture writers at [test_simulator_execution.py:56](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L56), which shows execution and planning surfaces are already too entangled.

### Requested Change
Move the CLI parser into `scripts/run_simulation.py` or a dedicated CLI wrapper, and move result-bundle packaging or UI payload generation behind a simulator packaging boundary. Keep the execution module focused on resolving runnable arm plans, invoking runtimes, and returning structured execution results.

### Acceptance Criteria
`src/flywire_wave/simulator_execution.py` no longer contains argparse handling or UI/export payload builders, and `scripts/run_simulation.py` becomes the real CLI entrypoint instead of a pass-through import. Execution helpers can be imported without pulling in packaging or presentation concerns.

### Verification
`make test`
`make smoke`

## overengineering_and_abstraction_load

# Overengineering And Abstraction Load Review Tickets

## OVR-001 - Remove the second full resolver from `compare-analysis`
- Status: open
- Priority: medium
- Source: overengineering_and_abstraction_load review
- Area: simulation planning / experiment comparison analysis

### Problem
The `make compare-analysis` path resolves the same manifest twice. `execute_experiment_comparison_workflow()` builds a full simulation plan, then asks for a separate readout-analysis plan through a helper that just rebuilds the same simulation plan and extracts one field. That extra abstraction hop does not buy a second real workflow in this repo.

### Evidence
- [src/flywire_wave/experiment_comparison_analysis.py:459](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L459) resolves `simulation_plan`, then [src/flywire_wave/experiment_comparison_analysis.py:465](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L465) resolves `analysis_plan` separately.
- [src/flywire_wave/simulation_planning.py:722](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L722) shows `resolve_manifest_readout_analysis_plan()` immediately calling [src/flywire_wave/simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) and only returning `readout_analysis_plan`.
- The public happy path is the single manifest-driven target at [Makefile:145](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L145), not two distinct planning backends.

### Requested Change
Resolve the manifest once in the comparison workflow and read `readout_analysis_plan` directly from that normalized simulation plan. If a helper is still wanted, make it a pure extractor from an existing plan rather than a second full resolver.

### Acceptance Criteria
- `execute_experiment_comparison_workflow()` performs one top-level manifest/config/schema/design-lock resolution.
- There is no public helper that re-runs full simulation planning solely to return `readout_analysis_plan`.
- Experiment-analysis outputs remain unchanged.

### Verification
- `make test`
- `make smoke`

## OVR-002 - Collapse duplicate CLI-runner orchestration in the review tooling
- Status: open
- Priority: medium
- Source: overengineering_and_abstraction_load review
- Area: `agent_tickets` / `review_prompt_tickets`

### Problem
The repo carries two near-identical subprocess wrappers for Codex/Codel jobs: one for agent tickets and one for review-prompt jobs. The only real extension point here is runner selection, which is already centralized. Maintaining two staging/streaming/artifact-sync implementations adds ceremony without adding a second meaningful backend.

### Evidence
- [src/flywire_wave/agent_tickets.py:299](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L299) and [src/flywire_wave/review_prompt_tickets.py:154](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L154) both create temp staging dirs, build the same `runner exec --json --cd ... --sandbox ... --output-last-message ...` command, stream output through [src/flywire_wave/agent_tickets.py:224](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L224), and return the same artifact paths.
- Artifact syncing is duplicated in [src/flywire_wave/agent_tickets.py:287](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/agent_tickets.py#L287) and [src/flywire_wave/review_prompt_tickets.py:142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L142).
- The review flow at [src/flywire_wave/review_prompt_tickets.py:335](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L335) exists only to run the repo’s `review-tickets` path from [Makefile:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L133), not to support a distinct job-execution platform.

### Requested Change
Introduce one shared CLI prompt-job executor and let both ticket execution and review-prompt execution compose it. Keep the specialization/review sequencing logic, but remove the duplicated subprocess/staging/artifact code.

### Acceptance Criteria
- Only one implementation owns subprocess spawning, stream handling, and artifact-sync for CLI-backed prompt jobs.
- `run_ticket()` and the review workflow still emit the same prompt/stdout/stderr/last-message artifacts and summaries.
- Existing ticket and review tests still pass.

### Verification
- `make test`
- `make smoke`

## OVR-003 - Remove the unused “partial arm plan” execution path
- Status: open
- Priority: high
- Source: overengineering_and_abstraction_load review
- Area: simulation planning / simulator execution

### Problem
Execution supports a second hypothetical arm-plan shape where bundle metadata is missing and must be reconstructed from fragments. The actual repo happy path never produces that shape: the planner already materializes `result_bundle.metadata` for every arm before execution. Carrying both shapes creates unnecessary indirection and a second source of truth in the core `baseline` / `surface_wave` path.

### Evidence
- [src/flywire_wave/simulation_planning.py:674](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L674), [src/flywire_wave/simulation_planning.py:686](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L686), and [src/flywire_wave/simulation_planning.py:687](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L687) always attach `result_bundle` metadata during plan construction.
- [src/flywire_wave/simulator_execution.py:172](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L172) and [src/flywire_wave/simulator_execution.py:178](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L178) feed those normalized arm plans straight into execution.
- [src/flywire_wave/simulator_execution.py:520](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L520) still falls back to rebuilding metadata from `manifest_reference`, `arm_reference`, `determinism`, `selected_assets`, and runtime state.

### Requested Change
Make planner-produced `result_bundle.metadata` the only supported execution input. Delete the fallback metadata reconstruction path and simplify processed-results-dir resolution around that single normalized arm-plan shape.

### Acceptance Criteria
- Simulator execution requires normalized arm plans with `result_bundle.metadata`.
- Missing bundle metadata fails clearly instead of silently reconstructing a second metadata representation.
- Baseline and surface-wave bundle ids, paths, and artifacts remain unchanged for manifest-driven runs.

### Verification
- `make test`
- `make milestone9-readiness`
- `make milestone10-readiness`

## OVR-004 - Narrow the dashboard build API to the repo’s real entry path
- Status: open
- Priority: high
- Source: overengineering_and_abstraction_load review
- Area: dashboard session planning / CLI

### Problem
Dashboard packaging is exposed as a generalized source-mode framework with manifest, experiment, and explicit per-bundle assembly modes. In this repo, the documented happy path is manifest-driven build plus open/export of an already packaged session. Keeping all three public acquisition modes makes the main local flow harder to understand and forces the planner to act like a bundle-orchestration framework the repo does not actually need.

### Evidence
- The documented workflow is manifest-driven at [Makefile:148](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L148) and [Makefile:151](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L151), with packaged-session export at [Makefile:154](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L154).
- The public CLI still exposes experiment and explicit bundle assembly knobs at [scripts/29_dashboard_shell.py:61](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L61) and [scripts/29_dashboard_shell.py:68](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L68).
- The planner defines three source modes at [src/flywire_wave/dashboard_session_planning.py:136](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L136) and exposes a broad multi-input public signature at [src/flywire_wave/dashboard_session_planning.py:158](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L158).
- The alternate modes are actively maintained for equivalence in [tests/test_dashboard_session_planning.py:193](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L193) and [tests/test_dashboard_session_planning.py:243](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L243).

### Requested Change
Keep one public dashboard build path centered on manifest-driven planning, plus the existing open/export operations on packaged sessions. If explicit bundle assembly is still useful for fixtures, move it behind a private helper instead of the public CLI and public planner signature.

### Acceptance Criteria
- `scripts/29_dashboard_shell.py build` and `resolve_dashboard_session_plan()` no longer advertise three equivalent acquisition modes publicly.
- `make dashboard`, `make dashboard-open`, and packaged-session export behavior remain intact.
- Fixture-only alternate assembly, if retained, is internal rather than part of the main user-facing API.

### Verification
- `make test`
- `make milestone14-readiness`

## readability_and_maintainability

# Readability And Maintainability Review Tickets

## FWW-MAINT-001 - Active subset publication is hidden inside preset generation
- Status: open
- Priority: high
- Source: readability_and_maintainability review
- Area: subset selection

### Problem
The canonical selected-root roster for the rest of the pipeline is not modeled as its own step. Instead, `generate_subsets_from_config()` quietly publishes one preset as the authoritative `selected_root_ids` alias and may also refresh the subset-scoped synapse registry as a side effect of iterating generated presets. That makes it hard to tell which subset output is authoritative for `select -> meshes -> assets -> simulation`, and maintainers have to remember that the active preset has extra behavior that other generated presets do not.

### Evidence
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L257) loops over all requested presets, but only the `active_preset` branch writes `paths.selected_root_ids` and conditionally calls `materialize_synapse_registry()`.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L283) ties synapse-registry refresh to the presence of `processed_coupling_dir` or `synapse_source_csv`, so the canonical coupling side effect is controlled by path-key presence rather than an explicit publish step.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L313) returns only `active_preset` plus generated artifact paths; it does not record whether the canonical alias or subset-scoped coupling registry was actually refreshed.
- [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L19) and [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L114) show that this hidden side effect is part of the external contract.

### Requested Change
Separate “build preset artifacts” from “publish canonical active subset” into explicit steps or helpers, and return structured metadata showing which preset became the authoritative root roster and whether subset-scoped coupling artifacts were refreshed.

### Acceptance Criteria
- The code has one explicit helper or phase that publishes the canonical active subset used downstream.
- The conditions for refreshing the subset-scoped synapse registry are expressed as named selection-pipeline behavior, not as incidental path-key checks inside the preset loop.
- The returned summary clearly states which preset, if any, updated `selected_root_ids` and coupling-side artifacts.

### Verification
`make test`

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

## FWW-MAINT-003 - Experiment-suite status taxonomy and executor semantics diverge on `ready`
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: experiment suite orchestration

### Problem
The experiment-suite contract advertises `ready` as a real work-item status with its own semantics, but the executor and state rollups do not model it. That leaves maintainers unable to tell whether `ready` is a dead status, an intended persisted transition, or something external tooling is allowed to write.

### Evidence
- [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L101) includes `WORK_ITEM_STATUS_READY` in the supported status set.
- [experiment_suite_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_contract.py#L1894) gives `ready` a distinct description and marks it resumable, implying it is part of the authoritative orchestration state machine.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L77) excludes `ready` from `_SATISFIED_DEPENDENCY_STATUSES` and `_RETRYABLE_STATUSES`.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1201) therefore treats a persisted `ready` work item as an unsupported status.
- [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1338) omits `ready` from `status_counts` and `overall_status`, while initialization only seeds `planned` items at [experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1282).

### Requested Change
Make the status machine single-sourced. Either remove `ready` from the public contract if it is not meant to persist, or implement full executor, dependency, and rollup handling for it from the same transition table.

### Acceptance Criteria
- The public contract and executor recognize the same complete set of work-item statuses.
- Transition, retry, dependency-satisfaction, and rollup rules come from one shared status model.
- If `ready` remains supported, persisted execution state can carry it without raising unsupported-status errors.

### Verification
`make test`

## FWW-MAINT-004 - Review-surface packagers hand-build the same artifact-reference logic in multiple modules
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: packaged review surfaces

### Problem
Dashboard, showcase, and whole-brain-context planners repeatedly hand-assemble artifact-reference payloads from upstream bundle metadata and then re-check the same bundle-alignment invariants. That obscures which fields are authoritative for packaged review surfaces: discovered bundle paths, metadata `artifacts`, explicit overrides, or copied session references. Any contract change to artifact IDs, scopes, or required alignment now needs synchronized edits across several large modules.

### Evidence
- [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1359) manually maps each upstream artifact into dashboard references by repeating `bundle_id`, `artifact_id`, `format`, `artifact_scope`, and `status`.
- [showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3756) repeats the same pattern for dashboard, analysis, validation, and suite artifacts, then maintains a separate explicit-override merge path at [showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4203).
- [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1185) builds yet another artifact-reference catalog for subset, dashboard, showcase, and connectivity artifacts.
- The same `bundle_id` alignment rule for dashboard metadata/payload/state is duplicated in [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1134), [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3336), [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3419), and [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3443).

### Requested Change
Introduce shared helpers for “lift bundle metadata into artifact references” and “validate packaged bundle alignment”, with declarative role-to-artifact mappings reused by dashboard, showcase, and whole-brain-context planners.

### Acceptance Criteria
- Artifact-reference construction for packaged review surfaces is driven by shared helpers or declarative maps rather than repeated hand-written blocks.
- Bundle-alignment checks for packaged dashboard/showcase/session records are centralized.
- A contract change to an upstream artifact role or artifact ID requires updating one shared mapping path, not each planner separately.

### Verification
`make test`

## testing_and_verification_gaps

# Testing And Verification Gaps Review Tickets

## TESTGAP-001 - Resume-state mismatch rejection is not protected
- Status: open
- Priority: high
- Source: testing_and_verification_gaps review
- Area: experiment suite execution

### Problem
A stale `experiment_suite_execution_state.json` can only be resumed safely if it still matches the current suite identity and work-item ordering. That guard exists in code, but there is no test that seeds an incompatible state file and proves the workflow refuses to reuse it. A regression here could silently resume the wrong suite, skip the wrong work items, or reuse stale packaged outputs without `make test` or `make milestone15-readiness` catching it.

### Evidence
- The mismatch checks for `suite_id`, `suite_spec_hash`, and `work_item_order` live in [src/flywire_wave/experiment_suite_execution.py:1366](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L1366).
- Existing coverage only exercises the happy-path resume flow in [tests/test_experiment_suite_execution.py:58](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L58).
- The Milestone 15 readiness test only verifies the default readiness report path and does not seed an incompatible persisted state in [tests/test_milestone15_readiness.py:21](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_milestone15_readiness.py#L21).

### Requested Change
Add a deterministic unit test in [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) that writes a persisted execution-state fixture with a mismatched `suite_spec_hash` and a separate fixture with a mismatched `work_item_order`, then asserts `execute_experiment_suite_plan()` fails before any stage executor runs or package output is refreshed.

### Acceptance Criteria
- Reusing a state file with a different `suite_spec_hash` raises a clear `ValueError`.
- Reusing a state file with a different `work_item_order` raises a clear `ValueError`.
- No stage executor is called after either mismatch is detected.
- The mismatched state file is left unchanged after the rejected resume attempt.

### Verification
- `python -m unittest tests.test_experiment_suite_execution -v`
- `make test`

## TESTGAP-002 - `validation-ladder-package` is only covered indirectly through the smoke fixture
- Status: open
- Priority: high
- Source: testing_and_verification_gaps review
- Area: validation ladder packaging

### Problem
The repo documents `scripts/27_validation_ladder.py package` and `make validation-ladder-package` as the path for packaging existing per-layer `validation_bundle.json` artifacts. Current verification only covers the synthetic smoke workflow, not the package path that real numerical, morphology, circuit, and task runs hand off into. A regression in duplicate-layer rejection, required-layer enforcement, input-order normalization, or baseline writing could break real ladder packaging while `make validation-ladder-smoke` and `make milestone13-readiness` still pass.

### Evidence
- The documented package workflow is in [docs/pipeline_notes.md:576](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L576) and the Make target is in [Makefile:186](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L186).
- The package implementation has explicit checks for required layers and duplicate layer IDs in [src/flywire_wave/validation_reporting.py:558](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L558) and [src/flywire_wave/validation_reporting.py:681](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_reporting.py#L681).
- Current test coverage only runs the smoke fixture in [tests/test_validation_reporting.py:24](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_reporting.py#L24).
- Milestone 13 readiness also shells only the `smoke` subcommand in [src/flywire_wave/milestone13_readiness.py:487](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L487).

### Requested Change
Add a deterministic packaging test module, preferably [tests/test_validation_ladder_package.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_validation_ladder_package.py), that materializes tiny local layer bundles and directly exercises `package_validation_ladder_outputs()` plus `scripts/27_validation_ladder.py package`. Include one shuffled-order success case, one duplicate-layer failure case, one missing-required-layer failure case, and one `--write-baseline` assertion.

### Acceptance Criteria
- Packaging the same layer bundles in different input orders yields the same `bundle_id`, summary bytes, and layer ordering.
- Supplying two bundles for the same `layer_id` fails clearly.
- Requiring all four ladder layers and omitting one fails clearly.
- `--write-baseline` writes a normalized regression baseline from the packaged summary.

### Verification
- `python -m unittest tests.test_validation_ladder_package -v`
- `make test`

## TESTGAP-003 - `--fail-fast` suite execution behavior is untested
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: experiment suite execution CLI

### Problem
The suite runner exposes a `--fail-fast` mode that should stop scheduling after the first failed or partial work item. That branch is separate from the default resume path and is not exercised by current tests or readiness. A regression could keep launching downstream stages after the first failure, contaminating persisted state and review packages, while the existing orchestration tests still pass.

### Evidence
- The CLI flag is part of the public command surface in [scripts/31_run_experiment_suite.py:50](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/31_run_experiment_suite.py#L50).
- The executor has dedicated `fail_fast` break logic on exceptions and failed or partial statuses in [src/flywire_wave/experiment_suite_execution.py:334](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L334) and [src/flywire_wave/experiment_suite_execution.py:349](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L349).
- No test references `fail_fast`; current suite execution coverage only uses the default behavior in [tests/test_experiment_suite_execution.py:58](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py#L58).
- Milestone 15 readiness also exercises only the default workflow path in [tests/test_milestone15_readiness.py:41](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_milestone15_readiness.py#L41).

### Requested Change
Extend [tests/test_experiment_suite_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_execution.py) with a deterministic `fail_fast=True` scenario that forces one simulation work item to fail, then asserts later work items are not attempted. Add one subprocess-style assertion against `scripts/31_run_experiment_suite.py --fail-fast` if the CLI surface is easy to reuse from the same fixture.

### Acceptance Criteria
- With `fail_fast=True`, execution stops after the first failed or partial work item.
- Later work items remain unattempted in the persisted execution state.
- The stage call log proves no downstream executor ran after the first failing item.
- A subsequent non-`fail_fast` rerun can resume from the stopped state.

### Verification
- `python -m unittest tests.test_experiment_suite_execution -v`
- `make test`

## TESTGAP-004 - `make verify` has no stubbed regression coverage for auth, outage, or version handling
- Status: open
- Priority: medium
- Source: testing_and_verification_gaps review
- Area: preprocessing readiness

### Problem
`make all` starts with `make verify`, and `scripts/00_verify_access.py` contains nontrivial classification logic for auth failures, transient materialize outages, `--require-materialize`, missing materialization version `783`, and fafbseg token syncing. None of that is protected by a local deterministic test. A regression could misclassify token failure as a temporary outage or allow the wrong materialization version through without `make test`, `make smoke`, or any readiness command noticing.

### Evidence
- The setup docs make `make verify` part of the normal access check and `make all` entry sequence in [README.md:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L59) and [README.md:88](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L88).
- The verify script contains retry and exit-code logic for auth, transient HTTP/network errors, and materialization visibility in [scripts/00_verify_access.py:36](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L36), [scripts/00_verify_access.py:102](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L102), and [scripts/00_verify_access.py:127](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L127).
- Secret-sync behavior is implemented separately in [src/flywire_wave/auth.py:9](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/auth.py#L9).
- No test file references `scripts/00_verify_access.py` or `ensure_flywire_secret`.

### Requested Change
Add a fully local test module, preferably [tests/test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py), that stubs `caveclient`, `requests`, `fafbseg`, and `cloudvolume` and executes `scripts/00_verify_access.py` or `main()` directly. Cover at least: 401 auth failure, transient materialize outage with and without `--require-materialize`, requested materialization version not visible, and successful token-sync plus dataset selection.

### Acceptance Criteria
- Auth failure returns exit code `1` with the auth-specific guidance text.
- Transient materialize unavailability returns `0` by default and `2` with `--require-materialize`.
- Invisible materialization version returns `1` and names the requested version.
- Success path prints the configured datastack, materialization version, and fafbseg token-sync outcome.
- All of the above run without live FlyWire access.

### Verification
- `python -m unittest tests.test_verify_access -v`
- `make test`
