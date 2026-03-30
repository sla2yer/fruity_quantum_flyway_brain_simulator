# FW-M16-006 Rationale

## Design Choices

This ticket turns the last three Milestone 16 beats into planner-owned
showcase state instead of leaving them as implicit operator convention.

The main choice was to keep the implementation inside the existing
`showcase_session_planning` and `showcase_player` layers:

- the comparison beat now packages one canonical `comparison_act` with stable
  pairing semantics, shared-timebase metadata, and an explicit fairness
  boundary between `shared_comparison` and `wave_only_diagnostic`
- the highlight beat now packages one explicit `highlight_presentation` that
  labels the wave-only scope, carries traceable evidence references, and
  switches cleanly to a caveated fallback view when approval is missing
- the closing beat now packages one `summary_analysis_landing` with a fixed
  headline, newcomer-readable summary lines, decision-panel claim rows, and
  links back to analysis, suite, and validation evidence

I kept the evidence trace anchored to existing artifact-role references rather
than inventing a new review contract. The player resolves those step evidence
references into runtime `evidence_hooks` with artifact paths and bundle ids, so
the presentation layer can stay lightweight while still being traceable.

The late-stage presets also now carry the same choreography/UI metadata model
used by the first four beats. That keeps the comparison, highlight, and summary
acts inside one coherent showcase-state system instead of becoming special-case
JSON islands.

## Testing Strategy

Coverage is split between plan packaging and runtime application.

- `tests/test_showcase_session_planning.py` now checks deterministic packaged
  comparison/highlight/summary metadata, explicit fallback demotion when the
  highlight is not approved, and clear showcase-level failure handling for pair
  loss and shared-timebase loss.
- `tests/test_showcase_player.py` now drives a packaged session through
  `baseline_wave_comparison`, `approved_wave_highlight`, and `summary_analysis`
  while asserting fairness labels, view kinds, and resolved evidence hooks.

That split matches the architecture: the planner owns the story metadata, and
the player owns how that metadata is surfaced at runtime.

## Simplifications

This version still stops short of a dedicated rendered showcase shell.

- comparison, highlight, and summary “views” are structured metadata, not new
  HTML panes
- evidence hooks resolve to artifact references and paths, not rich rendered
  citations or inline previews
- the closing summary is newcomer-readable text plus decision-row metadata, not
  a fully designed presentation slide

Those simplifications keep the scope aligned with the ticket: make the story
honest and reproducible first, then let later UI/export work decide how to draw
it.

## Future Expansion

- Consume `presentation_view`, `fairness_boundary`, and `evidence_hooks`
  directly in a dedicated showcase shell or dashboard-shell integration.
- Promote any late-stage view identifiers that need stronger guarantees into
  the showcase contract if they become cross-layer dependencies.
- Add richer summary rendering that can preview suite plots or validation
  findings inline without changing the underlying evidence linkage model.
- Extend the fallback path so different rejected highlight types can map to
  different caveated closing-language patterns instead of sharing one generic
  redirect.
