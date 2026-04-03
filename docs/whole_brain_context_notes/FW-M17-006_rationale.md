# FW-M17-006 Rationale

## Design choices

This ticket adds the first explicit Milestone 17 explanation layer on top of
the existing whole-brain packaging work instead of introducing a second graph
contract or pushing interpretation logic into the UI.

The core decisions were:

- add one explicit mixed-context overlay id,
  `bidirectional_context_graph`, so the packaged review surface can name
  upstream-only, downstream-only, and mixed whole-brain emphasis modes
  directly
- package overlay workflow metadata, metadata-facet group/filter catalogs,
  pathway explanation cards, interaction-flow records, and reviewer summary
  cards inside each packaged graph view so later UI and showcase layers do not
  have to reconstruct semantics from raw topology alone
- make metadata-facet filtering deterministic by recording concrete filter ids,
  matched roots, preserved active anchors, visible edge pairs, and module ids
  for each packaged facet value
- keep the active-versus-context boundary explicit inside every overlay,
  filter, and pathway explanation record rather than treating that boundary as
  a styling convention
- thread the same explanation-layer metadata through the dashboard whole-brain
  bridge so the dashboard package exposes one normalized surface for richer
  Milestone 17 review behavior

The pathway explanation mode intentionally starts from the active anchor and
walks toward the contextual target even for upstream biological relationships.
That makes the explanation easier to discuss while still recording the true
biological direction separately.

## Testing strategy

The regression coverage for this ticket focuses on deterministic packaged
behavior rather than browser-only interaction logic.

The new tests verify:

- the contract exposes the new bidirectional context overlay deterministically
- a bidirectional fixture query packages stable overlay workflows,
  cell-class and neuropil facet filters, reviewer summary cards, and
  active-to-context pathway explanation metadata
- the richer Milestone 17 packaged fixture exports the same explanation-layer
  metadata through `context_view_payload.json`, including deterministic
  interaction-flow ids
- the dashboard whole-brain bridge normalizes the same overlay, facet, and
  pathway explanation metadata into the circuit-pane model

The focused verification pass reruns:

- `tests/test_whole_brain_context_contract.py`
- `tests/test_whole_brain_context_query.py`
- `tests/test_whole_brain_context_planning.py`
- `tests/test_dashboard_scene_circuit.py`

## Simplifications

This first explanation layer stays deliberately local and metadata-driven.

Current simplifications:

- interaction flows are packaged as deterministic metadata records; they are
  not yet promoted into a new dashboard-global serialized state model
- metadata-facet filtering operates on packaged local metadata values rather
  than on a live graph database or an open-ended query language
- pathway explanation mode focuses on one active-to-context walkthrough style
  instead of shipping multiple competing explanation grammars in the first pass
- reviewer cards are concise captions and counts, not a full narrative authoring
  system

These tradeoffs keep the implementation inspectable and deterministic while
still making the context graph easier to trust and discuss.

## Future expansion

Likely follow-on work can extend this layer by:

- wiring the packaged interaction-flow ids into dashboard-local controls or
  showcase playback state when that interaction becomes review-critical
- adding richer explanation modes such as target-first upstream walkthroughs,
  comparative pathway cards, or curated downstream-module justifications
- exposing more facet dimensions when local metadata quality is high enough to
  support them honestly
- letting showcase mode script specific explanation cards or facet filters as
  narrative beats on top of the same packaged metadata surface
