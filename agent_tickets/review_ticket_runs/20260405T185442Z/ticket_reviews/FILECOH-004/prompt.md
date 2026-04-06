Review work ticket FILECOH-004: Split experiment comparison discovery, scoring, and export packaging.
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
## FILECOH-004 - Split experiment comparison discovery, scoring, and export packaging
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: experiment comparison analysis

### Problem
`experiment_comparison_analysis.py` mixes filesystem bundle discovery, bundle-vs-plan validation, core comparison rollups, null-test evaluation, workflow orchestration, and UI or export packaging. That makes metric or null-test changes harder to review because the same file also owns report generation and artifact writing.

### Evidence
The file begins with bundle discovery at [experiment_comparison_analysis.py:84](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L84), computes the main summary at [experiment_comparison_analysis.py:255](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L255), orchestrates the full workflow at [experiment_comparison_analysis.py:451](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L451), packages bundle artifacts at [experiment_comparison_analysis.py:503](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L503), builds UI payloads at [experiment_comparison_analysis.py:853](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L853), evaluates null tests at [experiment_comparison_analysis.py:2142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2142), and assembles output summaries at [experiment_comparison_analysis.py:2613](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L2613). Those are separate seams in this repo: discovery or validation, analysis, and packaging or export.

### Requested Change
Split the module into a bundle discovery or validation module, a core comparison computation module, and a packaging or export module for UI payloads and report artifacts. `execute_experiment_comparison_workflow` should remain as a thin coordinator across those boundaries.

### Acceptance Criteria
Bundle discovery and plan-alignment validation no longer live in the same file as null-test scoring and export payload builders. The analysis summary can be computed without importing packaging helpers, and the packaging path consumes a normalized summary object rather than re-owning analysis logic.

### Verification
`make test`
`make smoke`
