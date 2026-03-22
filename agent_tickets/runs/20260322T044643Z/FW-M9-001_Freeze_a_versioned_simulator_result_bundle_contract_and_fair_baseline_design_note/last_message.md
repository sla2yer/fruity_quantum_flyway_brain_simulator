**Changed**
- Added the new simulator contract module [simulator_result_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_result_contract.py). It centralizes `simulator_result_bundle.v1` path building, run-spec hashing, manifest/arm metadata normalization, deterministic serialization, fixed shared artifact inventory, and bundle discovery for baseline and later `surface_wave` runs.
- Added the decisive design note [simulator_result_bundle_design.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/simulator_result_bundle_design.md), updated [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md), and exported the module from [__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py).
- Added focused regression coverage in [test_simulator_result_contract.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_result_contract.py) for deterministic bundle paths, deterministic serialization from fixture baseline specs, and bundle discovery.

**Verified**
- `make test` passed: 92 tests.
- `python3 -m unittest tests.test_simulator_result_contract -v` passed.

**Blocker**
- I could not stage or create the requested commit in this environment because Git metadata is read-only here. The exact failure was:
  `fatal: Unable to create '/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/.git/index.lock': Read-only file system`
- I left the unrelated untracked `agent_tickets/runs/20260322T044643Z/` directory untouched. If you want to finish the commit locally, run:
```bash
git add docs/pipeline_notes.md docs/simulator_result_bundle_design.md src/flywire_wave/__init__.py src/flywire_wave/simulator_result_contract.py tests/test_simulator_result_contract.py
git commit -m "FW-M9-001 freeze simulator result bundle contract"
```