Review work ticket FILECOH-003: Move whole-brain context query execution and packaging out of the planning catch-all.
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
## FILECOH-003 - Move whole-brain context query execution and packaging out of the planning catch-all
- Status: open
- Priority: high
- Source: file_length_and_cohesion review
- Area: whole-brain context planning

### Problem
`whole_brain_context_planning.py` is nominally a planner, but it also executes whole-brain queries, generates preset executions, applies downstream handoffs, builds view payload or state, and packages artifacts. That collapses planning, query execution, and local review packaging into one module.

### Evidence
[whole_brain_context_planning.py:188](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L188) resolves source context, merges artifact references, builds query inputs, and directly calls `execute_whole_brain_context_query` at [whole_brain_context_planning.py:330](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L330). The same file executes preset queries again inside the preset library builder at [whole_brain_context_planning.py:1921](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L1921) and [whole_brain_context_planning.py:2018](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2018), then switches to downstream handoff mutation and catalog or view assembly around [whole_brain_context_planning.py:2450](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L2450) and packages bundles at [whole_brain_context_planning.py:448](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/src/flywire_wave/whole_brain_context_planning.py#L448). Test setup also crosses planning modules at [test_whole_brain_context_planning.py:48](/home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo/tests/test_whole_brain_context_planning.py#L48).

### Requested Change
Keep source and contract resolution in the planning module, but move query execution or preset hydration behind the `whole_brain_context_query` family and move bundle payload or state packaging behind a packaging-oriented module. Downstream handoff enrichment should sit with the query or presentation layer it belongs to, not inside the top-level planner.

### Acceptance Criteria
`resolve_whole_brain_context_session_plan` becomes an orchestrator that consumes source context and query results instead of executing queries inline. Query execution, preset execution, and package payload or state builders are owned by narrower modules whose names match those responsibilities.

### Verification
`make test`
`make validate-manifest`
`make smoke`
