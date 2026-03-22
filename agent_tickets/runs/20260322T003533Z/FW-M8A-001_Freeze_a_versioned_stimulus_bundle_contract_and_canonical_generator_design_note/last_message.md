**Changed**
- Added [stimulus_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/stimulus_contract.py#L16) with the first-class `stimulus_bundle.v1` contract: canonical bundle/alias path builders, deterministic parameter hashing, strict metadata parsing, metadata writing, and canonical bundle discovery/alias resolution.
- Added focused regression coverage in [test_stimulus_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_stimulus_contract.py#L34) for stable path generation, deterministic serialization, and bundle discovery through a compatibility alias.
- Added the decisive design note [stimulus_bundle_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/stimulus_bundle_design.md#L1), choosing the hybrid descriptor-plus-cache model and freezing the spatial, temporal, luminance, seeding, hashing, alias, and replay invariants.
- Updated [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md#L178) so the Milestone 8A stimulus contract sits next to the existing handoff contracts.

**Verified**
- `python3 -m unittest tests.test_stimulus_contract -v`
- `make test`  
  Result: 58 tests passed.

**Git**
- I could not complete the requested staging/commit step in this environment because writes under `.git` are blocked by the sandbox. `git add` fails with: `fatal: Unable to create '/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/.git/index.lock': Read-only file system`
- The code and docs changes are present in the working tree, but no commit was created.