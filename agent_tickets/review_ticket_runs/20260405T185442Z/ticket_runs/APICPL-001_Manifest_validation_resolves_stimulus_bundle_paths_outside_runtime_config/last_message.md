Implemented APICPL-001 end to end.

**Changed**
- Added a shared manifest-input root resolver in [manifests.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/manifests.py) so manifest-facing code can resolve processed bundle roots from either `config_path` or explicit overrides.
- Routed manifest validation, stimulus bundle resolution, retinal bundle resolution, and simulation planning through that shared resolver in [manifests.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/manifests.py), [stimulus_bundle.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_bundle.py), [retinal_workflow.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/retinal_workflow.py), and [simulation_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py).
- Updated [04_validate_manifest.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/04_validate_manifest.py) to accept `--config` and `--processed-stimulus-dir`, and updated [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile) so `make validate-manifest` now uses `$(CONFIG)`.
- Added a regression test in [test_manifest_validation.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_manifest_validation.py) that records a manifest-driven stimulus bundle under a nondefault `processed_stimulus_dir` and verifies validation and `resolve_manifest_simulation_plan` resolve the same bundle reference and metadata path.

**Verified**
- `make validate-manifest`
- `python3 -m unittest tests.test_manifest_validation -v`
- `python3 -m unittest tests.test_simulation_planning -v`
- `python3 -m unittest tests.test_stimulus_bundle_workflow -v`
- `python3 -m unittest tests.test_retinal_bundle_workflow -v`

All passed.