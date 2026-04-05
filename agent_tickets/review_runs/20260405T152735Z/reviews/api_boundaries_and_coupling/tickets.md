# API Boundaries And Coupling Review Tickets

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
