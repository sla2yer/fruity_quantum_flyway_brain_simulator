Implemented FW-M8B-001 end to end in the repo code/docs, with one caveat: the requested git staging/commit step is blocked by the sandbox because `.git` is mounted read-only.

**Changed**
- Added a new library-owned retinal contract module at [retinal_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/retinal_contract.py#L32) that centralizes:
  - versioned retinal bundle paths
  - upstream source references
  - deterministic retinal-spec hashing
  - bundle metadata/reference serialization
  - bundle path discovery/resolution
  - canonical eye ordering, frame layout, timing, coordinate, signal, and sampling-kernel metadata
- Added the decisive Milestone 8B design note at [retinal_bundle_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/retinal_bundle_design.md#L1), choosing `direct_per_ommatidium_irradiance` over raster and feature-map intermediates, and freezing the world/body/head/eye frame conventions plus downstream invariants.
- Updated [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L231) so the retinal contract sits alongside the existing contract sections.
- Added regression coverage in [test_retinal_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_retinal_contract.py#L32) and extended config-path coverage in [test_config_paths.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_config_paths.py#L19). Also exposed the new module in [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py#L3) and added `processed_retinal_dir` to [config.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/config.py#L13).

**Verified**
- `python -m unittest tests.test_retinal_contract -v`
- `python -m unittest tests.test_config_paths.ConfigPathResolutionTest -v`
- `make test`  
  Result: 77 tests passed.

**Blocked**
- I could not stage or commit because git writes are disallowed here. `git add ...` failed with:
  - `fatal: Unable to create '.../.git/index.lock': Read-only file system`
- A direct probe also failed:
  - `touch .git/codex_write_probe: Read-only file system`

When `.git` is writable, the intended commit step is:

```bash
git add docs/pipeline_notes.md docs/retinal_bundle_design.md \
  src/flywire_wave/__init__.py src/flywire_wave/config.py src/flywire_wave/retinal_contract.py \
  tests/test_config_paths.py tests/test_retinal_contract.py
git commit -m "FW-M8B-001 Freeze retinal input bundle contract"
```