Review work ticket FILECOH-001: Split simulation manifest planning from analysis and asset/runtime resolution.
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
## FILECOH-001 - Split simulation manifest planning from analysis and asset/runtime resolution
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: simulation planning

### Problem
`simulation_planning.py` has become the catch-all owner for manifest validation, runtime normalization, readout-analysis planning, circuit asset discovery, and surface-wave mixed-fidelity execution planning. That makes routine changes to one planning seam pull several unrelated subsystems into the same file and review surface.

### Evidence
[simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) resolves the manifest, validates it, normalizes runtime config, resolves inputs, and calls circuit asset discovery in the same top-level path. The file then shifts into readout-analysis planning at [simulation_planning.py:743](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L743), local geometry/coupling readiness checks at [simulation_planning.py:2950](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2950), surface-wave execution plan assembly at [simulation_planning.py:3406](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3406), and mixed-fidelity/operator routing at [simulation_planning.py:3667](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L3667). The test surface mirrors that spillover: [test_simulator_execution.py:56](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L56) and [test_experiment_suite_aggregation.py:37](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_experiment_suite_aggregation.py#L37) import fixture builders from [test_simulation_planning.py:931](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L931) and [test_simulation_planning.py:1070](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulation_planning.py#L1070).

### Requested Change
Keep `resolve_manifest_simulation_plan` as the orchestration entrypoint, but move readout-analysis planning under an analysis-planning boundary, move geometry/coupling asset resolution under an asset-readiness boundary, and move surface-wave or mixed-fidelity execution-plan construction under an execution-runtime planning boundary.

### Acceptance Criteria
`simulation_planning.py` is reduced to manifest-level orchestration and shared normalization, while readout-analysis helpers, circuit asset discovery or validation, and surface-wave mixed-fidelity planning live in narrower modules with explicit imports. Shared test fixture writers are moved out of `test_simulation_planning.py` into a dedicated test utility module instead of remaining trapped in the planner test file.

### Verification
`make test`
`make validate-manifest`
`make smoke`
