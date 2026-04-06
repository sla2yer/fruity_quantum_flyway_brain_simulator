Work ticket FILECOH-003: Move whole-brain context query orchestration, preset hydration, and packaging out of the planning catch-all.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: file_length_and_cohesion review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
`whole_brain_context_planning.py` is still a 3,700+ line catch-all. The low-level query engine already lives in `whole_brain_context_query.py`, but the planning module still resolves source artifacts, constructs execution inputs, invokes the query engine inline, re-executes queries for every preset, injects downstream handoff targets, builds packaged session payload/catalog/state objects, and writes the bundle. Planning, preset hydration, presentation shaping, and package I/O remain collapsed into one module.

Requested Change:
Keep source-mode resolution, artifact discovery and override handling, selection resolution, and contract/query-profile selection in `whole_brain_context_planning.py`. Move session-level query orchestration behind a narrower query-facing layer that accepts resolved inputs and returns `query_execution`, hydrated preset results, and handoff-enriched query artifacts. Move `context_query_catalog`, `context_view_payload`, `context_view_state`, and bundle-write behavior behind a packaging-oriented module or service. The planner should orchestrate those components instead of re-running preset queries, mutating handoff payloads, and writing packaged artifacts itself.

Acceptance Criteria:
`resolve_whole_brain_context_session_plan` remains responsible for config, source context, artifact reference, selection, and query-state resolution, but it no longer calls `execute_whole_brain_context_query` or performs preset hydration inline inside `whole_brain_context_planning.py`. Per-preset execution is no longer implemented inside `_build_query_preset_library` in the planning module; preset hydration is owned by a narrower query or preset module whose name matches that responsibility. Downstream handoff enrichment for query results and preset payloads no longer lives in `whole_brain_context_planning.py`. `package_whole_brain_context_session` no longer performs dashboard sub-packaging or writes session JSON artifacts directly from the planning module; that work is owned by a packaging-oriented module. `whole_brain_context_planning.py` stops defining the builders for `context_query_catalog`, `context_view_payload`, and `context_view_state`, and planning tests focus on orchestration boundaries rather than preset packaging and handoff lineage.

Verification:
`make test`
`make validate-manifest`
`make smoke`
