**Changed**
Implemented the manifest-driven planning layer in [simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py). The canonical API is `resolve_manifest_simulation_plan`, with `discover_simulation_run_plans` and `resolve_simulation_arm_plan` for deterministic per-arm/per-seed discovery.

The planner now:
- validates manifest + local config + selected-root/coupling prerequisites
- normalizes typed baseline runtime config for `P0` and `P1`
- preserves stable arm ordering from manifest declaration order
- resolves selected roots, input bundle references, coupling sources, timing, seed handling, and deterministic simulator-result bundle locations/run hashes
- reuses the same manifest path for both `baseline` and `surface_wave` arms, with baseline-specific config only in the model sub-section

I also added `processed_simulator_results_dir` to [config.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/config.py), exported the module from [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py), and added focused regression coverage in [test_simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py). The already-present Milestone 9 result-contract foundation files in the worktree were left intact and used by this planner.

**Verified**
- `make test` passed: 94 tests
- `.venv/bin/python -m unittest tests.test_simulation_planning` passed

**Blocked**
I could not stage or create the requested commit because this environment blocks writes under `.git`: `Unable to create .git/index.lock: Read-only file system`. The code changes are in the worktree but remain uncommitted.