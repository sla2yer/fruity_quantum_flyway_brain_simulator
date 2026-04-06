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
