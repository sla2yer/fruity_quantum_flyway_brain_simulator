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
