Review work ticket APICPL-004: Subset handoff contract is duplicated across selection, planners, and readiness fixtures.
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
## APICPL-004 - Subset handoff contract is duplicated across selection, planners, and readiness fixtures
- Status: open
- Priority: medium
- Source: api_boundaries_and_coupling review
- Area: selection / subset handoff

### Problem
`selected_root_ids.txt` and `subset_manifest.json` are public pipeline handoff artifacts, but their filenames, safe-name rules, and JSON payload shape are reconstructed in multiple modules instead of being owned by one library contract. Any future change to subset metadata or naming has to be coordinated manually across planning and readiness code.

### Evidence
- `[src/flywire_wave/selection.py#L103](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L103)`, `[src/flywire_wave/selection.py#L142](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L142)`, and `[src/flywire_wave/selection.py#L413](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/selection.py#L413)` define the canonical subset artifact names and payload shape.
- `[src/flywire_wave/simulation_planning.py#L176](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L176)` and `[src/flywire_wave/simulation_planning.py#L2823](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/simulation_planning.py#L2823)` duplicate the subset-manifest filename and path resolution.
- `[src/flywire_wave/experiment_suite_planning.py#L1806](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/experiment_suite_planning.py#L1806)` hardcodes the same filename again.
- Readiness fixtures hand-write the same contract in `[src/flywire_wave/milestone9_readiness.py#L315](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone9_readiness.py#L315)`, `[src/flywire_wave/milestone10_readiness.py#L392](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone10_readiness.py#L392)`, `[src/flywire_wave/milestone11_readiness.py#L472](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone11_readiness.py#L472)`, `[src/flywire_wave/milestone12_readiness.py#L610](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone12_readiness.py#L610)`, and `[src/flywire_wave/milestone13_readiness.py#L838](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/milestone13_readiness.py#L838)`.

### Requested Change
Introduce a small selection/subset contract helper that owns subset artifact path building, safe-name normalization, manifest serialization/parsing, and active-root roster references. Route selection generation, simulation planning, suite planning, and readiness fixture writers through that helper.

### Acceptance Criteria
One library surface owns `subset_manifest.json` and selected-root roster semantics, and downstream consumers stop hardcoding the filename or manually serializing subset manifest payloads.

### Verification
`python3 -m unittest tests.test_simulation_planning -v`; `python3 -m unittest tests.test_selection -v` after installing `networkx`; add readiness-fixture regressions that round-trip generated subset references through the shared helper.

## efficiency_and_modularity

# Efficiency And Modularity Review Tickets
