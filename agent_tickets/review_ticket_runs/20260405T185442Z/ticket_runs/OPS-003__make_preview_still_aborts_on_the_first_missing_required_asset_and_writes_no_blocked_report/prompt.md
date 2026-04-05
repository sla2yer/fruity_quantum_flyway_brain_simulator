Work ticket OPS-003: `make preview` still aborts on the first missing required asset and writes no blocked report.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: error_handling_and_operability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`make preview` is still the outlier among the local inspection/report commands. If any requested root is missing a required preview input, the CLI raises a traceback before it writes the deterministic preview bundle, so operators get neither a blocked summary nor an aggregate view of which roots are incomplete after a partial `make assets` run.

Requested Change:
Align geometry preview with the repo’s existing blocked-report behavior for ordinary missing local prerequisites. The preview command should collect missing required preview inputs per root, write the deterministic output bundle anyway, and return a structured blocked summary instead of propagating `FileNotFoundError` to stderr.

Acceptance Criteria:
`make preview CONFIG=...` writes `summary.json` and `root_ids.txt` even when one or more requested roots are missing required preview inputs.
Ordinary missing-prerequisite cases do not emit a Python traceback; the command returns a structured blocked result instead of crashing.
The summary identifies blocked roots, missing asset keys, and resolved file paths, and it aggregates all missing prerequisites across the requested root set rather than stopping at the first miss.
The output tells the operator whether the missing prerequisite implies rerunning `make meshes`, `make assets`, or both.
A fully built root still produces the current happy-path preview output, and `tests/test_geometry_preview.py` gains a missing-prerequisite regression case.

Verification:
Create a local preview bundle with `make assets CONFIG=config/local.yaml`, remove one required preview input such as `<root_id>_patch_graph.npz`, then run `make preview CONFIG=config/local.yaml`.
Confirm that the command writes the deterministic preview output directory and a structured blocked summary naming the missing asset path and affected root IDs, without a traceback.
Repeat with multiple incomplete roots or multiple missing required assets to confirm the report aggregates all blocked prerequisites instead of aborting on the first miss.
Confirm that a fully built asset set still produces the existing happy-path preview HTML and summary.
