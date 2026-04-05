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

## APICPL-002 - Experiment bundle discovery is implemented as directory globbing instead of contract-owned lookup
- Status: open
- Priority: high
- Source: api_boundaries_and_coupling review
- Area: experiment analysis / dashboard planning

### Problem
Several planners discover packaged bundles by rebuilding directory layout and metadata filenames instead of asking a contract-owned helper to resolve them from plan identity. That leaks filename and folder ownership into higher-level workflows and makes stray files under an experiment directory part of discovery policy.

### Evidence
- `[src/flywire_wave/experiment_comparison_analysis.py#L149](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L149)` constructs `.../bundles/<experiment_id>/<arm_id>/`, and `[src/flywire_wave/experiment_comparison_analysis.py#L152](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L152)` globs `*/simulator_result_bundle.json`.
- `[src/flywire_wave/dashboard_session_planning.py#L260](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L260)` already has a manifest-derived `bundle_set`, but `[src/flywire_wave/dashboard_session_planning.py#L674](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L674)` and `[src/flywire_wave/dashboard_session_planning.py#L725](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L725)` still glob analysis and validation bundle metadata under hardcoded contract filenames.
- `[src/flywire_wave/validation_planning.py#L476](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_planning.py#L476)` shows the better pattern: derive the expected analysis bundle path from plan identity via contract helpers instead of scanning the filesystem.

### Requested Change
Add contract-owned discovery APIs for simulator, experiment-analysis, and validation bundle metadata lookup from plan identity or bundle ids, and replace raw `glob("*/...json")` discovery in `experiment_comparison_analysis.py` and `dashboard_session_planning.py`.

### Acceptance Criteria
High-level planners no longer hardcode `*/simulator_result_bundle.json`, `*/experiment_analysis_bundle.json`, or `*/validation_bundle.json` discovery. Discovery remains stable if on-disk naming changes behind the contract helpers.

### Verification
`python3 -m unittest tests.test_experiment_comparison_analysis -v`; `python3 -m unittest tests.test_simulation_planning -v`; `python3 -m unittest tests.test_dashboard_session_planning -v` after full dev dependencies are installed (`trimesh` is missing in this environment).

## APICPL-003 - Geometry manifest `_coupling_contract` header is derived from whichever root record sorts first
- Status: open
- Priority: high
- Source: api_boundaries_and_coupling review
- Area: geometry / coupling manifest contract

### Problem
The manifest-level coupling header is treated as the authoritative global seam for `synapse_registry.csv`, but it is currently synthesized from one per-root `coupling_bundle`. That makes a global contract depend on record order and allows stale or mixed per-root coupling metadata to silently rewrite the header that simulation planning trusts.

### Evidence
- `[src/flywire_wave/geometry_contract.py#L732](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L732)` seeds `_coupling_contract` from `_first_coupling_bundle_metadata`, and `[src/flywire_wave/geometry_contract.py#L852](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_contract.py#L852)` returns the first root’s `coupling_bundle`.
- `[src/flywire_wave/coupling_contract.py#L213](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_contract.py#L213)` then overrides the caller-provided `processed_coupling_dir` with the path embedded in that sampled bundle metadata.
- `[src/flywire_wave/simulation_planning.py#L2978](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2978)` through `[src/flywire_wave/simulation_planning.py#L3003](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3003)` consume `_coupling_contract.local_synapse_registry` as the authoritative plan input.

### Requested Change
Make manifest-level coupling metadata a canonical manifest-owned record built from explicit manifest inputs, not from a sampled root bundle. If per-root coupling bundles disagree about the shared coupling registry location or status, manifest writing should fail instead of serializing whichever root happens to come first.

### Acceptance Criteria
`_coupling_contract.local_synapse_registry` is stable under root reordering, and inconsistent per-root coupling metadata cannot produce a misleading manifest header.

### Verification
`python3 -m unittest tests.test_coupling_contract -v`; `python3 -m unittest tests.test_simulation_planning -v`; add regressions that swap record order and that inject conflicting per-root coupling metadata.

## APICPL-004 - Subset handoff contract is duplicated across selection, planners, and readiness fixtures
- Status: open
- Priority: medium
- Source: api_boundaries_and_coupling review
- Area: selection / subset handoff

