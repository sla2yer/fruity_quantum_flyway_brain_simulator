Review work ticket FWW-MAINT-004: Review-surface packagers hand-build the same artifact-reference logic in multiple modules.
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
## FWW-MAINT-004 - Review-surface packagers hand-build the same artifact-reference logic in multiple modules
- Status: open
- Priority: medium
- Source: readability_and_maintainability review
- Area: packaged review surfaces

### Problem
Dashboard, showcase, and whole-brain-context planners repeatedly hand-assemble artifact-reference payloads from upstream bundle metadata and then re-check the same bundle-alignment invariants. That obscures which fields are authoritative for packaged review surfaces: discovered bundle paths, metadata `artifacts`, explicit overrides, or copied session references. Any contract change to artifact IDs, scopes, or required alignment now needs synchronized edits across several large modules.

### Evidence
- [dashboard_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/dashboard_session_planning.py#L1359) manually maps each upstream artifact into dashboard references by repeating `bundle_id`, `artifact_id`, `format`, `artifact_scope`, and `status`.
- [showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L3756) repeats the same pattern for dashboard, analysis, validation, and suite artifacts, then maintains a separate explicit-override merge path at [showcase_session_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/showcase_session_planning.py#L4203).
- [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1185) builds yet another artifact-reference catalog for subset, dashboard, showcase, and connectivity artifacts.
- The same `bundle_id` alignment rule for dashboard metadata/payload/state is duplicated in [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1134), [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3336), [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3419), and [whole_brain_context_planning.py](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L3443).

### Requested Change
Introduce shared helpers for “lift bundle metadata into artifact references” and “validate packaged bundle alignment”, with declarative role-to-artifact mappings reused by dashboard, showcase, and whole-brain-context planners.

### Acceptance Criteria
- Artifact-reference construction for packaged review surfaces is driven by shared helpers or declarative maps rather than repeated hand-written blocks.
- Bundle-alignment checks for packaged dashboard/showcase/session records are centralized.
- A contract change to an upstream artifact role or artifact ID requires updating one shared mapping path, not each planner separately.

### Verification
`make test`

## testing_and_verification_gaps

# Testing And Verification Gaps Review Tickets
