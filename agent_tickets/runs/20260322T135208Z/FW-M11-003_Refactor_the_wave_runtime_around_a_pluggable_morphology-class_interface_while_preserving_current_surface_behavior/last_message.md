Implemented the Milestone 11 runtime refactor around a pluggable morphology-class adapter.

Key changes:
- Added a library-owned runtime interface and surface adapter in [src/flywire_wave/hybrid_morphology_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/hybrid_morphology_runtime.py). It covers initialization, source injection, stepping, state export, readout export, and coupling-facing projection, with shared runtime metadata describing those surfaces.
- Switched `surface_wave` manifest execution to use that interface in [src/flywire_wave/simulator_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py) instead of wiring the surface circuit directly. Pure-surface arms still run through the same public CLI and write the same result-bundle artifacts, with added `morphology_runtime` metadata in wave summary/provenance.
- Exported the new module in [src/flywire_wave/__init__.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/__init__.py).
- Added regression coverage in [tests/test_surface_wave_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_surface_wave_execution.py), [tests/test_hybrid_morphology_runtime.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_hybrid_morphology_runtime.py), and [tests/test_simulator_execution.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py).

Verified:
- `make test` passed: 133 tests, 0 failures.
- Focused regressions passed:
```bash
.venv/bin/python -m unittest \
  tests.test_surface_wave_execution.SurfaceWaveExecutionTest.test_morphology_runtime_adapter_preserves_surface_fixture_behavior \
  tests.test_hybrid_morphology_runtime.HybridMorphologyRuntimeTest.test_runtime_interface_hosts_lightweight_stub_class -v
```