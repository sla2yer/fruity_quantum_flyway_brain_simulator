## OPS-003 - `make preview` still aborts on the first missing required asset and writes no blocked report
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/05_preview_geometry.py` / `src/flywire_wave/geometry_preview.py` / `tests/test_geometry_preview.py`

### Problem
`make preview` is still the outlier among the local inspection/report commands. If any requested root is missing a required preview input, the CLI raises a traceback before it writes the deterministic preview bundle, so operators get neither a blocked summary nor an aggregate view of which roots are incomplete after a partial `make assets` run.

### Evidence
- [Makefile:123](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L123) and [Makefile:124](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L124) wire `make preview` directly to the preview CLI with no wrapper-level missing-asset handling.
- [scripts/05_preview_geometry.py:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/05_preview_geometry.py#L59) calls `generate_geometry_preview_report(...)` directly and only prints a summary after that returns.
- [src/flywire_wave/geometry_preview.py:64](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L64) builds all per-root entries before output writing; [src/flywire_wave/geometry_preview.py:100](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L100) and [src/flywire_wave/geometry_preview.py:101](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L101) only write `index.html` and `summary.json` after all entries succeed.
- [src/flywire_wave/geometry_preview.py:142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L142), [src/flywire_wave/geometry_preview.py:143](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L143), [src/flywire_wave/geometry_preview.py:144](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L144), and [src/flywire_wave/geometry_preview.py:145](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L145) hard-require the raw mesh, simplified mesh, surface graph, and patch graph; [src/flywire_wave/geometry_preview.py:799](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L799) raises `FileNotFoundError` on the first missing path.
- [tests/test_geometry_preview.py:20](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_geometry_preview.py#L20) covers only the deterministic happy path. There is no missing-prerequisite regression test for preview.
- Current repro on 2026-04-05: after generating assets for root `101` and deleting `101_patch_graph.npz`, running `scripts/05_preview_geometry.py --config <tmp>/config.yaml --root-id 101` exited with status `1`, printed a traceback ending in `FileNotFoundError: Missing preview input asset: .../101_patch_graph.npz`, and wrote neither `summary.json` nor `index.html`.
- The repo already has a blocked-report pattern for ordinary missing prerequisites in [src/flywire_wave/operator_qa.py:404](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/operator_qa.py#L404), [src/flywire_wave/coupling_inspection.py:493](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_inspection.py#L493), and [tests/test_operator_qa.py:125](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_operator_qa.py#L125).

### Requested Change
Align geometry preview with the repo’s existing blocked-report behavior for ordinary missing local prerequisites. The preview command should collect missing required preview inputs per root, write the deterministic output bundle anyway, and return a structured blocked summary instead of propagating `FileNotFoundError` to stderr.

### Acceptance Criteria
`make preview CONFIG=...` writes `summary.json` and `root_ids.txt` even when one or more requested roots are missing required preview inputs.
Ordinary missing-prerequisite cases do not emit a Python traceback; the command returns a structured blocked result instead of crashing.
The summary identifies blocked roots, missing asset keys, and resolved file paths, and it aggregates all missing prerequisites across the requested root set rather than stopping at the first miss.
The output tells the operator whether the missing prerequisite implies rerunning `make meshes`, `make assets`, or both.
A fully built root still produces the current happy-path preview output, and `tests/test_geometry_preview.py` gains a missing-prerequisite regression case.

### Verification
Create a local preview bundle with `make assets CONFIG=config/local.yaml`, remove one required preview input such as `<root_id>_patch_graph.npz`, then run `make preview CONFIG=config/local.yaml`.
Confirm that the command writes the deterministic preview output directory and a structured blocked summary naming the missing asset path and affected root IDs, without a traceback.
Repeat with multiple incomplete roots or multiple missing required assets to confirm the report aggregates all blocked prerequisites instead of aborting on the first miss.
Confirm that a fully built asset set still produces the existing happy-path preview HTML and summary.