### Problem
`selected_root_ids.txt` and `subset_manifest.json` are public pipeline handoff artifacts, but their filenames, safe-name rules, and JSON payload shape are reconstructed in multiple modules instead of being owned by one library contract. Any future change to subset metadata or naming has to be coordinated manually across planning and readiness code.

### Evidence
- `[src/flywire_wave/selection.py#L103](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L103)`, `[src/flywire_wave/selection.py#L142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L142)`, and `[src/flywire_wave/selection.py#L413](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L413)` define the canonical subset artifact names and payload shape.
- `[src/flywire_wave/simulation_planning.py#L176](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L176)` and `[src/flywire_wave/simulation_planning.py#L2823](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2823)` duplicate the subset-manifest filename and path resolution.
- `[src/flywire_wave/experiment_suite_planning.py#L1806](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L1806)` hardcodes the same filename again.
- Readiness fixtures hand-write the same contract in `[src/flywire_wave/milestone9_readiness.py#L315](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone9_readiness.py#L315)`, `[src/flywire_wave/milestone10_readiness.py#L392](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone10_readiness.py#L392)`, `[src/flywire_wave/milestone11_readiness.py#L472](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone11_readiness.py#L472)`, `[src/flywire_wave/milestone12_readiness.py#L610](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone12_readiness.py#L610)`, and `[src/flywire_wave/milestone13_readiness.py#L838](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L838)`.

### Requested Change
Introduce a small selection/subset contract helper that owns subset artifact path building, safe-name normalization, manifest serialization/parsing, and active-root roster references. Route selection generation, simulation planning, suite planning, and readiness fixture writers through that helper.

### Acceptance Criteria
One library surface owns `subset_manifest.json` and selected-root roster semantics, and downstream consumers stop hardcoding the filename or manually serializing subset manifest payloads.

### Verification
`python3 -m unittest tests.test_simulation_planning -v`; `python3 -m unittest tests.test_selection -v` after installing `networkx`; add readiness-fixture regressions that round-trip generated subset references through the shared helper.

## efficiency_and_modularity

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

## error_handling_and_operability

# Error Handling And Operability Review Tickets

## OPS-001 - `make verify` is not a reliable gate for `make meshes`
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: `scripts/00_verify_access.py` / auth preflight

### Problem
`make verify` is documented as the operator preflight before the FlyWire-backed pipeline, but the script is not authoritative for the next step it is supposed to protect. It can still dump an uncaught info-service exception after client construction, and it also downgrades `fafbseg` or local-secret-sync failures to warnings while still returning success. That lets operators burn time on `make meshes` after a misleading green verify.

### Evidence
- [README.md:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L59) tells operators to run `make verify` before preprocessing.
- [scripts/00_verify_access.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L118) and [scripts/00_verify_access.py:119](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L119) call the info service outside the request error-shaping used for client creation and materialize retries.
- [scripts/00_verify_access.py:166](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L166) starts the `fafbseg`/secret-sync check, [scripts/00_verify_access.py:180](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L180) catches every exception, and [scripts/00_verify_access.py:183](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L183) still prints success text and returns `0`.
- [scripts/02_fetch_meshes.py:83](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L83) and [scripts/02_fetch_meshes.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L118) depend on the same `ensure_flywire_secret` / `fafbseg` path that verify can currently waive.

### Requested Change
Make `verify` fail by default when mesh-fetch prerequisites are not usable, and shape every subcheck into explicit operator-facing statuses. If partial verification is still desired, require an explicit opt-in flag and label the result as partial rather than printing “Access looks good.”

### Acceptance Criteria
`make verify` exits non-zero when FlyWire mesh prerequisites are broken, including missing `fafbseg`, broken secret sync, or post-client info-service failures.
The script prints one actionable failure summary per failing subsystem, including the package/env fix or network/auth next step.
The success path is only emitted when the prerequisites needed by `make meshes` have actually been validated, or when the operator explicitly asked for a partial check.

