Work ticket APICPL-002: Planner bundle metadata resolution still falls back to filesystem globbing instead of contract-owned lookup.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: api_boundaries_and_coupling review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repository now has more contract support than this ticket originally assumed: simulator result bundles have a direct metadata-path resolver, experiment-analysis and validation contracts have deterministic bundle path builders, and validation planning already uses the identity-based analysis lookup pattern. The remaining issue is that experiment comparison and dashboard planning still bypass those contract surfaces and rescan on-disk directories for `*/...bundle.json`. That keeps discovery policy coupled to folder layout and allows unrelated or stale files under an experiment root to affect planner behavior.

Requested Change:
Replace the remaining raw directory scans with contract-owned metadata lookup:
- In `discover_experiment_bundle_set()`, resolve expected simulator bundle metadata from the canonical per-run `result_bundle` identity or `resolve_simulator_result_bundle_metadata_path()` instead of globbing arm bundle directories.
- Add shared experiment-analysis and validation bundle metadata lookup helpers that accept plan identity when available and bundle-reference inputs when only upstream bundle ids are available, then route dashboard session planning through those helpers instead of direct `glob("*/...bundle.json")` calls.
- Keep ambiguity handling inside the shared resolver layer so planner modules stop owning filename and folder policy.

Acceptance Criteria:
High-level planners no longer call `glob("*/simulator_result_bundle.json")`, `glob("*/experiment_analysis_bundle.json")`, or `glob("*/validation_bundle.json")` to resolve bundle metadata. Experiment comparison and dashboard planning resolve bundle metadata through contract-owned identity/path helpers, and stray or stale directories under `bundles/`, `analysis/`, or `validation/` do not change which bundle is selected.

Verification:
`python3 -m unittest tests.test_experiment_comparison_analysis -v`; `python3 -m unittest tests.test_validation_planning -v`; `python3 -m unittest tests.test_dashboard_session_planning -v` after installing `trimesh` (that suite currently fails to import in this environment with `ModuleNotFoundError: trimesh`).
