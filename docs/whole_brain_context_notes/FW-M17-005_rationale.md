# FW-M17-005 Rationale

## Design choices

This ticket keeps the Milestone 17 dashboard extension inside the existing
packaged static-app workflow instead of introducing a new service or a second
dashboard-specific graph contract.

The core decisions were:

- keep `dashboard_session.v1` as the canonical launch surface and treat the
  Milestone 17 package as an optional linked artifact set for the circuit pane
- add explicit dashboard-side artifact hooks for the packaged
  `whole_brain_context_session.v1` metadata, payload, query catalog, and view
  state so session hashing and discovery stay honest
- normalize the richer Milestone 17 payload into one dashboard-owned
  `whole_brain_context` bridge model inside the circuit pane rather than making
  the browser reconstruct graph semantics from raw packaged JSON
- preserve the existing linked state boundary by allowing context-only nodes to
  participate in hover-driven inspection while keeping selection enabled only
  for active subset roots
- render one overview representation plus one focused representation from the
  packaged preset library and degrade oversized views to summary-only cards
  instead of pretending a full graph rendered successfully

The dashboard bridge intentionally collapses duplicate highlight/base node
records from the packaged context payload into one display node per root. That
keeps pathway emphasis visible without drawing the same biological root twice.

## Testing strategy

The regression coverage for this ticket focuses on the first end-to-end local
workflow plus explicit failure handling.

The new tests verify:

- the dashboard contract now advertises whole-brain-context artifact hooks for
  the circuit pane
- a fixture whole-brain context package can be linked into a dashboard session
  plan and changes the dashboard session spec hash
- the packaged dashboard bootstrap exposes one overview and one focused
  whole-brain representation with explicit active, context-only, and
  pathway-highlight styling state
- linked inspection semantics stay honest: active nodes remain selectable while
  context-only nodes expose hover metadata without fabricating downstream
  morphology or time-series selection support
- oversized overview payloads degrade to summary-only mode and missing packaged
  payload files surface as unavailable context instead of crashing or silently
  drawing partial graphs

The existing dashboard contract, dashboard scene/circuit, and whole-brain
context planning tests were also rerun as part of the local verification pass.

## Simplifications

The first dashboard bridge is intentionally conservative.

Current simplifications:

- the dashboard does not expose the full Milestone 17 preset library as a new
  global serialized state model; representation switching is app-local UI state
- whole-brain overlay switching still relies on the packaged preset outputs and
  node styling metadata rather than a new dashboard-wide overlay taxonomy
- context-only nodes are hover-inspectable but not selectable, because the
  existing morphology and time-series panes still own active-subset simulator
  state only
- oversized views currently degrade to summary cards rather than introducing a
  second layout engine, virtualized graph canvas, or server-backed paging layer

These are deliberate tradeoffs. The goal here is one truthful, reviewable
Milestone 17 dashboard workflow, not a graph platform rewrite.

## Future expansion

Likely follow-on work can extend this layer by:

- promoting whole-brain representation choice into exported dashboard or
  showcase replay state when that interaction becomes review-critical
- exposing more of the packaged preset catalog, query-family metadata, and
  linked showcase handoff inside the circuit pane
- adding richer overlay and metadata-facet explanation controls on top of the
  packaged Milestone 17 payloads
- replacing summary-only degradation with a larger-graph renderer if later
  milestones need more scale than the current static SVG budget allows
