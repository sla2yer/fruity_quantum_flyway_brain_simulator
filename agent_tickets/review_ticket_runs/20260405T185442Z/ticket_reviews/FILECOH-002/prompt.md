Review work ticket FILECOH-002: Separate showcase session source resolution, narrative authoring, validation, and packaging.
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
## FILECOH-002 - Separate showcase session source resolution, narrative authoring, validation, and packaging
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: showcase session planning

### Problem
`showcase_session_planning.py` mixes upstream artifact resolution, narrative and preset authoring, rehearsal/dashboard patch validation, and bundle packaging in one file. The current shape makes story-level edits risky because they sit beside packaging and low-level UI validation rules.

### Evidence
[showcase_session_planning.py:288](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L288) resolves suite, dashboard, analysis, and validation inputs, then immediately assembles presets, steps, script payloads, preset catalogs, and export manifests before returning a plan; packaging is in the same module at [showcase_session_planning.py:540](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L540). The file also owns long presentation-specific builders at [showcase_session_planning.py:1982](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L1982) and [showcase_session_planning.py:3341](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3341), export assembly at [showcase_session_planning.py:4019](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4019) and [showcase_session_planning.py:4128](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4128), and deep rehearsal metadata validation at [showcase_session_planning.py:4479](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4479). The tests already depend on peer-module fixture builders at [test_showcase_session_planning.py:70](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_showcase_session_planning.py#L70), which is a sign that ownership is blurred across review surfaces.

### Requested Change
Split this module along real showcase seams: source and upstream artifact resolution, narrative or preset construction, presentation-state validation, and package or export writing. The planning entrypoint should compose those pieces instead of owning all four concerns directly.

### Acceptance Criteria
A top-level showcase planner remains, but preset or step generation lives outside the packaging code path, rehearsal or dashboard state validation lives in a validation-focused module, and export-manifest or bundle writing lives in a packaging-focused module. Showcase tests no longer need to reach through multiple peer test files to materialize reusable fixtures.

### Verification
`make test`
`make smoke`
