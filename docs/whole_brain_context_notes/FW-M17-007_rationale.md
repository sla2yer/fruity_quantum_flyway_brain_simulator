# FW-M17-007 Rationale

## Design choices

This ticket keeps optional downstream readout modules inside the existing
Milestone 17 context package instead of turning them into a new simulator
layer, decoder stack, or showcase-only JSON convention.

The core decisions were:

- keep one canonical downstream-module record shape inside
  `whole_brain_context_session.v1` and extend that record with explicit
  simplification labels, lineage metadata, and handoff targets
- label each packaged module as optional, simplified, and context-oriented so
  the package does not overstate biological fidelity or imply a new fair
  readout claim
- trace each module back to active-subset anchors and the originating
  Milestone 17 query profile, with optional supporting pathway ids when a
  packaged pathway highlight overlaps the summarized roots
- treat dashboard and showcase handoff references as metadata-backed target
  records that point into the Milestone 17 preset library, rather than letting
  the showcase layer recompute context queries on its own
- add one explicit Milestone 16 showcase handoff link on the packaged
  `analysis_summary` preset so the cross-milestone transition feels like a
  continuation of review flow instead of an unrelated side branch

The practical boundary is unchanged: downstream modules summarize broader
context around the active subset, but they do not become new simulated neurons
or a stealth Milestone 18 expansion.

## Testing strategy

The regression coverage for this ticket focuses on deterministic packaging and
cross-package lineage rather than browser-only interaction details.

The new tests verify:

- the whole-brain query layer emits simplified downstream-module records with
  explicit summary labels and stable lineage back to active anchors
- whole-brain context contract serialization preserves the new downstream
  module metadata surface deterministically
- a packaged Milestone 16 showcase fixture exposes a stable
  `whole_brain_context_handoff` link from the `analysis_summary` preset
- a packaged Milestone 17 context fixture resolves that showcase link into
  stable handoff targets on the downstream-module records and on the
  `showcase_handoff` preset metadata

The focused verification pass reruns:

- `tests/test_whole_brain_context_query.py`
- `tests/test_whole_brain_context_contract.py`
- `tests/test_whole_brain_context_planning.py`

The full repo verification still ends with `make test`.

## Simplifications

This first downstream-module layer is intentionally conservative.

Current simplifications:

- module records summarize grouped downstream roots from the packaged local
  graph; they do not introduce new dynamics, readout equations, or learned
  decoding behavior
- supporting pathway lineage is opportunistic and local: it reuses packaged
  Milestone 17 pathway ids when available instead of inventing a second module
  justification catalog
- showcase handoff is currently attached to one stable preset,
  `analysis_summary`, rather than every possible story beat
- dashboard handoff stays session-level because Milestone 14 does not yet ship
  a richer narrative preset library comparable to the showcase package

These constraints keep the surface honest and make it easier to inspect the
package as metadata rather than mistaking it for a new scientific model.

## Future expansion

Likely follow-on work can extend this layer by:

- adding more curated downstream-module role ids when Grant wants additional
  summary families beyond the initial simplified readout/projection split
- threading downstream-module handoff state into dashboard or showcase UI
  affordances once those interactions are review-critical
- attaching richer module-specific evidence such as curated rationale text,
  facet rollups, or approved pathway justifications when that curation is ready
- promoting the current metadata-backed handoff targets into a broader review
  navigation surface if later milestones need more than preset-to-preset
  linking
