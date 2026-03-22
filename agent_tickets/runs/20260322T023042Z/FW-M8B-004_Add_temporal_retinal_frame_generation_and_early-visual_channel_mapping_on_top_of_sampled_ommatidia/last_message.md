**Changes**
- Added [retinal_bundle.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/retinal_bundle.py) with the canonical temporal handoff API: `project_and_record_retinal_bundle`, `record_retinal_bundle`, and `load_recorded_retinal_bundle`. It writes deterministic retinal archives with both raw `time x eye x ommatidium` frames and simulator-facing `time x eye x unit x channel` early-visual units.
- Extended [retinal_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/retinal_contract.py) so every retinal bundle now carries an explicit `simulator_input` block: default mapping family `identity_per_ommatidium`, one `irradiance` channel, explicit aggregation/normalization/adaptation/polarity semantics, and deterministic source-reference hashing from sampled source descriptors.
- Updated [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py), [retinal_bundle_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/retinal_bundle_design.md), and [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md), and added regression coverage in [test_retinal_bundle.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_retinal_bundle.py) plus updated contract expectations in [test_retinal_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_retinal_contract.py).

**Verified**
- `make test` passed: 86 tests.
- `./.venv/bin/python -m unittest tests.test_retinal_bundle -v` passed.

**Note**
- I could not complete the requested `git add` / commit step here because git writes are blocked in this sandbox: `fatal: Unable to create '.git/index.lock': Read-only file system`.