**Changes**

Refactored [simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py) into manifest-level orchestration plus thin compatibility wrappers. The extracted logic now lives in:
- [simulation_analysis_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_analysis_planning.py) for readout-analysis planning
- [simulation_asset_resolution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_asset_resolution.py) for geometry/coupling readiness and asset resolution
- [simulation_runtime_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_runtime_planning.py) for surface-wave execution and mixed-fidelity planning

`resolve_manifest_simulation_plan` remains the main orchestration entrypoint, and `resolve_manifest_readout_analysis_plan` plus `resolve_manifest_mixed_fidelity_plan` still exist as thin public wrappers so callers do not need import changes.

Moved shared test fixture writers out of [test_simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py) into [simulation_planning_test_support.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/simulation_planning_test_support.py), then updated the dependent test modules to import from that support module instead of another test file.

**Verification**

- `make validate-manifest`: passed
- `make test`: failed due pre-existing relative-import errors in [test_cli_startup.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_cli_startup.py) and [test_verify_access.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py), unrelated to this refactor
- `make smoke`: failed for the same reason because it runs the test suite

The simulation-planning and downstream planning/validation tests exercised by the full run passed after the refactor.