### Verification
Run `make verify CONFIG=config/local.yaml` in an environment with working CAVE access but without `fafbseg` or working secret storage; it should exit non-zero with a targeted fix message.
Run `make verify CONFIG=config/local.yaml` with an invalid datastack or forced info-service failure; it should return a shaped error, not a traceback.
Run `make verify CONFIG=config/local.yaml` in a fully provisioned environment; it should still exit `0`.

## OPS-002 - Missing Python dependencies fail as raw import tracebacks across pipeline entrypoints
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: pipeline CLI imports

### Problem
Several operator entrypoints import heavy runtime dependencies at module import time, so a partially provisioned environment dies with raw `ModuleNotFoundError` tracebacks before any CLI guidance can be shown. The repo already has a canonical recovery path in `make bootstrap`, but these failures never point operators back to it.

### Evidence
- [src/flywire_wave/selection.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L12) imports `networkx` at module load.
- [src/flywire_wave/mesh_pipeline.py:11](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L11) imports `trimesh` at module load.
- [scripts/02_fetch_meshes.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L12) and [scripts/03_build_wave_assets.py:10](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L10) import `tqdm` before any error shaping.
- [Makefile:101](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L101) already defines the intended recovery path as `make bootstrap`.
- Observed locally by running `python3 -m unittest tests.test_config_paths tests.test_manifest_validation tests.test_mesh_pipeline_fetch tests.test_simulator_execution tests.test_experiment_comparison_analysis tests.test_review_prompt_tickets tests.test_run_review_prompt_tickets tests.test_geometry_preview tests.test_operator_qa tests.test_coupling_inspection -v`: the run surfaced raw `ModuleNotFoundError` tracebacks for `networkx`, `trimesh`, and `tqdm` from pipeline/report entrypoints instead of actionable operator messages.

### Requested Change
Move these imports behind shaped dependency checks or wrap them in consistent operator-facing errors that name the missing package and point to `make bootstrap` (or the equivalent install command). Add a lightweight automated check so missing dependency behavior does not regress back to raw tracebacks.

### Acceptance Criteria
`make select`, `make meshes`, `make assets`, and report commands that depend on extra packages fail with concise messages naming the missing dependency and the bootstrap/install fix.
Those commands no longer emit a Python traceback for ordinary missing-package cases.
At least one automated test covers the shaped error path for missing runtime dependencies.

### Verification
In an environment missing `networkx`, run `make select CONFIG=config/local.yaml`; the command should fail with an actionable dependency message.
In an environment missing `trimesh` or `tqdm`, run `make meshes CONFIG=config/local.yaml` and `make assets CONFIG=config/local.yaml`; both should fail without a traceback and should point to `make bootstrap`.
Re-run the targeted unittest subset above and confirm the dependency failures are now shaped operator errors instead of import tracebacks.

## OPS-003 - `make preview` aborts on the first missing asset instead of emitting a blocked report
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/05_preview_geometry.py` / `src/flywire_wave/geometry_preview.py`

### Problem
The geometry preview command is the odd operator-facing report surface out: it hard-fails on the first missing mesh/graph artifact instead of writing a blocked summary that tells the operator which roots are incomplete. After a partial `make assets` run, that makes preview failures harder to diagnose than the repo’s other offline inspection commands.

### Evidence
- [scripts/05_preview_geometry.py:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/05_preview_geometry.py#L59) delegates straight into report generation and has no prerequisite shaping beyond “no root IDs.”
- [src/flywire_wave/geometry_preview.py:142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L142) through [src/flywire_wave/geometry_preview.py:145](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L145) require all core assets up front, and [src/flywire_wave/geometry_preview.py:797](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L797) raises `FileNotFoundError` on the first miss.
- The repo already has a blocked-report pattern elsewhere: [src/flywire_wave/operator_qa.py:404](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/operator_qa.py#L404) and [src/flywire_wave/coupling_inspection.py:493](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_inspection.py#L493) turn missing artifacts into structured blocked entries instead of crashing.
- [tests/test_operator_qa.py:125](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_operator_qa.py#L125) explicitly locks in the blocked-report behavior for operator QA, while [tests/test_geometry_preview.py:19](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_geometry_preview.py#L19) only covers the happy path.

### Requested Change
Give preview the same blocked/missing-prerequisite behavior as the other local inspection commands. At minimum, aggregate all missing prerequisite paths before exiting; preferably write a summary/report bundle that marks blocked roots and points directly to the missing artifact paths.

### Acceptance Criteria
`make preview` writes a summary artifact even when one or more requested roots are missing preview prerequisites.
The summary identifies blocked roots, missing asset keys, and concrete file paths.
The command exits without a traceback for ordinary missing-artifact cases and tells the operator whether to rerun `make meshes`, `make assets`, or both.

### Verification
Run `make assets CONFIG=config/local.yaml`, remove one required preview input such as a patch graph, then run `make preview CONFIG=config/local.yaml`.
Confirm that the command produces a structured blocked summary or report bundle naming the missing artifact path and affected root IDs.
Confirm that a fully built asset set still produces the current happy-path preview output.

## OPS-004 - `make review-tickets` leaves failed prompt jobs without a trustworthy error artifact
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/run_review_prompt_tickets.py` / `src/flywire_wave/review_prompt_tickets.py`

