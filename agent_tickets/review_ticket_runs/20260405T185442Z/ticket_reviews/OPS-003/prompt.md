Review work ticket OPS-003: `make preview` aborts on the first missing asset instead of emitting a blocked report.
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
