Review work ticket OVR-001: Remove the second full resolver from `compare-analysis`.
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
## OVR-001 - Remove the second full resolver from `compare-analysis`
- Status: open
- Priority: medium
- Source: overengineering_and_abstraction_load review
- Area: simulation planning / experiment comparison analysis

### Problem
The `make compare-analysis` path resolves the same manifest twice. `execute_experiment_comparison_workflow()` builds a full simulation plan, then asks for a separate readout-analysis plan through a helper that just rebuilds the same simulation plan and extracts one field. That extra abstraction hop does not buy a second real workflow in this repo.

### Evidence
- [src/flywire_wave/experiment_comparison_analysis.py:459](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L459) resolves `simulation_plan`, then [src/flywire_wave/experiment_comparison_analysis.py:465](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L465) resolves `analysis_plan` separately.
- [src/flywire_wave/simulation_planning.py:722](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L722) shows `resolve_manifest_readout_analysis_plan()` immediately calling [src/flywire_wave/simulation_planning.py:482](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L482) and only returning `readout_analysis_plan`.
- The public happy path is the single manifest-driven target at [Makefile:145](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L145), not two distinct planning backends.

### Requested Change
Resolve the manifest once in the comparison workflow and read `readout_analysis_plan` directly from that normalized simulation plan. If a helper is still wanted, make it a pure extractor from an existing plan rather than a second full resolver.

### Acceptance Criteria
- `execute_experiment_comparison_workflow()` performs one top-level manifest/config/schema/design-lock resolution.
- There is no public helper that re-runs full simulation planning solely to return `readout_analysis_plan`.
- Experiment-analysis outputs remain unchanged.

### Verification
- `make test`
- `make smoke`