### Problem
The review-ticket runner advertises per-job artifacts including `stderr.log`, but the implementation merges child stderr into stdout and then writes an empty `stderr.log`. On failure, the top-level script only prints the summary path, so operators still have to dig through JSON to discover which prompt set failed and which log file actually has the diagnostics.

### Evidence
- [README.md:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L133) documents the review-run artifact layout as an operator-facing surface.
- [src/flywire_wave/review_prompt_tickets.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L16) declares `stderr.log` as a standard artifact.
- [src/flywire_wave/review_prompt_tickets.py:199](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L199) launches child jobs with `stderr=subprocess.STDOUT`, and [src/flywire_wave/review_prompt_tickets.py:219](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L219) creates an empty `stderr.log` if none exists.
- [scripts/run_review_prompt_tickets.py:176](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_review_prompt_tickets.py#L176) only prints the summary path and optional combined ticket path after the run, not the failing prompt-set log paths.
- [tests/test_review_prompt_tickets.py:74](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_review_prompt_tickets.py#L74) and [tests/test_run_review_prompt_tickets.py:29](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_run_review_prompt_tickets.py#L29) only cover fake successful jobs and dry-run; the real failure-triage path is untested.

### Requested Change
Make the failure artifacts honest and directly discoverable. Either capture real child stderr separately, or stop advertising `stderr.log` and point operators to the actual combined log. Also print a short end-of-run failure summary listing the failed prompt-set slugs and the exact artifact paths to inspect.

### Acceptance Criteria
A failed specialization or review job leaves at least one non-empty, clearly named error artifact for that prompt set.
The end-of-run console output lists failed prompt sets and the relevant `stdout.jsonl`, `stderr.log`, or `last_message.md` paths.
Automated coverage includes a failing runner path rather than only dry-run and fake-success cases.

### Verification
Run `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set error_handling_and_operability --runner <failing-stub>'`.
Confirm that the command exits non-zero, prints the failed prompt-set slug and artifact paths, and leaves a non-empty error artifact for that failed job.
Confirm that a successful run still writes the documented review artifacts under `agent_tickets/review_runs/<timestamp>/`.

## file_length_and_cohesion

# File Length And Cohesion Review Tickets

## FILECOH-001 - Split simulation manifest planning from analysis and asset/runtime resolution
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: simulation planning

### Problem
`simulation_planning.py` has become the catch-all owner for manifest validation, runtime normalization, readout-analysis planning, circuit asset discovery, and surface-wave mixed-fidelity execution planning. That makes routine changes to one planning seam pull several unrelated subsystems into the same file and review surface.

### Evidence
[simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) resolves the manifest, validates it, normalizes runtime config, resolves inputs, and calls circuit asset discovery in the same top-level path. The file then shifts into readout-analysis planning at [simulation_planning.py:743](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L743), local geometry/coupling readiness checks at [simulation_planning.py:2950](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2950), surface-wave execution plan assembly at [simulation_planning.py:3406](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3406), and mixed-fidelity/operator routing at [simulation_planning.py:3667](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3667). The test surface mirrors that spillover: [test_simulator_execution.py:56](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L56) and [test_experiment_suite_aggregation.py:37](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_aggregation.py#L37) import fixture builders from [test_simulation_planning.py:931](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L931) and [test_simulation_planning.py:1070](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L1070).

### Requested Change
Keep `resolve_manifest_simulation_plan` as the orchestration entrypoint, but move readout-analysis planning under an analysis-planning boundary, move geometry/coupling asset resolution under an asset-readiness boundary, and move surface-wave or mixed-fidelity execution-plan construction under an execution-runtime planning boundary.

### Acceptance Criteria
`simulation_planning.py` is reduced to manifest-level orchestration and shared normalization, while readout-analysis helpers, circuit asset discovery or validation, and surface-wave mixed-fidelity planning live in narrower modules with explicit imports. Shared test fixture writers are moved out of `test_simulation_planning.py` into a dedicated test utility module instead of remaining trapped in the planner test file.

### Verification
`make test`
`make validate-manifest`
`make smoke`

## FILECOH-002 - Separate showcase session source resolution, narrative authoring, validation, and packaging
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: showcase session planning

### Problem
`showcase_session_planning.py` mixes upstream artifact resolution, narrative and preset authoring, rehearsal/dashboard patch validation, and bundle packaging in one file. The current shape makes story-level edits risky because they sit beside packaging and low-level UI validation rules.

### Evidence
[showcase_session_planning.py:288](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L288) resolves suite, dashboard, analysis, and validation inputs, then immediately assembles presets, steps, script payloads, preset catalogs, and export manifests before returning a plan; packaging is in the same module at [showcase_session_planning.py:540](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L540). The file also owns long presentation-specific builders at [showcase_session_planning.py:1982](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L1982) and [showcase_session_planning.py:3341](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3341), export assembly at [showcase_session_planning.py:4019](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4019) and [showcase_session_planning.py:4128](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4128), and deep rehearsal metadata validation at [showcase_session_planning.py:4479](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4479). The tests already depend on peer-module fixture builders at [test_showcase_session_planning.py:70](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_showcase_session_planning.py#L70), which is a sign that ownership is blurred across review surfaces.

### Requested Change
Split this module along real showcase seams: source and upstream artifact resolution, narrative or preset construction, presentation-state validation, and package or export writing. The planning entrypoint should compose those pieces instead of owning all four concerns directly.

### Acceptance Criteria
A top-level showcase planner remains, but preset or step generation lives outside the packaging code path, rehearsal or dashboard state validation lives in a validation-focused module, and export-manifest or bundle writing lives in a packaging-focused module. Showcase tests no longer need to reach through multiple peer test files to materialize reusable fixtures.

### Verification
`make test`
`make smoke`

## FILECOH-003 - Move whole-brain context query execution and packaging out of the planning catch-all
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: whole-brain context planning

### Problem
`whole_brain_context_planning.py` is nominally a planner, but it also executes whole-brain queries, generates preset executions, applies downstream handoffs, builds view payload or state, and packages artifacts. That collapses planning, query execution, and local review packaging into one module.

### Evidence
[whole_brain_context_planning.py:188](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L188) resolves source context, merges artifact references, builds query inputs, and directly calls `execute_whole_brain_context_query` at [whole_brain_context_planning.py:330](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L330). The same file executes preset queries again inside the preset library builder at [whole_brain_context_planning.py:1921](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1921) and [whole_brain_context_planning.py:2018](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2018), then switches to downstream handoff mutation and catalog or view assembly around [whole_brain_context_planning.py:2450](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2450) and packages bundles at [whole_brain_context_planning.py:448](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L448). Test setup also crosses planning modules at [test_whole_brain_context_planning.py:48](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_whole_brain_context_planning.py#L48).

### Requested Change
Keep source and contract resolution in the planning module, but move query execution or preset hydration behind the `whole_brain_context_query` family and move bundle payload or state packaging behind a packaging-oriented module. Downstream handoff enrichment should sit with the query or presentation layer it belongs to, not inside the top-level planner.

### Acceptance Criteria
`resolve_whole_brain_context_session_plan` becomes an orchestrator that consumes source context and query results instead of executing queries inline. Query execution, preset execution, and package payload or state builders are owned by narrower modules whose names match those responsibilities.

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
