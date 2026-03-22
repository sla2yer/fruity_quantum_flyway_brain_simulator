**Changed**
- Added the canonical baseline-family layer in [baseline_families.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/baseline_families.py#L1). It documents the library-owned `P0`/`P1` equations, validates normalized model specs, rejects ambiguous cases like nonzero `resting_potential` with `initial_state=all_zero`, and exposes explicit state-variable plus shared-readout metadata.
- The main API is [baseline_families.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/baseline_families.py#L307). `resolve_baseline_neuron_family` and `resolve_baseline_neuron_family_from_arm_plan` turn normalized planning specs into executable families.
- The executable `P0` and `P1` engines are in [baseline_families.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/baseline_families.py#L394). `P0` is the passive leaky membrane baseline, `P1` adds explicit synaptic-current integration, and both use the same membrane-state shared readout semantics.
- Added focused regression coverage in [test_baseline_families.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_baseline_families.py#L38). The tests instantiate fixture `P0`/`P1` runs through the real simulator runtime and check deterministic passive response, filtered impulse response, shared readout extraction, and clear failures for invalid parameterizations.

**Verified**
- `./.venv/bin/python -m unittest tests.test_baseline_families -v`
- `make test` passed: 99 tests

**Commit Blocker**
- I attempted to stage the ticket files with `git add src/flywire_wave/baseline_families.py tests/test_baseline_families.py`, but this sandbox cannot write under `.git`.
- Exact failure: `fatal: Unable to create '/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/.git/index.lock': Read-only file system`
- If you want to finish that step locally, run:
```bash
git add src/flywire_wave/baseline_families.py tests/test_baseline_families.py
git commit -m "FW-M9-004 implement canonical P0 and P1 baseline families"
```