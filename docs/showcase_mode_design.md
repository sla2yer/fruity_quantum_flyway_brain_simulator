# Showcase Mode Design

## Purpose

Milestone 16 needs one library-owned showcase contract before polished demo
logic starts spreading across dashboard state dumps, suite reports, and ad hoc
export scripts. The versioned software contract is `showcase_session.v1`,
implemented in `flywire_wave.showcase_session_contract`.

The contract composes with earlier milestones instead of replacing them:

- `dashboard_session.v1` still owns replay semantics, pane state, and the
  packaged review surface that showcase presets build on top of.
- `experiment_suite.v1` still owns suite-level rollups, comparison plots, and
  review artifacts that support a polished story with deterministic context.
- `experiment_analysis_bundle.v1` still owns the Milestone 12 comparison and
  summary payloads that the fair-comparison and closing-summary beats cite.
- `validation_ladder.v1` still owns validation findings and reviewer handoff
  state that act as scientific guardrails on the highlighted wave-only beat.

## Bundle Surface

The default bundle layout is:

- `.../showcase_sessions/<experiment_id>/<showcase_spec_hash>/showcase_session.json`
- `.../showcase_sessions/<experiment_id>/<showcase_spec_hash>/showcase_script.json`
- `.../showcase_sessions/<experiment_id>/<showcase_spec_hash>/showcase_state.json`
- `.../showcase_sessions/<experiment_id>/<showcase_spec_hash>/narrative_preset_catalog.json`
- `.../showcase_sessions/<experiment_id>/<showcase_spec_hash>/exports/showcase_export_manifest.json`

`showcase_session.json` is the authoritative discovery anchor. The other files
reserve one deterministic place for later scripted playback, saved-preset, and
export work without mutating upstream dashboard, suite, analysis, or validation
contracts.

## Seven-Step Flow

The v1 step ids are fixed:

1. `scene_selection`
2. `fly_view_input`
3. `active_visual_subset`
4. `activity_propagation`
5. `baseline_wave_comparison`
6. `approved_wave_highlight`
7. `summary_analysis`

The ids are intentionally short and stable. Visible labels may change later,
but later Milestone 16 work should not rename these ids without a contract
version change.

Each step also carries one default preset id and one default cue kind:

- `scene_selection` -> `scene_context` -> `camera_transition`
- `fly_view_input` -> `retinal_input_focus` -> `playback_scrub`
- `active_visual_subset` -> `subset_context` -> `overlay_reveal`
- `activity_propagation` -> `propagation_replay` -> `playback_scrub`
- `baseline_wave_comparison` -> `paired_comparison` -> `comparison_swap`
- `approved_wave_highlight` -> `approved_highlight` -> `narration_callout`
- `summary_analysis` -> `analysis_summary` -> `export_capture`

`highlight_fallback` is the one reserved fallback preset for the highlight
beat.

## Ownership Boundary

The handoff is explicit in the contract metadata:

- Jack owns scripted playback mechanics, saved-preset identity, camera
  transitions, polished UI state, operator controls, deterministic packaging,
  and export surfaces.
- Grant owns which scientific comparison is approved for the story, which
  wave-specific phenomenon is allowed to occupy the highlight beat, and the
  guardrail review on that beat's scientific claim scope.

The boundary rule is simple:

- Jack may decide how the story is played and exported.
- Grant decides whether the highlighted effect is scientifically acceptable to
  show at all.

## Guardrail And Fallback

The fair comparison beat remains `baseline_wave_comparison`. That is the
contract-owned fairness boundary for direct baseline-versus-wave claims.

`approved_wave_highlight` is a separate beat with stricter rules:

- it requires explicitly labeled wave-only evidence
- it requires validation-backed guardrail evidence
- it must remain visibly distinct from the fair paired comparison surface

If the requested highlight is unavailable, unapproved, or not scientifically
defensible, later showcase code must:

- switch the beat to the `highlight_fallback` preset
- use cue kind `fallback_redirect`
- include the `fallback_notice` narrative annotation
- keep the paired-comparison beat intact rather than fabricating a substitute
  wave-only effect

That is the canonical Milestone 16 fallback rule.

## Preserved Invariants

Later showcase tickets should preserve these invariants unless
`showcase_session.v1` changes:

- the seven-step order stays fixed
- preset ids, cue kinds, annotation ids, evidence-role ids, operator-control
  ids, export-target-role ids, and presentation-status ids stay contract-owned
- showcase sessions discover upstream dashboard, suite, analysis, and
  validation artifacts through metadata-backed role hooks rather than filename
  guessing
- showcase-owned artifacts remain downstream package outputs and do not rewrite
  earlier milestone bundle metadata
- the highlight beat stays subordinate to Grant-owned scientific approval and
  validation-backed guardrails

If later work needs different beat ids, different fallback meaning, or a
different ownership boundary, that is a new showcase contract version rather
than a silent edit to `showcase_session.v1`.
