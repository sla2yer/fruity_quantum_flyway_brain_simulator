# FW-M16-003 Rationale

## Design Choices

This ticket adds a richer Milestone 16 rehearsal layer without widening the
Milestone 14 or Milestone 15 readiness fixtures.

The main design decision is to keep the compact readiness fixtures as upstream
evidence generators and package the richer story surface downstream in the
showcase layer:

- Milestone 14 still owns the fast packaged dashboard-session fixture
- Milestone 15 still owns the fast packaged suite-review fixture
- Milestone 16 now owns the richer `milestone16_rehearsal` fixture mode and
  the curated narrative preset library that composes those earlier bundles

The narrative preset library stays inside the packaged
`narrative_preset_catalog.json` instead of living in operator notes or
browser-only state. The catalog now records:

- stable story-arc preset ids for the major beats
- richer preset-local rehearsal metadata such as camera anchors, subset focus,
  propagation view context, comparison pairing, highlight state, and analysis
  landing context
- explicit highlight metadata with the nominated phenomenon id, primary
  analysis evidence, supporting suite and validation references, and a
  declared fallback path

That keeps the scientific boundary explicit. The showcase package can present a
Grant-approved effect, but it cites shipped analysis, suite, and validation
artifacts rather than pretending the presentation layer derived the claim.

I also added one thin CLI wrapper, `scripts/35_showcase_session.py`, plus the
`make showcase-session` entrypoint so later runtime, export, and readiness
tickets have one canonical local packaging path.

## Testing Strategy

Coverage stays focused on the regression risks introduced by the new curation
layer.

`tests/test_showcase_session_planning.py` now includes a representative
rehearsal-flow test that:

- packages a richer showcase fixture from the existing packaged dashboard and
  suite fixtures
- forces one explicit approved highlight id so the test can assert stable
  highlight metadata
- verifies the stable story-arc preset id map and deterministic preset
  discovery order
- verifies the packaged highlight metadata includes suite and validation
  support references plus a fallback path
- verifies the packaged highlight step keeps stable evidence references

The older showcase-planning tests still run unchanged, which checks that the
new rehearsal metadata did not regress the earlier Milestone 16 planner
surface.

## Simplifications

This ticket still stops short of a full showcase runtime.

- The preset library is metadata-rich, but it does not yet drive a live step
  sequencer.
- Camera anchors and rehearsal metadata are declared in the packaged preset
  state, not yet rendered by a dedicated player.
- The approved highlight metadata points to shipped evidence references, but
  it does not create a new review workflow beyond the existing validation
  handoff.
- The CLI packages a showcase session; it does not yet open, play, or export
  the story interactively.

Those constraints keep the scope aligned with the ticket: deterministic
rehearsal curation, not full demo runtime work.

## Future Expansion Points

Likely follow-on work:

- load the richer preset library directly into the later Milestone 16 player
- teach export code to use the stored camera anchors and analysis landing
  metadata rather than recomputing them
- validate highlight-support references more deeply against specific suite
  sections or validation findings once later tickets know the final rendered
  review surfaces
- add a readiness-style Milestone 16 rehearsal audit once the scripted player
  and export workflows exist
