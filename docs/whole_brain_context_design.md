# Whole-Brain Context Design

## Purpose

Milestone 17 needs one library-owned contract before whole-brain context work
spreads across ad hoc graph exports, dashboard-only JSON patches, and showcase
presets. The versioned software contract is
`whole_brain_context_session.v1`, implemented in
`flywire_wave.whole_brain_context_contract`.

The contract composes with earlier milestones instead of rewriting them:

- subset-selection artifacts still own the active root roster and the rules
  that produced it
- the canonical local synapse registry from `coupling_bundle.v1` still owns the
  local connectivity input
- `dashboard_session.v1` still owns replay state, pane state, and the compact
  active-subset review surface
- `showcase_session.v1` still owns narrative rehearsal state, scripted
  presentation mechanics, and curated story beats

Milestone 17 adds one downstream context packaging layer that freezes the
vocabulary for larger-brain graph views around that existing active surface.

## Readiness Vs Review

Milestone 14 and Milestone 16 already ship compact dashboard and showcase
fixtures on purpose. Those fixtures are the minimum local readiness gate, not
the richer review surface for whole-brain context behavior.

Milestone 17 therefore layers a downstream review fixture on top of those
existing packages instead of widening them:

- compact dashboard or showcase packages remain the fast gate
- the richer context package is built in fixture mode
  `milestone17_whole_brain_review`
- `context_query_catalog.json` now owns the deterministic review-preset
  library for whole-brain context inspection
- the packaged context bundle keeps explicit links back to dashboard and
  showcase metadata so reviewers can compare the compact gate against the
  richer whole-brain view without rebuilding ad hoc exports

## Default Delivery Model

The default local delivery model is `packaged_local_context_bundle`.

That means one context session is packaged under a deterministic local bundle
directory with:

- `whole_brain_context_session.json` as the authoritative discovery anchor
- `context_view_payload.json` as the reserved packaged graph-view payload
- `context_query_catalog.json` as the reserved packaged query-taxonomy export
- `context_view_state.json` as the exportable serialized view state

The goal is the same offline-review property used by Milestones 14 and 16: a
reviewer should be able to inspect the packaged context session from local disk
without depending on a backend service.

The richer review fixture packages both:

- one primary `query_execution` for the default context-session landing state
- one deterministic preset library with stable graph-payload references for
  richer review workflows

## Query Taxonomy

The v1 query profile ids are fixed:

1. `active_subset_shell`
2. `upstream_connectivity_context`
3. `downstream_connectivity_context`
4. `bidirectional_connectivity_context`
5. `pathway_highlight_review`
6. `downstream_module_review`

The default query profile is `bidirectional_connectivity_context`.

The intended split is:

- shell and directional profiles are deterministic Jack-owned packaging modes
- highlight and downstream-module review profiles are still deterministic
  packages, but they surface Grant-owned scientific curation decisions more
  directly

## Review Preset Library

The first Milestone 17 review preset ids are fixed:

1. `overview_context`
2. `upstream_halo`
3. `downstream_halo`
4. `pathway_focus`
5. `dashboard_handoff`
6. `showcase_handoff`

These presets sit on top of the lower-level query profiles. They package
stable review states and stable references into `context_view_payload.json`
instead of forcing later UI or showcase work to invent one-off local graph
entry points.

## Active Vs Context Boundary

The core Milestone 17 truthfulness rule is that active-versus-context status is
contract state, not styling.

The stable node-role ids are:

- `active_selected`
- `context_only`
- `active_pathway_highlight`
- `context_pathway_highlight`

Interpretation rules:

- active roles always trace back to the active subset-selection artifacts
- context roles remain outside the active subset even when they are closely
  connected or visually emphasized
- pathway-highlight roles are still active-or-context first and highlight
  second; emphasis never silently changes boundary status

Optional downstream module records are separate objects with stable module-role
ids. They are allowed simplifications, not disguised neuron records.

## Layers And Overlays

The stable context-layer ids are:

- `active_subset`
- `upstream_context`
- `downstream_context`
- `pathway_highlight`
- `downstream_module`

The stable overlay ids are:

- `active_boundary`
- `upstream_graph`
- `downstream_graph`
- `pathway_highlight`
- `downstream_module`
- `metadata_facet_badges`

`active_boundary` is the non-negotiable baseline overlay. Later Milestone 17
UI work may add polish, but it may not remove or blur the active/context split.

## Graph Budgets

The contract owns reduction-profile ids and their default budgets:

- `local_shell_compact`
- `balanced_neighborhood`
- `pathway_focus`
- `downstream_module_collapsed`

These budgets are delivery constraints, not scientific truth claims. They exist
to keep Milestone 17 packages scalable and deterministic.

The preserved rule is:

- active selected nodes must survive reduction
- context may be reduced, collapsed, or summarized
- downstream modules must stay visibly labeled as summaries

## Ownership Boundary

The boundary is explicit:

- Jack owns deterministic context packaging, query-profile identity,
  graph-budget rules, scalable UI semantics, linked interaction mechanics, and
  the contract-level truthfulness labels that separate active state from
  contextual scaffolding.
- Grant owns which broader relationships are scientifically worth surfacing,
  which pathway highlights are acceptable to show, and whether optional
  downstream modules are scientifically meaningful enough to package at all.

The practical rule is:

- Jack decides how the larger context is packaged and navigated.
- Grant decides which broader pathway story is scientifically worth elevating.

## Truthfulness Boundary

Milestone 17 is intentionally descriptive before it is explanatory.

The contract therefore freezes these boundaries:

- upstream and downstream graph overlays show deterministic local context, not
  automatic importance rankings
- pathway highlights are curated interpretive emphasis and must stay labeled as
  such
- downstream modules are summaries and may not be restated as fair simulator
  readouts or one-to-one neuron observations
- dashboard and showcase packages remain bridge artifacts; Milestone 17 may
  link to them or synchronize with them, but it may not mutate their earlier
  contracts

## Preserved Invariants

Later Milestone 17 tickets should preserve these invariants unless
`whole_brain_context_session.v1` changes:

- query-profile ids, node-role ids, edge-role ids, context-layer ids, overlay
  ids, reduction-profile ids, metadata-facet ids, downstream-module-role ids,
  and discovery-hook ids stay contract-owned
- the active subset boundary continues to flow from subset-selection artifacts
  instead of UI-local tags
- local connectivity discovery continues to resolve through the canonical local
  synapse registry rather than new ad hoc graph snapshots
- dashboard and showcase packages remain downstream bridges instead of hidden
  dependencies or competing sources of truth
- any new scientific curation logic stays visibly separate from deterministic
  packaging mechanics

If later work needs different taxonomy ids, different active/context meaning,
or a different ownership boundary, that is a new contract version rather than a
silent edit to `whole_brain_context_session.v1`.
