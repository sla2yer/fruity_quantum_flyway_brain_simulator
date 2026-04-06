Work ticket FILECOH-005: Split simulator CLI and result-bundle packaging behind a stable execution facade.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: file_length_and_cohesion review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`simulator_execution.py` is still the stable public entrypoint for manifest-driven simulator runs, but it remains a 1,872-line mixed module that owns CLI parsing, baseline and surface-wave execution orchestration, extension artifact definitions, bundle writing, provenance serialization, and UI-facing comparison payload assembly. The original ticket is still accurate, but the current repo state makes the requirement sharper: preserve the execution API while extracting CLI and result-bundle packaging into dedicated seams.

Requested Change:
Keep `execute_manifest_simulation` as the stable library facade and keep its return shape intact. Move CLI parsing and stdout formatting into `scripts/run_simulation.py` or a dedicated simulator CLI module. Move extension artifact-spec builders, bundle writes, provenance assembly, UI comparison payload construction, and wave-only extension serialization into a simulator packaging module that consumes normalized execution results plus the existing `simulator_result_contract` helpers. Preserve current artifact IDs, file formats, and executed-run summary fields so readiness, dashboard, wave-analysis, validation, and suite flows do not need a contract migration.

Acceptance Criteria:
`scripts/run_simulation.py` or a dedicated CLI sibling becomes the real CLI entrypoint, and `src/flywire_wave/simulator_execution.py` no longer imports `argparse` or owns command-line parsing. `execute_manifest_simulation` remains import-compatible for current callers, but artifact-spec declaration and package writing for `structured_log`, `execution_provenance`, `ui_comparison_payload`, `surface_wave_summary`, `surface_wave_patch_traces`, `surface_wave_coupling_events`, and `mixed_morphology_state_bundle` live outside `simulator_execution.py`. The current artifact IDs, bundle formats, and run-summary fields remain unchanged, and execution-focused tests can exercise orchestration without asserting all packaging payload details in the same module surface.

Verification:
`make test`
`make smoke`
