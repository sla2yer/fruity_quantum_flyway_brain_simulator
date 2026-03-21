**Changes**
- Added a shared registry-membership check in [src/flywire_wave/registry.py:196](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/registry.py) that raises a `RuntimeError` with the missing-count and a sample of missing IDs.
- Switched both [scripts/02_fetch_meshes.py:53](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py) and [scripts/03_build_wave_assets.py:51](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py) to use that shared validator, so the asset builder now fails before processing meshes if selected IDs are absent from the neuron registry.
- Added regression coverage in [tests/test_config_paths.py:93](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_config_paths.py) that reproduces the old silent-success case by providing a raw mesh for an unregistered root ID and asserting `03_build_wave_assets.py` now fails with the registry error. Added direct helper tests in [tests/test_registry.py:260](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_registry.py).

**Verified**
- `.venv/bin/python -m unittest tests.test_registry -v`
- `.venv/bin/python -m unittest tests.test_config_paths -v`
- `make test` passed: 19 tests, including the existing happy-path pipeline integration and the new failure regression.