# FW-M15-001 Rationale

## Design Choices

This ticket adds one library-owned Milestone 15 contract module instead of
letting suite vocabulary drift across shell scripts, ad hoc result folders, or
later reporting code. The module owns:

- the canonical experiment-dimension IDs
- the first required ablation-family IDs
- suite-cell lineage kinds
- work-item status semantics
- artifact-role discovery hooks for upstream manifests and downstream bundles
- suite-level reproducibility hooks
- normalization of representative suite metadata

The contract deliberately composes with the existing Milestone 9 through
Milestone 14 layers instead of re-litigating them. The suite layer references
`simulation_plan.v1`, `simulator_result_bundle.v1`,
`experiment_analysis_bundle.v1`, `validation_ladder.v1`, and
`dashboard_session.v1`; it does not replace those contracts.

The ownership boundary is also encoded directly in the contract metadata:

- Jack owns the orchestration surface and deterministic mechanics
- Grant owns which ablation families and parameterizations are scientifically
  meaningful

That keeps the suite layer honest. The software contract defines how ablations
are named and tracked, not which scientific claims they prove.

## Why The Ticket Stops Before Full Suite Packaging

Milestone 15 still has later tickets for planning, execution, packaging,
aggregation, and reporting. This ticket therefore freezes vocabulary and
metadata hooks first, but it does not invent a premature suite-bundle layout
that would overlap with `FW-M15-005`.

The design-note language is intentional:

- suite metadata is already the discovery anchor
- upstream bundle paths remain owned by earlier milestone contracts
- later suite packaging must reuse the artifact roles and lineage semantics
  defined here

That gives the rest of the milestone one stable vocabulary without collapsing
several later tickets into this first contract ticket.

## Testing Strategy

The regression coverage stays focused on the contract surface introduced here:

- deterministic normalization and JSON serialization of the Milestone 15 suite
  contract metadata
- stable discovery of canonical dimension IDs and ablation-family IDs
- normalization of representative suite metadata with reordered inputs and
  humanized IDs
- deterministic suite metadata serialization plus discovery of lineage-linked
  cells, work items, and artifact references

This is narrow by design. The ticket is meant to lock vocabulary and metadata
semantics first, not to pretend the full orchestration runner already exists.

## Simplifications

The first version intentionally does not implement:

- suite-manifest parsing or expansion rules
- batch execution or resume logic
- ablation transform realizations
- suite-owned output-root packaging and result indexing
- aggregation, tables, plots, or review-report generation logic

It also uses one minimal suite metadata shape:

- upstream references
- normalized suite cells
- stage-level work items
- downstream artifact references

That is enough to freeze the vocabulary Jack and Grant need to share before the
later workflow tickets land.

## Future Expansion Points

The clearest follow-on paths are:

- `FW-M15-002`: resolve suite manifests and sweep rules into normalized plans
- `FW-M15-003`: add deterministic work scheduling and persisted execution state
- `FW-M15-004`: realize each ablation family as deterministic transforms
- `FW-M15-005`: package suite outputs and result indexes under a suite-owned
  root
- `FW-M15-006` and `FW-M15-007`: add rollups, tables, plots, and review
  surfaces on top of the package/index layer

Those tickets should keep using the IDs, lineage semantics, work-item
statuses, and artifact roles frozen here unless the suite contract version
changes.
