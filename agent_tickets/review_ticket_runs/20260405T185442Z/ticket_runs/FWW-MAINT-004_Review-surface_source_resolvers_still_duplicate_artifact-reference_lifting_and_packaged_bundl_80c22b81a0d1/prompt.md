Work ticket FWW-MAINT-004: Review-surface source resolvers still duplicate artifact-reference lifting and packaged bundle-alignment checks.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: readability_and_maintainability review

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The original ticket’s `showcase_session_planning.py` citations are stale, because showcase upstream-reference assembly has been moved behind a helper. The underlying issue is still present, though: dashboard, showcase-source resolution, and whole-brain-context planning still each hand-lift bundle metadata into review-surface artifact references with repeated `bundle_id` / `artifact_id` / `format` / `artifact_scope` / `status` plumbing, and packaged dashboard alignment checks are still duplicated across loaders and validators. Contract metadata already carries artifact-hook catalogs for these surfaces, but the current source-resolution paths do not share one helper for “lift bundle metadata into artifact references,” “merge explicit overrides against hook defaults,” and “validate packaged bundle alignment.”

Requested Change:
Introduce shared review-surface helpers that use contract hook metadata to lift packaged bundle metadata and discovered paths into artifact references, merge explicit artifact overrides, and validate packaged dashboard/showcase bundle alignment. Keep this ticket scoped to the duplicated source-resolution and packaged-surface validation paths in dashboard, showcase-source resolution, and whole-brain-context planning; do not broaden it into a larger contract-schema rewrite unless a minimal hook-shape adjustment is required.

Acceptance Criteria:
- `dashboard_session_planning`, `showcase_session_sources`, and `whole_brain_context_planning` no longer each maintain separate role-by-role blocks for the same packaged dashboard/showcase-style artifact-reference lifting.
- Explicit artifact override merging is handled by a shared helper or shared abstraction reused by showcase and whole-brain-context paths.
- Packaged dashboard/showcase `bundle_id` alignment checks are centralized and reused wherever metadata, payload, and state are loaded or validated.
- Updating an upstream role’s `artifact_id`, scope, or required contract version requires changing one shared mapping/lift path rather than planner-specific copy blocks.

Verification:
`make test`
`pytest tests/test_dashboard_session_planning.py tests/test_showcase_session_planning.py tests/test_whole_brain_context_planning.py`
