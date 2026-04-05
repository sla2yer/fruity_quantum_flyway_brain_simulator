Review work ticket EFFMOD-FW-003: Let experiment-suite stages execute from a resolved simulation plan instead of replanning per stage and model mode.
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
## EFFMOD-FW-003 - Let experiment-suite stages execute from a resolved simulation plan instead of replanning per stage and model mode
- Status: open
- Priority: high
- Source: efficiency_and_modularity review
- Area: experiment suites

### Problem
Suite execution is wired around file paths instead of a reusable planning object, so the same materialized cell can reparse config/manifest inputs and rerun expensive planning work multiple times. In the simulation stage, the suite resolves a plan to discover model modes, then `execute_manifest_simulation()` resolves the same plan again for each mode. That planning path also loads fine-operator archives and runs an eigensolver to estimate spectral radius, so the duplicated work is materially expensive for surface-wave cells.

### Evidence
- [experiment_suite_execution.py:548](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L548) resolves `simulation_plan` once, then loops over `model_modes` and calls `execute_manifest_simulation(...)` at [experiment_suite_execution.py:570](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L570).
- [simulator_execution.py:161](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L161) shows `execute_manifest_simulation()` immediately calling `resolve_manifest_simulation_plan(...)` again at [simulator_execution.py:172](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L172).
- [simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) reloads config, manifest, schema, and design lock on each plan resolution.
- [simulation_planning.py:4315](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4315) and [simulation_planning.py:4771](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L4771) compute spectral radius by reopening the operator archive and running `eigsh`.
- [experiment_suite_execution.py:731](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_execution.py#L731) shows the validation stage resolving the full simulation plan again for the same work item.

### Requested Change
Introduce a reusable suite execution context that carries a resolved simulation plan, resolved arm plans, and cached operator-stability metadata. Update simulator and validation entrypoints so they can consume that object directly instead of forcing a path-based round-trip back through `resolve_manifest_simulation_plan()`.

### Acceptance Criteria
- A suite work item resolves its manifest/config-driven simulation plan once and reuses it across simulation and validation stages.
- Executing multiple model modes for one materialized cell does not call `resolve_manifest_simulation_plan()` repeatedly.
- Spectral-radius estimation is computed once per unique operator bundle per plan, or loaded from cached plan/metadata state.

### Verification
- `.venv/bin/python -m unittest tests.test_experiment_suite_execution tests.test_simulation_planning tests.test_simulator_execution -v`
- `make smoke`

## error_handling_and_operability

# Error Handling And Operability Review Tickets
