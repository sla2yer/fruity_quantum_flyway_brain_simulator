## FWW-MAINT-001 - Canonical active-subset publication and coupling refresh remain implicit in subset generation
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: selection pipeline

### Problem
`generate_subsets_from_config()` still mixes two responsibilities: generating subset artifacts for requested presets and publishing the canonical active subset used by the mesh/assets pipeline. The `active_preset` branch quietly writes `paths.selected_root_ids` and may rematerialize the subset-scoped synapse registry, while the CLI wrapper exposes only "generate subsets" as a single action. Newer whole-brain planning code now cross-checks subset artifacts against `paths.selected_root_ids`, so the ambiguity is narrower than the original ticket implied, but the selection-to-mesh/assets handoff still depends on hidden active-preset behavior.

### Evidence
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L382) defines `generate_subsets_from_config()` as the single entry point for both preset generation and active-subset publication.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L438) writes `paths.selected_root_ids` only inside the `name == active_preset` branch after per-preset artifacts have already been built.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L445) refreshes the synapse registry based on `processed_coupling_dir` or `synapse_source_csv` path-key presence, rather than an explicit publish step or named selection-pipeline action.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L475) returns only `active_preset` plus `generated_presets`; it does not report whether canonical root IDs or coupling artifacts were published.
- [scripts/01_select_subset.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/01_select_subset.py#L44) exposes only `generate_subsets_from_config()`, so the operator-facing selection command still has no distinct publish phase.
- [scripts/02_fetch_meshes.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/02_fetch_meshes.py#L110) and [scripts/03_build_wave_assets.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/03_build_wave_assets.py#L106) still consume `paths.selected_root_ids` as the canonical downstream roster.
- [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L21) and [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L116) still lock the root-id alias write and subset-scoped synapse-registry refresh into the selection contract.
- [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L856) already validates subset artifact root IDs against `paths.selected_root_ids`, which narrows this ticket to the selection/asset-prep flow rather than the broader planning/runtime stack.

### Requested Change
Refactor the selection pipeline so "build preset artifacts" and "publish canonical active subset" are separate, explicitly named steps, while preserving current output files and CLI behavior. The publish step should own any `selected_root_ids` alias update and any subset-scoped synapse-registry refresh, and the returned summary should say what was actually published.

### Acceptance Criteria
- The code has one explicit helper, phase, or orchestration step that publishes the canonical active subset used by downstream `meshes` and `assets` commands.
- Synapse-registry refresh is triggered as named publish behavior, not as incidental path-key checks embedded in the preset-generation loop.
- The selection summary/index records whether `paths.selected_root_ids` was updated and whether subset-scoped coupling artifacts were refreshed for the active preset.
- Existing selection outputs for generated preset artifacts remain unchanged apart from the addition of explicit publication metadata.

### Verification
`make test`