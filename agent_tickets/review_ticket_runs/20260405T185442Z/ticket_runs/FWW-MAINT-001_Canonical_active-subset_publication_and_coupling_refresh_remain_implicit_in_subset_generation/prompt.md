Work ticket FWW-MAINT-001: Canonical active-subset publication and coupling refresh remain implicit in subset generation.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: readability_and_maintainability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`generate_subsets_from_config()` still mixes two responsibilities: generating subset artifacts for requested presets and publishing the canonical active subset used by the mesh/assets pipeline. The `active_preset` branch quietly writes `paths.selected_root_ids` and may rematerialize the subset-scoped synapse registry, while the CLI wrapper exposes only "generate subsets" as a single action. Newer whole-brain planning code now cross-checks subset artifacts against `paths.selected_root_ids`, so the ambiguity is narrower than the original ticket implied, but the selection-to-mesh/assets handoff still depends on hidden active-preset behavior.

Requested Change:
Refactor the selection pipeline so "build preset artifacts" and "publish canonical active subset" are separate, explicitly named steps, while preserving current output files and CLI behavior. The publish step should own any `selected_root_ids` alias update and any subset-scoped synapse-registry refresh, and the returned summary should say what was actually published.

Acceptance Criteria:
- The code has one explicit helper, phase, or orchestration step that publishes the canonical active subset used by downstream `meshes` and `assets` commands.
- Synapse-registry refresh is triggered as named publish behavior, not as incidental path-key checks embedded in the preset-generation loop.
- The selection summary/index records whether `paths.selected_root_ids` was updated and whether subset-scoped coupling artifacts were refreshed for the active preset.
- Existing selection outputs for generated preset artifacts remain unchanged apart from the addition of explicit publication metadata.

Verification:
`make test`
