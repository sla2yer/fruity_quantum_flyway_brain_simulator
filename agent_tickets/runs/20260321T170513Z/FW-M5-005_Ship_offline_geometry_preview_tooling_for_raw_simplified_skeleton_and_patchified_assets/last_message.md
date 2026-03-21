**Changed**
- Added an offline preview generator in [geometry_preview.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L51) and a CLI in [05_preview_geometry.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/05_preview_geometry.py#L18). It reads built local bundles only and writes a deterministic report directory at `config.paths.geometry_preview_dir/root-ids-<sorted-root-ids>/` with `index.html`, `summary.json`, and `root_ids.txt`.
- The report renders raw mesh, simplified mesh, skeleton, surface graph, and patch graph views together, plus bundle stats, artifact paths, and QA highlights. The default output root is now configured in [config.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/config.py#L11).
- Documented the workflow and reviewer checklist in [geometry_preview.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/geometry_preview.md#L13) and linked the new step from [README.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L314). Added `make preview` in [Makefile](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L8).
- Added a smoke-style automated test in [test_geometry_preview.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_geometry_preview.py#L19) that builds fixture assets, runs the preview script, and checks deterministic output generation.

**Verified**
- `make test`  
  Result: `32` tests passed.
- `.venv/bin/python -m unittest tests.test_geometry_preview -v`  
  Result: smoke preview test passed, including actual HTML report generation from stub assets.