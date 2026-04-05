Review work ticket APICPL-002: Experiment bundle discovery is implemented as directory globbing instead of contract-owned lookup.
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
## APICPL-002 - Experiment bundle discovery is implemented as directory globbing instead of contract-owned lookup
- Status: open
- Priority: high
- Source: api_boundaries_and_coupling review
- Area: experiment analysis / dashboard planning

### Problem
Several planners discover packaged bundles by rebuilding directory layout and metadata filenames instead of asking a contract-owned helper to resolve them from plan identity. That leaks filename and folder ownership into higher-level workflows and makes stray files under an experiment directory part of discovery policy.

### Evidence
- `[src/flywire_wave/experiment_comparison_analysis.py#L149](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L149)` constructs `.../bundles/<experiment_id>/<arm_id>/`, and `[src/flywire_wave/experiment_comparison_analysis.py#L152](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_comparison_analysis.py#L152)` globs `*/simulator_result_bundle.json`.
- `[src/flywire_wave/dashboard_session_planning.py#L260](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L260)` already has a manifest-derived `bundle_set`, but `[src/flywire_wave/dashboard_session_planning.py#L674](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L674)` and `[src/flywire_wave/dashboard_session_planning.py#L725](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L725)` still glob analysis and validation bundle metadata under hardcoded contract filenames.
- `[src/flywire_wave/validation_planning.py#L476](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/validation_planning.py#L476)` shows the better pattern: derive the expected analysis bundle path from plan identity via contract helpers instead of scanning the filesystem.

### Requested Change
Add contract-owned discovery APIs for simulator, experiment-analysis, and validation bundle metadata lookup from plan identity or bundle ids, and replace raw `glob("*/...json")` discovery in `experiment_comparison_analysis.py` and `dashboard_session_planning.py`.

### Acceptance Criteria
High-level planners no longer hardcode `*/simulator_result_bundle.json`, `*/experiment_analysis_bundle.json`, or `*/validation_bundle.json` discovery. Discovery remains stable if on-disk naming changes behind the contract helpers.

### Verification
`python3 -m unittest tests.test_experiment_comparison_analysis -v`; `python3 -m unittest tests.test_simulation_planning -v`; `python3 -m unittest tests.test_dashboard_session_planning -v` after full dev dependencies are installed (`trimesh` is missing in this environment).
