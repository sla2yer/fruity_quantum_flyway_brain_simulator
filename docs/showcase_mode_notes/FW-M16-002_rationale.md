# FW-M16-002 Rationale

## Design Choices

This ticket keeps Milestone 16 showcase assembly library-owned in
`flywire_wave.showcase_session_planning` instead of letting runtime, export,
or rehearsal code each rediscover dashboard, analysis, validation, and suite
artifacts independently.

The planner now resolves one normalized showcase plan from any of the intended
entry modes:

- manifest-driven resolution
- experiment-id resolution
- packaged dashboard-session resolution
- suite-package resolution, including dashboard-stage discovery from suite
  inventories
- explicit artifact resolution, including suite rollup artifacts rather than
  only dashboard, analysis, and validation paths

That normalization records the seven-step narrative order, saved presets,
operator defaults, comparison-arm pairing, highlight selection, closing
analysis assets, and deterministic output locations before anything is written
to disk. Packaging then writes the `showcase_session.v1` bundle once, so later
runtime or export code can consume showcase-owned files rather than reparsing
raw repo directories.

I also tightened two small contract edges while doing this work:

- showcase contract metadata is parsed before planning, so callers get the same
  normalization and validation behavior as the rest of the contract surfaces
- showcase metadata now rejects a default export target that is not enabled,
  which turns a confusing downstream mismatch into one clear planner error

## Testing Strategy

`tests/test_showcase_session_planning.py` uses the existing Milestone 14 and
Milestone 15 fixture builders instead of synthetic one-off JSON.

The focused coverage verifies:

- deterministic showcase planning and packaging from one packaged dashboard
  session plus one packaged suite review surface
- suite-package source mode discovering a packaged dashboard session through
  the experiment-suite stage inventory
- explicit artifact mode preserving suite rollup evidence and honoring a
  highlight override when validation review approves it
- clear failures for unsupported preset overlays and missing highlight-review
  evidence

That gives the ticket regression coverage on the planner behaviors that are
most likely to drift as later showcase runtime work lands.

## Simplifications

This ticket still stops at planning and packaging.

- It does not implement the Milestone 16 step sequencer or rehearsal controls.
- It does not render still images or replay media.
- It keeps suite-package discovery lightweight by reusing existing packaged
  inventory helpers instead of inventing a second suite catalog.
- It treats explicit suite artifacts as evidence inputs, not as a replacement
  for the Milestone 15 suite review workflow.

## Future Expansion Points

Likely follow-on work:

- load packaged showcase sessions into a runtime or rehearsal controller
- persist mid-rehearsal operator state transitions back into showcase-owned
  state files
- generate deterministic still, clip, and review-manifest exports from the
  packaged showcase export manifest
- tighten highlight-evidence compatibility checks once later Milestone 16 work
  knows exactly which analysis payload slices are rendered live
