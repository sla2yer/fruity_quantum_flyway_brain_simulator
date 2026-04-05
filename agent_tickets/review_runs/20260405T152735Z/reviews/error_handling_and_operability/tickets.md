# Error Handling And Operability Review Tickets

## OPS-001 - `make verify` is not a reliable gate for `make meshes`
- Status: open
- Priority: high
- Source: error_handling_and_operability review
- Area: `scripts/00_verify_access.py` / auth preflight

### Problem
`make verify` is documented as the operator preflight before the FlyWire-backed pipeline, but the script is not authoritative for the next step it is supposed to protect. It can still dump an uncaught info-service exception after client construction, and it also downgrades `fafbseg` or local-secret-sync failures to warnings while still returning success. That lets operators burn time on `make meshes` after a misleading green verify.

### Evidence
- [README.md:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L59) tells operators to run `make verify` before preprocessing.
- [scripts/00_verify_access.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L118) and [scripts/00_verify_access.py:119](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L119) call the info service outside the request error-shaping used for client creation and materialize retries.
- [scripts/00_verify_access.py:166](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L166) starts the `fafbseg`/secret-sync check, [scripts/00_verify_access.py:180](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L180) catches every exception, and [scripts/00_verify_access.py:183](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/00_verify_access.py#L183) still prints success text and returns `0`.
- [scripts/02_fetch_meshes.py:83](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L83) and [scripts/02_fetch_meshes.py:118](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L118) depend on the same `ensure_flywire_secret` / `fafbseg` path that verify can currently waive.

### Requested Change
Make `verify` fail by default when mesh-fetch prerequisites are not usable, and shape every subcheck into explicit operator-facing statuses. If partial verification is still desired, require an explicit opt-in flag and label the result as partial rather than printing “Access looks good.”

### Acceptance Criteria
`make verify` exits non-zero when FlyWire mesh prerequisites are broken, including missing `fafbseg`, broken secret sync, or post-client info-service failures.
The script prints one actionable failure summary per failing subsystem, including the package/env fix or network/auth next step.
The success path is only emitted when the prerequisites needed by `make meshes` have actually been validated, or when the operator explicitly asked for a partial check.

### Verification
Run `make verify CONFIG=config/local.yaml` in an environment with working CAVE access but without `fafbseg` or working secret storage; it should exit non-zero with a targeted fix message.
Run `make verify CONFIG=config/local.yaml` with an invalid datastack or forced info-service failure; it should return a shaped error, not a traceback.
Run `make verify CONFIG=config/local.yaml` in a fully provisioned environment; it should still exit `0`.

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

## OPS-003 - `make preview` aborts on the first missing asset instead of emitting a blocked report
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/05_preview_geometry.py` / `src/flywire_wave/geometry_preview.py`

### Problem
The geometry preview command is the odd operator-facing report surface out: it hard-fails on the first missing mesh/graph artifact instead of writing a blocked summary that tells the operator which roots are incomplete. After a partial `make assets` run, that makes preview failures harder to diagnose than the repo’s other offline inspection commands.

### Evidence
- [scripts/05_preview_geometry.py:59](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/05_preview_geometry.py#L59) delegates straight into report generation and has no prerequisite shaping beyond “no root IDs.”
- [src/flywire_wave/geometry_preview.py:142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L142) through [src/flywire_wave/geometry_preview.py:145](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L145) require all core assets up front, and [src/flywire_wave/geometry_preview.py:797](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/geometry_preview.py#L797) raises `FileNotFoundError` on the first miss.
- The repo already has a blocked-report pattern elsewhere: [src/flywire_wave/operator_qa.py:404](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/operator_qa.py#L404) and [src/flywire_wave/coupling_inspection.py:493](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/coupling_inspection.py#L493) turn missing artifacts into structured blocked entries instead of crashing.
- [tests/test_operator_qa.py:125](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_operator_qa.py#L125) explicitly locks in the blocked-report behavior for operator QA, while [tests/test_geometry_preview.py:19](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_geometry_preview.py#L19) only covers the happy path.

### Requested Change
Give preview the same blocked/missing-prerequisite behavior as the other local inspection commands. At minimum, aggregate all missing prerequisite paths before exiting; preferably write a summary/report bundle that marks blocked roots and points directly to the missing artifact paths.

### Acceptance Criteria
`make preview` writes a summary artifact even when one or more requested roots are missing preview prerequisites.
The summary identifies blocked roots, missing asset keys, and concrete file paths.
The command exits without a traceback for ordinary missing-artifact cases and tells the operator whether to rerun `make meshes`, `make assets`, or both.

### Verification
Run `make assets CONFIG=config/local.yaml`, remove one required preview input such as a patch graph, then run `make preview CONFIG=config/local.yaml`.
Confirm that the command produces a structured blocked summary or report bundle naming the missing artifact path and affected root IDs.
Confirm that a fully built asset set still produces the current happy-path preview output.

## OPS-004 - `make review-tickets` leaves failed prompt jobs without a trustworthy error artifact
- Status: open
- Priority: medium
- Source: error_handling_and_operability review
- Area: `scripts/run_review_prompt_tickets.py` / `src/flywire_wave/review_prompt_tickets.py`

### Problem
The review-ticket runner advertises per-job artifacts including `stderr.log`, but the implementation merges child stderr into stdout and then writes an empty `stderr.log`. On failure, the top-level script only prints the summary path, so operators still have to dig through JSON to discover which prompt set failed and which log file actually has the diagnostics.

### Evidence
- [README.md:133](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/README.md#L133) documents the review-run artifact layout as an operator-facing surface.
- [src/flywire_wave/review_prompt_tickets.py:16](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L16) declares `stderr.log` as a standard artifact.
- [src/flywire_wave/review_prompt_tickets.py:199](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L199) launches child jobs with `stderr=subprocess.STDOUT`, and [src/flywire_wave/review_prompt_tickets.py:219](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/review_prompt_tickets.py#L219) creates an empty `stderr.log` if none exists.
- [scripts/run_review_prompt_tickets.py:176](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_review_prompt_tickets.py#L176) only prints the summary path and optional combined ticket path after the run, not the failing prompt-set log paths.
- [tests/test_review_prompt_tickets.py:74](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_review_prompt_tickets.py#L74) and [tests/test_run_review_prompt_tickets.py:29](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_run_review_prompt_tickets.py#L29) only cover fake successful jobs and dry-run; the real failure-triage path is untested.

### Requested Change
Make the failure artifacts honest and directly discoverable. Either capture real child stderr separately, or stop advertising `stderr.log` and point operators to the actual combined log. Also print a short end-of-run failure summary listing the failed prompt-set slugs and the exact artifact paths to inspect.

### Acceptance Criteria
A failed specialization or review job leaves at least one non-empty, clearly named error artifact for that prompt set.
The end-of-run console output lists failed prompt sets and the relevant `stdout.jsonl`, `stderr.log`, or `last_message.md` paths.
Automated coverage includes a failing runner path rather than only dry-run and fake-success cases.

### Verification
Run `make review-tickets REVIEW_TICKETS_ARGS='--prompt-set error_handling_and_operability --runner <failing-stub>'`.
Confirm that the command exits non-zero, prints the failed prompt-set slug and artifact paths, and leaves a non-empty error artifact for that failed job.
Confirm that a successful run still writes the documented review artifacts under `agent_tickets/review_runs/<timestamp>/`.
