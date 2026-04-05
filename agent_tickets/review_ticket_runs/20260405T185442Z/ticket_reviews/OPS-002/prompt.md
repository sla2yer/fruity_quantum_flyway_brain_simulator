Review work ticket OPS-002: Missing Python dependencies fail as raw import tracebacks across pipeline entrypoints.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo

This is a ticket review pass only. Do not implement code.
Earlier backlog tickets may already have changed the surrounding code.
Check whether this ticket is still accurate for the repository's current state and update it if needed.

Rules:
- Keep the same ticket ID.
- Return exactly one ticket in the same markdown ticket format.
- Update the title, priority, area, and sections if the ticket needs refinement.
- If the ticket no longer needs implementation, set `- Status: closed` and explain why.
- Do not create new tickets or broaden this ticket into a larger backlog item.
- Return only the updated single-ticket markdown and do not use code fences.

Existing Ticket:
## OPS-002 - Missing Python dependencies fail as raw import tracebacks across pipeline entrypoints
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: pipeline CLI imports

### Problem
Several operator entrypoints import heavy runtime dependencies at module import time, so a partially provisioned environment dies with raw `ModuleNotFoundError` tracebacks before any CLI guidance can be shown. The repo already has a canonical recovery path in `make bootstrap`, but these failures never point operators back to it.

### Evidence
- [src/flywire_wave/selection.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L12) imports `networkx` at module load.
- [src/flywire_wave/mesh_pipeline.py:11](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/mesh_pipeline.py#L11) imports `trimesh` at module load.
- [scripts/02_fetch_meshes.py:12](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L12) and [scripts/03_build_wave_assets.py:10](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L10) import `tqdm` before any error shaping.
- [Makefile:101](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L101) already defines the intended recovery path as `make bootstrap`.
- Observed locally by running `python3 -m unittest tests.test_config_paths tests.test_manifest_validation tests.test_mesh_pipeline_fetch tests.test_simulator_execution tests.test_experiment_comparison_analysis tests.test_review_prompt_tickets tests.test_run_review_prompt_tickets tests.test_geometry_preview tests.test_operator_qa tests.test_coupling_inspection -v`: the run surfaced raw `ModuleNotFoundError` tracebacks for `networkx`, `trimesh`, and `tqdm` from pipeline/report entrypoints instead of actionable operator messages.

### Requested Change
Move these imports behind shaped dependency checks or wrap them in consistent operator-facing errors that name the missing package and point to `make bootstrap` (or the equivalent install command). Add a lightweight automated check so missing dependency behavior does not regress back to raw tracebacks.

### Acceptance Criteria
`make select`, `make meshes`, `make assets`, and report commands that depend on extra packages fail with concise messages naming the missing dependency and the bootstrap/install fix.
Those commands no longer emit a Python traceback for ordinary missing-package cases.
At least one automated test covers the shaped error path for missing runtime dependencies.

### Verification
In an environment missing `networkx`, run `make select CONFIG=config/local.yaml`; the command should fail with an actionable dependency message.
In an environment missing `trimesh` or `tqdm`, run `make meshes CONFIG=config/local.yaml` and `make assets CONFIG=config/local.yaml`; both should fail without a traceback and should point to `make bootstrap`.
Re-run the targeted unittest subset above and confirm the dependency failures are now shaped operator errors instead of import tracebacks.
