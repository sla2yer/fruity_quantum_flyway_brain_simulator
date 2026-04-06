Review work ticket OVR-004: Narrow the dashboard build API to the repo’s real entry path.
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
## OVR-004 - Narrow the dashboard build API to the repo’s real entry path
- Status: open
- Priority: high
- Source: overengineering_and_abstraction_load review
- Area: dashboard session planning / CLI

### Problem
Dashboard packaging is exposed as a generalized source-mode framework with manifest, experiment, and explicit per-bundle assembly modes. In this repo, the documented happy path is manifest-driven build plus open/export of an already packaged session. Keeping all three public acquisition modes makes the main local flow harder to understand and forces the planner to act like a bundle-orchestration framework the repo does not actually need.

### Evidence
- The documented workflow is manifest-driven at [Makefile:148](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L148) and [Makefile:151](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L151), with packaged-session export at [Makefile:154](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/Makefile#L154).
- The public CLI still exposes experiment and explicit bundle assembly knobs at [scripts/29_dashboard_shell.py:61](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L61) and [scripts/29_dashboard_shell.py:68](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/scripts/29_dashboard_shell.py#L68).
- The planner defines three source modes at [src/flywire_wave/dashboard_session_planning.py:136](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L136) and exposes a broad multi-input public signature at [src/flywire_wave/dashboard_session_planning.py:158](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L158).
- The alternate modes are actively maintained for equivalence in [tests/test_dashboard_session_planning.py:193](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L193) and [tests/test_dashboard_session_planning.py:243](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_dashboard_session_planning.py#L243).

### Requested Change
Keep one public dashboard build path centered on manifest-driven planning, plus the existing open/export operations on packaged sessions. If explicit bundle assembly is still useful for fixtures, move it behind a private helper instead of the public CLI and public planner signature.

### Acceptance Criteria
- `scripts/29_dashboard_shell.py build` and `resolve_dashboard_session_plan()` no longer advertise three equivalent acquisition modes publicly.
- `make dashboard`, `make dashboard-open`, and packaged-session export behavior remain intact.
- Fixture-only alternate assembly, if retained, is internal rather than part of the main user-facing API.

### Verification
- `make test`
- `make milestone14-readiness`

## readability_and_maintainability

# Readability And Maintainability Review Tickets
