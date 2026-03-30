# FW-M17-004 Rationale

## Design choices

This ticket adds the first review-oriented whole-brain fixture layer on top of
the existing Milestone 17 context-session package instead of widening the
upstream dashboard or showcase readiness fixtures.

The core decisions were:

- keep the compact dashboard and showcase packages as the minimum fast gate
  rather than turning them into larger whole-brain stress fixtures
- package the richer review path under one explicit fixture mode,
  `milestone17_whole_brain_review`
- add a deterministic query-preset library inside
  `context_query_catalog.json` instead of relying on ad hoc reviewer memory or
  one-off local JSON edits
- give each preset stable references back into `context_view_payload.json` so
  later UI, dashboard-handoff, and showcase-handoff work can reuse one
  reproducible local package

The first preset library is intentionally small and review-shaped:

- `overview_context`
- `upstream_halo`
- `downstream_halo`
- `pathway_focus`
- `dashboard_handoff`
- `showcase_handoff`

Those presets sit above the lower-level query profiles. Query profiles still
own the graph-expansion semantics; presets now own the reviewer-facing entry
points.

## Testing strategy

The regression coverage for this ticket focuses on one richer local fixture
workflow rather than only contract-unit behavior.

The new integration-style test:

- packages a showcase-linked whole-brain review fixture with a deterministic
  local synapse registry and local node metadata registry
- enumerates the packaged preset library through the planning helper and the
  serialized query catalog
- checks stable graph-payload references for overview and pathway-focused
  presets
- proves the packaged payload exercises context-only nodes, directional
  overlays, and at least one pathway-focused review case
- verifies dashboard and showcase handoff presets keep stable metadata
  references

The existing whole-brain contract, query, and planning tests were also rerun to
make sure the richer review layer stays compatible with FW-M17-001 through
FW-M17-003.

## Simplifications

The first richer review fixture is still deliberately local and conservative.

Current simplifications:

- preset payloads reuse deterministic local query execution instead of adding a
  separate cache, database, or server-backed preset service
- preset references point into packaged JSON payload sections rather than
  defining a second versioned graph-export contract
- handoff presets currently emphasize stable dashboard/showcase bridge points,
  not full two-way synchronization with those upstream packages
- the richer review workflow ships one curated local metadata fixture for
  testing instead of claiming scientific completeness for the whole female
  brain

These are deliberate. The goal of this ticket is a reproducible review target,
not a final interactive graph product.

## Future expansion

Likely follow-on work can build on this layer by:

- adding preset-specific reduction overrides or targeted pathway endpoints for
  narrower review questions
- exposing the preset library through a dedicated CLI or UI entry point
- attaching richer downstream-module payloads and handoff annotations when the
  scientific story is ready
- promoting the richer review fixture into later showcase and dashboard export
  flows without changing the compact readiness gate
