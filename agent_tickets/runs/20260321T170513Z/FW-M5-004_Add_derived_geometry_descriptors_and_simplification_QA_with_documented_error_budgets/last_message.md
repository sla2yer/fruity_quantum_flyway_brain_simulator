**Changed**
- Added structured geometry descriptor/QA support in [geometry_qa.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_qa.py) and wired it into [mesh_pipeline.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py). The descriptor sidecar now summarizes `raw_mesh`, `simplified_mesh`, `coarse_patches`, and optional `skeleton`; the QA sidecar now records per-check `pass`/`warn`/`fail`, applied thresholds, and a blocking/non-blocking summary.
- Updated [03_build_wave_assets.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py) to pass `meshing.qa_thresholds`, surface QA warning/failure details in the build summary, and exit non-zero only when a blocking QA check fails.
- Documented the default budgets and rationale in [geometry_descriptor_qa.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/geometry_descriptor_qa.md), linked it from [pipeline_notes.md](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/docs/pipeline_notes.md), and added example threshold config in [visual_subset.example.yaml](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/config/visual_subset.example.yaml).
- Expanded regression coverage in [test_mesh_pipeline_build.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_mesh_pipeline_build.py) and [test_config_paths.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_config_paths.py) for healthy builds, warning-only QA, and blocking-threshold failures.

**Verified**
- `make test` passed (`31` tests).
- Focused descriptor/QA tests passed:
  - `.venv/bin/python -m unittest tests.test_mesh_pipeline_build -v`
  - `.venv/bin/python -m unittest tests.test_config_paths -v`

Pre-existing unrelated worktree changes were left untouched.