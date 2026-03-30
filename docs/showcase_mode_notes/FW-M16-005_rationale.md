# FW-M16-005 Rationale

## Design Choices

This ticket adds a presentation-polish layer without changing the ownership
boundary established by `showcase_session.v1` and `dashboard_session.v1`.
The implementation keeps the richer choreography in showcase-owned preset
metadata instead of duplicating dashboard logic or inventing a second linked
state model.

The first four narrative presets now carry structured rehearsal metadata for:

- deterministic camera anchors and transitions
- annotation placement and reveal timing
- pane-link metadata that ties scene choice, input framing, subset emphasis,
  and propagation replay together
- emphasis state that names the relevant roots, overlays, and linked panes
- showcase UI-state rules, including a mode-specific escape hatch back to the
  packaged Milestone 14 dashboard shell

The player resolves that metadata into explicit runtime state fields such as
`camera_choreography`, `annotation_layout`, `narrative_annotations`,
`presentation_links`, `emphasis_state`, and `showcase_ui_state`. That makes
the choreography traceable in serialized state and available to later UI or
export work without forcing that code to parse ad hoc nested blobs.

The subset beat now prefers the dashboard’s `selected_subset_highlight`
overlay, and the propagation beat now prefers the shared-readout overlay ahead
of the wave-only overlay. That keeps the early story beats aligned with the
roadmap language: scene, fly-view/input, subset, and propagation should feel
linked before the later fair-comparison and approved-highlight acts.

## Testing Strategy

The regression coverage is split across planning and runtime:

- `tests/test_showcase_session_planning.py` now asserts deterministic early-beat
  choreography metadata, scene/input linkage metadata, subset-emphasis overlay
  state, propagation timing hints, and packaged dashboard escape-hatch paths.
- `tests/test_showcase_player.py` now asserts that the player resolves that
  metadata into runtime state, including annotation placements, camera anchors,
  emphasis overlays, and runtime-mode-specific showcase UI-state variants.

This keeps one test focused on preset packaging and one focused on preset
application, which matches the architecture of the feature.

## Simplifications

This version does not introduce a new standalone showcase HTML shell. The
packaged showcase still rides on the existing dashboard session plus showcase
state, and the “escape hatch” is represented as deterministic metadata that
points back to the richer dashboard surface.

Camera choreography is metadata-driven rather than a real browser camera
engine. The repo now knows what anchor, transition, timing, and annotation
placement should apply for the first four beats, but a later rendering layer
still needs to animate that visually.

UI-state rules are expressed as showcase control groups and runtime-mode
variants, not direct DOM mutations. That keeps the contract at the right
abstraction level for now and avoids coupling Milestone 16 state too tightly to
one specific dashboard-shell implementation.

## Future Expansion

- Add a dedicated showcase presentation shell or dashboard-shell integration
  that consumes `showcase_ui_state` and `camera_choreography` directly.
- Extend the same choreography model to the comparison, approved-highlight, and
  summary-analysis beats.
- Add deterministic export helpers that render annotation placements and camera
  timing into stills or frame sequences.
- If later work needs stricter taxonomy for control groups, placements, or
  transition kinds, promote those identifiers into the showcase contract rather
  than leaving them as planner-owned conventions.
