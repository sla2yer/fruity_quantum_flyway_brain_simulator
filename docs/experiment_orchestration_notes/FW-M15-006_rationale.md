# FW-M15-006 Rationale

## Design Choices

This ticket adds one library-owned suite rollup module,
`flywire_wave.experiment_suite_aggregation`, plus a thin CLI wrapper
`scripts/32_suite_aggregation.py`.

The core design choice is to make the packaged Milestone 15 suite inventory the
only discovery anchor for suite-level rollups.

- the workflow consumes `experiment_suite_package.json` or `result_index.json`
- it discovers experiment-analysis and validation outputs through the packaged
  stage-artifact inventory
- it does not rescan bundle directories or infer comparisons from folder names

That keeps Milestone 15 aggregation downstream of the existing package/index
layer from `FW-M15-005` instead of creating a second discovery mechanism.

Another deliberate choice is to keep the first suite rollup surface visibly
sectioned rather than collapsing everything into one mixed score table. The
summary JSON therefore has three top-level review sections:

- `shared_comparison_metrics`
- `wave_only_diagnostics`
- `validation_findings`

Each section carries raw evidence rows first and summary tables second. That
preserves the fairness boundary the earlier milestones already established:

- shared comparison metrics come from Milestone 12 experiment-analysis group
  rollups
- wave diagnostics come from Milestone 12 wave-only rollups
- validation findings come from Milestone 13 validation-ladder summaries and
  finding-row exports

The pairing semantics are also explicit instead of being hidden inside plotting
helpers.

- baseline-versus-wave pairing is inherited directly from the packaged
  experiment-analysis `group_id`, `group_kind`, and `comparison_semantics`
  fields
- intact-versus-ablated pairing is inherited directly from
  `suite_plan.comparison_pairings.suite_cell_pairings` with
  `pairing_kind='ablation_vs_base'`
- seed rollup validity is checked against the suite package’s own
  `simulation_lineage_cells`, so experiment-level rollups must declare the same
  realized seed set the suite index says was run

That last point matters because Milestone 15 should not silently re-average
seeded runs. The suite layer now treats seed aggregation as upstream evidence
that must match the packaged lineage exactly.

I also kept repeated-cell collapse explicit and inspectable. Raw paired rows are
never discarded. Summary tables are built on top of those rows with one declared
dimension slice:

- callers can keep all declared dimensions as the table key
- or they can request a subset of declared dimensions
- when multiple paired rows land in the same slice, the table records the
  source row count, source pairing ids, and deterministic summary statistics
  over the paired means

That gives reviewers one stable answer to “what was collapsed?” and “which
cells contributed to this row?”

## Testing Strategy

The regression coverage stays fixture-driven and targets the packaged-suite
boundary directly.

The new focused test module:

- resolves a real Milestone 15 suite plan with multiple dimensions, repeated
  seeds, and ablation variants
- materializes deterministic fixture analysis summaries and validation-ladder
  outputs for every review cell
- packages the suite through the real `experiment_suite_package` workflow
- runs the new aggregation API against the packaged inventory
- asserts deterministic raw rows, paired ablation deltas, fairness-boundary
  sectioning, and collapsed summary-table behavior
- forces a missing shared-rollup key and checks for a clear pairing failure
- forces incomplete seed coverage and checks for a clear seed-coverage failure

This intentionally tests the new rollup layer through the same packaged
inventory that later review tooling will use, rather than through an ad hoc
hand-built result-index stub.

## Simplifications

The first version stays conservative in a few places.

- The workflow writes JSON and CSV review exports, but it does not yet register
  those exports back into a new suite-package contract revision.
- Validation comparison rows summarize status changes and finding-count deltas;
  they do not yet attempt a fully matched validator-finding diff between base
  and ablation cells.
- Summary tables currently collapse paired rows only. Base-cell raw rows remain
  available for traceability, but they are not separately re-aggregated into a
  second table family.
- The workflow expects packaged analysis and validation artifacts to be present
  for every compared review cell. It fails closed on missing pair coverage
  instead of trying to infer partial comparisons.

These limits keep the first suite rollup honest and easy to audit while still
covering the Milestone 15 comparison use case.

## Future Expansion Points

The clearest follow-on paths are:

- register suite-owned aggregation exports into a dedicated package/report
  contract if later tickets need stronger discovery guarantees
- add richer validation comparison diffs keyed by validator and finding identity
- layer suite-owned plot generation on top of the new paired rows and summary
  tables
- add optional filters for ablation family, metric family, or validator family
  when reviewers want narrower exports
- extend summary-table collapse rules beyond deterministic mean statistics if
  Grant later wants stronger suite-level meta-analysis semantics
