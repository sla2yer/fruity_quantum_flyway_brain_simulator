Review work ticket OVR-003: Remove the unused “partial arm plan” execution path.
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
## OVR-003 - Remove the unused “partial arm plan” execution path
- Status: open
- Priority: high
- Source: overengineering_and_abstraction_load review
- Area: simulation planning / simulator execution

### Problem
Execution supports a second hypothetical arm-plan shape where bundle metadata is missing and must be reconstructed from fragments. The actual repo happy path never produces that shape: the planner already materializes `result_bundle.metadata` for every arm before execution. Carrying both shapes creates unnecessary indirection and a second source of truth in the core `baseline` / `surface_wave` path.

### Evidence
- [src/flywire_wave/simulation_planning.py:674](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L674), [src/flywire_wave/simulation_planning.py:686](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L686), and [src/flywire_wave/simulation_planning.py:687](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L687) always attach `result_bundle` metadata during plan construction.
- [src/flywire_wave/simulator_execution.py:172](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L172) and [src/flywire_wave/simulator_execution.py:178](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L178) feed those normalized arm plans straight into execution.
- [src/flywire_wave/simulator_execution.py:520](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L520) still falls back to rebuilding metadata from `manifest_reference`, `arm_reference`, `determinism`, `selected_assets`, and runtime state.

### Requested Change
Make planner-produced `result_bundle.metadata` the only supported execution input. Delete the fallback metadata reconstruction path and simplify processed-results-dir resolution around that single normalized arm-plan shape.

### Acceptance Criteria
- Simulator execution requires normalized arm plans with `result_bundle.metadata`.
- Missing bundle metadata fails clearly instead of silently reconstructing a second metadata representation.
- Baseline and surface-wave bundle ids, paths, and artifacts remain unchanged for manifest-driven runs.

### Verification
- `make test`
- `make milestone9-readiness`
- `make milestone10-readiness`
