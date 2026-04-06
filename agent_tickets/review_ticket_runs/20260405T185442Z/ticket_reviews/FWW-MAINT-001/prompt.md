Review work ticket FWW-MAINT-001: Active subset publication is hidden inside preset generation.
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
## FWW-MAINT-001 - Active subset publication is hidden inside preset generation
- Status: open
- Priority: high
- Source: readability_and_maintainability review
- Area: subset selection

### Problem
The canonical selected-root roster for the rest of the pipeline is not modeled as its own step. Instead, `generate_subsets_from_config()` quietly publishes one preset as the authoritative `selected_root_ids` alias and may also refresh the subset-scoped synapse registry as a side effect of iterating generated presets. That makes it hard to tell which subset output is authoritative for `select -> meshes -> assets -> simulation`, and maintainers have to remember that the active preset has extra behavior that other generated presets do not.

### Evidence
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L257) loops over all requested presets, but only the `active_preset` branch writes `paths.selected_root_ids` and conditionally calls `materialize_synapse_registry()`.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L283) ties synapse-registry refresh to the presence of `processed_coupling_dir` or `synapse_source_csv`, so the canonical coupling side effect is controlled by path-key presence rather than an explicit publish step.
- [selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L313) returns only `active_preset` plus generated artifact paths; it does not record whether the canonical alias or subset-scoped coupling registry was actually refreshed.
- [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L19) and [test_selection.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_selection.py#L114) show that this hidden side effect is part of the external contract.

### Requested Change
Separate “build preset artifacts” from “publish canonical active subset” into explicit steps or helpers, and return structured metadata showing which preset became the authoritative root roster and whether subset-scoped coupling artifacts were refreshed.

### Acceptance Criteria
- The code has one explicit helper or phase that publishes the canonical active subset used downstream.
- The conditions for refreshing the subset-scoped synapse registry are expressed as named selection-pipeline behavior, not as incidental path-key checks inside the preset loop.
- The returned summary clearly states which preset, if any, updated `selected_root_ids` and coupling-side artifacts.

### Verification
`make test`
