## OPS-002 - Core CLI entrypoints still raise raw startup `ModuleNotFoundError` instead of bootstrap guidance
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: CLI startup dependency handling

### Problem
The repo now has partial dependency shaping inside `verify`, but the core preflight and pipeline scripts still import declared packages before any operator-facing error handling runs. When the active interpreter has not been bootstrapped into the repo environment, operators still get raw `ModuleNotFoundError` tracebacks instead of a concise message naming the missing package and pointing back to `make bootstrap`. Because the Makefile prefers `.venv/bin/python` when it exists, this is now mainly a first-run or bypassed-interpreter failure mode, but it still affects the documented recovery path.

### Evidence
- [Makefile:1](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L1) prefers `.venv/bin/python` when available, and [Makefile:103](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L103), [Makefile:108](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L108), [Makefile:114](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L114), [Makefile:117](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L117), and [Makefile:120](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L120) still dispatch directly to the vulnerable entrypoints.
- [scripts/00_verify_access.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L12) imports `dotenv` at module load even though the same script later defines `_fail_missing_dependency`, so missing `python-dotenv` bypasses the shaped error path.
- [scripts/01_select_subset.py:14](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/01_select_subset.py#L14) imports [src/flywire_wave/selection.py:14](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L14), which imports `networkx` at module load.
- [scripts/02_fetch_meshes.py:11](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L11), [scripts/02_fetch_meshes.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L12), and [scripts/02_fetch_meshes.py:32](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L32) import `dotenv`, `tqdm`, and [src/flywire_wave/mesh_pipeline.py:11](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L11) before any CLI guidance can run.
- [scripts/03_build_wave_assets.py:10](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L10) and [scripts/03_build_wave_assets.py:31](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L31) make `tqdm` and `trimesh` startup dependencies before any shaped failure path.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/00_verify_access.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'dotenv'`.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/01_select_subset.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'networkx'`.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/02_fetch_meshes.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'dotenv'`.
- Observed locally on 2026-04-05 with the repo's unbootstrapped `python3`: `python3 scripts/03_build_wave_assets.py --config config/local.yaml` exits with raw `ModuleNotFoundError: No module named 'tqdm'`.
- [tests/test_verify_access.py:15](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_verify_access.py#L15) covers shaped failures after `verify` is already importable, but there is no automated coverage for the startup missing-import path on `verify`, `select`, `meshes`, or `assets`.

### Requested Change
Add a shared startup dependency guard for the core operator entrypoints so missing declared packages are caught before module-level imports explode. At minimum, `verify`, `select`, `meshes`, and `assets` should fail with one concise operator-facing message that names the missing package and points to `make bootstrap`, regardless of whether the missing dependency is `python-dotenv`, `networkx`, `tqdm`, or `trimesh`.

### Acceptance Criteria
`make verify`, `make select`, `make meshes`, and `make assets` fail with concise operator messages when the active interpreter is missing required Python packages.

Those ordinary missing-package cases exit nonzero without emitting a Python traceback.

The shaped message names the missing package and points operators to `make bootstrap` or the equivalent install command.

At least one automated test covers the startup missing-import path for `verify`, and at least one automated test covers the same behavior for a pipeline command such as `select`, `meshes`, or `assets`.

### Verification
In an interpreter without `python-dotenv`, run `PYTHON=python3 make verify CONFIG=config/local.yaml` or `python3 scripts/00_verify_access.py --config config/local.yaml`; the command should fail without a traceback and should point to `make bootstrap`.

In an interpreter without `networkx`, run `PYTHON=python3 make select CONFIG=config/local.yaml`; the command should fail with an actionable dependency message instead of a raw import traceback.

In an interpreter without `python-dotenv`, `tqdm`, or `trimesh`, run `PYTHON=python3 make meshes CONFIG=config/local.yaml` and `PYTHON=python3 make assets CONFIG=config/local.yaml`; both commands should fail without a traceback and should point to `make bootstrap`.

Re-run `./.venv/bin/python -m unittest tests.test_verify_access -v` together with the new missing-dependency startup tests and confirm the shaped error path is covered.
