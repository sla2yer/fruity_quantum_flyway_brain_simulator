# Experiment Analysis Bundle Design

## Purpose

Milestone 12 needs one experiment-level packaging layer so task summaries,
null-test tables, heatmap-like matrices, UI payloads, and offline review
artifacts remain discoverable without reparsing raw simulator bundle
directories. The versioned software contract is
`experiment_analysis_bundle.v1`, implemented in
`flywire_wave.experiment_analysis_contract`.

This bundle does not replace `simulator_result_bundle.v1`. It sits above the
per-run result contract and packages experiment-level analysis outputs that are
computed from a normalized Milestone 12 readout-analysis plan plus the local
bundle set discovered for one experiment.

## Canonical Layout

The library-owned default layout is:

- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/experiment_analysis_bundle.json`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/experiment_comparison_summary.json`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/task_summary_rows.json`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/null_test_table.json`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/comparison_matrices.json`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/visualization_catalog.json`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/analysis_ui_payload.json`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/report/index.html`
- `data/processed/simulator_results/analysis/<experiment_id>/<analysis_spec_hash>/report/summary.json`

`analysis_spec_hash` is the stable replay key for the experiment-level package.
It is derived from the normalized Milestone 12 analysis plan semantics rather
than from user-facing output target paths.

## Packaged Exports

`experiment_analysis_bundle.v1` freezes these first exports:

- `experiment_comparison_summary.json`: the full experiment-level comparison
  summary emitted by the Milestone 12 workflow
- `task_summary_rows.json`: stable requested-metric task rows and score-family
  exports
- `null_test_table.json`: flattened null-test rows plus hierarchical null-test
  results
- `comparison_matrices.json`: heatmap-like matrix exports for shared/task
  comparison rollups and wave-diagnostic rollups
- `visualization_catalog.json`: report references plus packaged phase-map
  references for later UI work
- `analysis_ui_payload.json`: one UI-facing payload with explicit
  `task_summary_cards`, `comparison_cards`, and `analysis_visualizations`
  sections

The UI payload may include both fairness-critical shared-comparison content and
wave-only diagnostic references, but those scopes must stay visibly separated.

## Discovery And Invariants

The metadata file remains the discovery anchor for every packaged artifact.
Later code should resolve artifact paths through
`flywire_wave.experiment_analysis_contract` helpers, not by guessing file
names.

Milestone 12 packaging must preserve these invariants:

- `readout_analysis.v1` remains the source of metric IDs, null-test IDs, and
  experiment-output IDs
- `simulator_result_bundle.v1` remains the upstream per-run comparison surface
- experiment-level packaging may add metadata and exports, but it may not
  mutate the per-run bundle contract
- UI-facing payloads and visualization catalogs must expose stable references
  to packaged summaries and review artifacts instead of requiring directory
  globbing
- offline review must be possible from packaged local artifacts alone

## Local Workflows

- `scripts/20_experiment_comparison_analysis.py` computes the experiment-level
  Milestone 12 summary, writes the canonical packaged bundle, and refreshes the
  default offline report
- `scripts/21_visualize_experiment_analysis.py` regenerates a deterministic
  static HTML report from an existing packaged analysis bundle without touching
  raw simulator bundle directories
- `scripts/22_milestone12_readiness.py` is the shipped integration audit for
  this layer: it materializes a deterministic local fixture, runs the shipped
  `scripts/20_experiment_comparison_analysis.py` and
  `scripts/21_visualize_experiment_analysis.py` commands, audits the packaged
  exports plus UI-facing payload discovery, and writes
  `milestone_12_readiness.md` / `milestone_12_readiness.json` under
  `config.paths.processed_simulator_results_dir/readiness/milestone_12/`
- `make milestone12-readiness` is the repo entrypoint for that readiness pass
- the readiness-generated visualization under
  `config.paths.processed_simulator_results_dir/readiness/milestone_12/visualization/index.html`
  is fully static, so no local server is required

If a later ticket needs different packaged artifact identities, different
matrix semantics, or a different UI payload meaning, that is a new contract
version rather than a silent edit to `experiment_analysis_bundle.v1`.
