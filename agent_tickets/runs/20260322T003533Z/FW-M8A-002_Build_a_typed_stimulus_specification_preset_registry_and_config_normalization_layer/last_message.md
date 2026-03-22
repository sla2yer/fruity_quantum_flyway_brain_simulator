**Changed**
- Added a typed stimulus registry and normalization API in [stimulus_registry.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_registry.py). It now reserves canonical Milestone 8A families, exposes discoverable presets/aliases, validates family-specific overrides, applies explicit timing/spatial/luminance/determinism defaults, and resolves the Milestone 1 `moving_edge` / `simple_moving_edge` pair to canonical `translated_edge` / `simple_translated_edge`.
- Wired config and manifest entrypoints to use the same resolver in [config.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/config.py) and [manifests.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/manifests.py), and exported the new module from [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py).
- Added fixture-driven regression coverage in [test_stimulus_registry.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_stimulus_registry.py) with fixture inputs in [stimulus_resolution_cases.yaml](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/fixtures/stimulus_resolution_cases.yaml) and [stimulus_config_fixture.yaml](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/fixtures/stimulus_config_fixture.yaml).

**Verified**
- `./.venv/bin/python -m unittest tests.test_stimulus_registry -v`
- `make test`
- `make validate-manifest`

**Blocker**
- I could not stage or create the requested commit because this environment cannot write to `.git`: `git add` failed with `Unable to create '.../.git/index.lock': Read-only file system`.