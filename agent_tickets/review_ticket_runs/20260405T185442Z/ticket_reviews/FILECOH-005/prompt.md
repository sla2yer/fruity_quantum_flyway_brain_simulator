Review work ticket FILECOH-005: Remove CLI and UI/export packaging concerns from simulator execution.
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
## FILECOH-005 - Remove CLI and UI/export packaging concerns from simulator execution
- Status: open
- Priority: medium
- Source: file_length_and_cohesion review
- Area: simulator execution

### Problem
`simulator_execution.py` mixes a library workflow API, an argparse CLI entrypoint, baseline and surface-wave execution, bundle writing, provenance generation, and UI comparison payload assembly. That blurs the boundary between execution/runtime code and packaging or presentation code, and it leaves `scripts/run_simulation.py` as a trivial shim instead of the actual CLI surface.

### Evidence
[scripts/run_simulation.py:1](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/run_simulation.py#L1) only imports `main` from the library, while [simulator_execution.py:161](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L161) exposes the reusable execution workflow and [simulator_execution.py:221](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L221) still owns argparse parsing. The same module writes bundle artifacts in [simulator_execution.py:285](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L285) and [simulator_execution.py:354](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L354), then switches to provenance and UI payload shaping at [simulator_execution.py:1582](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1582) and [simulator_execution.py:1635](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulator_execution.py#L1635). The tests also depend on simulation-planning fixture writers at [test_simulator_execution.py:56](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_simulator_execution.py#L56), which shows execution and planning surfaces are already too entangled.

### Requested Change
Move the CLI parser into `scripts/run_simulation.py` or a dedicated CLI wrapper, and move result-bundle packaging or UI payload generation behind a simulator packaging boundary. Keep the execution module focused on resolving runnable arm plans, invoking runtimes, and returning structured execution results.

### Acceptance Criteria
`src/flywire_wave/simulator_execution.py` no longer contains argparse handling or UI/export payload builders, and `scripts/run_simulation.py` becomes the real CLI entrypoint instead of a pass-through import. Execution helpers can be imported without pulling in packaging or presentation concerns.

### Verification
`make test`
`make smoke`

## overengineering_and_abstraction_load

# Overengineering And Abstraction Load Review Tickets
