Work ticket APICPL-001: Manifest validation resolves stimulus bundle paths outside runtime config.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: api_boundaries_and_coupling review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The public `validate-manifest` surface emits bundle-facing stimulus metadata, but it resolves the processed stimulus root from a repo default instead of the runtime config that manifest-driven execution actually uses. That means the repo’s safe validation loop can report a different external bundle path than `run_simulation.py` or other manifest-driven runners for the same manifest.

Requested Change:
Create one library-owned manifest-input resolver that accepts either `config_path` or explicit processed bundle roots, and route `scripts/04_validate_manifest.py`, manifest-driven stimulus/retinal workflows, and simulation planning through it. If validation keeps returning bundle paths, those paths need to be config-aware.

Acceptance Criteria:
`validate-manifest`, `resolve_manifest_simulation_plan`, and manifest-driven bundle recorders produce the same `stimulus_bundle_reference` and `stimulus_bundle_metadata_path` for the same manifest plus runtime config, including nondefault `processed_stimulus_dir` values.

Verification:
`make validate-manifest`; `python3 -m unittest tests.test_manifest_validation -v`; add a regression test that compares validation output against `resolve_manifest_simulation_plan` under a nondefault `config.paths.processed_stimulus_dir`.
