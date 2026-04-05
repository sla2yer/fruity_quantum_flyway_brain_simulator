Work ticket EFFMOD-FW-003: Reuse one resolved materialized simulation plan across experiment-suite stage execution.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: efficiency_and_modularity review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repository now already computes and persists a suite-level `base_simulation_plan`, but runtime work-item execution still drives stage entrypoints from materialized manifest/config file paths instead of a reusable resolved plan object. That means a single materialized suite cell can reparse config/manifest inputs and rebuild the same simulation plan several times during one run.

The duplication is broader than the original ticket text described. The simulation stage still resolves once to discover model modes and then resolves again inside `execute_manifest_simulation()` for each mode. The analysis stage also replans the same inputs to recover both the simulation plan and the embedded readout-analysis plan. The validation stage resolves a plan up front, then its layer workflows resolve the same plan again internally. For surface-wave cells, those extra resolutions still reopen operator bundles and rerun spectral-radius estimation, so the wasted work remains materially expensive.

Requested Change:
Refine this ticket around a per-work-item execution context rather than a new planner surface. After materialized inputs are written for a suite work item, resolve that materialized simulation plan once and carry it through stage execution. Extend simulation, analysis, and validation entrypoints so they can consume a pre-resolved `simulation_plan` directly, and let analysis/validation reuse embedded derived state such as `readout_analysis_plan`, resolved arm plans, and validation-plan inputs instead of round-tripping back through file-based resolvers.

Keep the existing path-based entrypoints as thin CLI wrappers, but make suite execution use the object path end-to-end. Memoize or persist surface-wave operator stability metadata within the resolved work-item plan so repeated stage/layer execution does not recompute spectral radius for the same operator bundle.

Acceptance Criteria:
- A suite work item resolves its materialized simulation plan once and reuses it across simulation, analysis, and validation stage execution for that cell.
- Executing multiple model modes for one materialized work item does not call `resolve_manifest_simulation_plan()` again after stage execution has started.
- Analysis execution consumes `simulation_plan["readout_analysis_plan"]` directly instead of calling `resolve_manifest_readout_analysis_plan()` for the same inputs.
- Validation layer workflows can consume the already resolved stage plan/context without reparsing the same manifest/config pair.
- Surface-wave spectral-radius estimation is computed once per unique operator bundle within a resolved work-item plan, or loaded from memoized plan metadata.

Verification:
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution tests.test_experiment_comparison_analysis tests.test_simulator_execution tests.test_validation_circuit tests.test_validation_morphology tests.test_validation_numerics tests.test_validation_task tests.test_validation_planning -v`
- `make smoke`
