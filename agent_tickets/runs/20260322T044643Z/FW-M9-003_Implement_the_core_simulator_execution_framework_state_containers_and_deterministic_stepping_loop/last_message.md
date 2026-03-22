**Changed**
- Added the core simulator runtime in [src/flywire_wave/simulator_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_runtime.py#L43): typed timebase/determinism/readout/run-blueprint objects, explicit per-neuron state buffers, protocol-based engine/drive/recurrent interfaces, deterministic fixed-step `SimulatorRun`, lifecycle hooks, immutable snapshots, and shared readout-trace capture. The plan bridge lives at [src/flywire_wave/simulator_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_runtime.py#L799), and the stepping loop is at [src/flywire_wave/simulator_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_runtime.py#L485).
- Exported the new runtime module from [src/flywire_wave/__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py#L3).
- Added focused regression coverage in [tests/test_simulator_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_runtime.py#L37) for deterministic fixture-circuit stepping, initialize/step/finalize boundaries, hook context, and snapshot extraction.

**Verified**
- `./.venv/bin/python -m unittest tests.test_simulator_runtime -v`
- `make test` passed: 96 tests total

**Commit**
- I could not stage or create the requested commit in this sandbox because Git metadata is read-only here. `git add` failed with: `Unable to create '.git/index.lock': Read-only file system`.