Implemented the Milestone 10 sweep/audit layer around the existing surface-wave plans.

Key additions:
- New deterministic sweep and offline inspection workflow in [surface_wave_inspection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/surface_wave_inspection.py) with a CLI entrypoint in [15_surface_wave_inspection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/15_surface_wave_inspection.py).
- The workflow supports explicit parameter sets plus grid expansion, repeatable seed handling, coupled runs plus representative single-neuron pulse probes, deterministic output directories, `report.md` / `summary.json` / `runs.csv`, per-run `traces.npz`, and SVG trace panels.
- It emits compact `pass` / `warn` / `fail` checks for finite-value stability, pulse energy/peak growth, missing wavefront detection, low driven dynamic range, low spatial contrast, missing coupling events, and extreme peak-to-drive ratios.
- Repo integration and docs were added in [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile), [config.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/config.py), [surface_wave_sweep.example.yaml](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/config/surface_wave_sweep.example.yaml), and [surface_wave_inspection.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/surface_wave_inspection.md).
- Added a smoke-style regression test in [test_surface_wave_inspection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_surface_wave_inspection.py) that builds a local fixture sweep, checks deterministic report paths, and asserts expected summary/diagnostic fields.

Verified:
- `./.venv/bin/python -m unittest tests.test_surface_wave_inspection -v`
- `make test`

I could not stage or create the requested commit in this sandbox because Git writes are blocked here: `fatal: Unable to create '.git/index.lock': Read-only file system`.