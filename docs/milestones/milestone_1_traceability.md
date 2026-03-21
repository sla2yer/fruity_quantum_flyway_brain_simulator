# Milestone 1 Traceability

This document maps the locked Milestone 1 scientific claim onto concrete software metrics, manifest controls, plots, and UI states. It is the traceability bridge between the brief, the machine-readable design lock, and the experiment manifest.

## Metric definitions

- `geometry_sensitive_shared_output_effect`: `(surface_intact - baseline_intact) - (surface_shuffled - baseline_shuffled)` applied to a shared readout
- `geometry_sensitive_null_direction_suppression_effect`: `geometry_sensitive_shared_output_effect` applied specifically to `null_direction_suppression_index`
- `null_direction_suppression_index`: shared output metric for preferred versus null-direction suppression
- `response_latency_to_peak_ms`: latency companion observable
- `direction_selectivity_index`: secondary shared output metric

## Claim-to-output mapping

| Claim or criterion | Concrete metric name(s) | Output artifact name(s) | Expected plot(s) | Expected UI state(s) | Manifest fields that control it |
|---|---|---|---|---|---|
| Distributed morphology-bound state exists in the surface model | `surface_state_patch_activation`, `surface_state_spread_extent` | `outputs/.../metrics/summary_metrics.json` | `outputs/.../plots/surface_state_snapshot.png` | `surface_vs_baseline_split_view` | `comparison_arms[].model_mode`, `comparison_arms[].morphology_condition`, `subset_name`, `circuit_name` |
| Geometry-sensitive shared-output effect is the core observable | `geometry_sensitive_shared_output_effect` | `outputs/.../metrics/summary_metrics.json`, `outputs/.../metrics/per_condition_summary.csv` | `outputs/.../plots/topology_ablation_comparison.png` | `milestone_decision_panel` | `primary_metric`, `success_criteria_ids`, `comparison_arms[].topology_condition`, `comparison_arms[].model_mode` |
| Primary observable is geometry-sensitive null-direction suppression | `geometry_sensitive_null_direction_suppression_effect`, `null_direction_suppression_index` | `outputs/.../metrics/summary_metrics.json` | `outputs/.../plots/null_direction_suppression_comparison.png` | `shared_output_trace_overlay` | `primary_metric`, `comparison_arms[].model_mode`, `comparison_arms[].topology_condition`, `stimulus_family`, `stimulus_name` |
| Latency is the main companion observable | `response_latency_to_peak_ms` | `outputs/.../metrics/summary_metrics.json`, `outputs/.../metrics/per_condition_summary.csv` | `outputs/.../plots/latency_shift_comparison.png` | `shared_output_trace_overlay` | `companion_metrics`, `stimulus_family`, `stimulus_name`, `random_seed`, `seed_sweep` |
| Intact versus shuffled topology ablation must be visible | `geometry_sensitive_shared_output_effect`, `geometry_sensitive_null_direction_suppression_effect` | `outputs/.../metrics/per_condition_summary.csv` | `outputs/.../plots/topology_ablation_comparison.png` | `surface_vs_baseline_split_view`, `milestone_decision_panel` | `comparison_arms[].topology_condition`, `comparison_arms[].morphology_condition` |
| `P0` versus `P1` baseline challenge must be explicit | `geometry_sensitive_shared_output_effect`, `baseline_gap_surface_minus_p1` | `outputs/.../metrics/per_condition_summary.csv` | `outputs/.../plots/baseline_challenge_comparison.png` | `milestone_decision_panel` | `comparison_arms[].baseline_family`, `success_criteria_ids` |
| Demo must show the same circuit and stimulus under matched conditions | `null_direction_suppression_index`, `response_latency_to_peak_ms` | `outputs/.../metrics/summary_metrics.json`, `outputs/.../ui/stimulus_overview.json` | `outputs/.../plots/shared_output_trace_overlay.png` | `stimulus_overview`, `surface_vs_baseline_split_view`, `shared_output_trace_overlay` | `subset_name`, `circuit_name`, `stimulus_family`, `stimulus_name`, `comparison_arms` |
| Stability across seeds and modest parameter changes is required | `geometry_sensitive_shared_output_effect_across_seeds`, `response_latency_to_peak_ms` | `outputs/.../metrics/per_condition_summary.csv` | `outputs/.../plots/stability_across_seeds.png` | `milestone_decision_panel` | `random_seed`, `seed_sweep`, `notes`, `tags` |

## Mandatory demo outputs

The following outputs are mandatory for the Milestone 1 one-minute demo and are encoded in the example manifest:

- `stimulus_overview`
- `surface_vs_baseline_split_view`
- `shared_output_trace_overlay`
- `null_direction_suppression_comparison`
- `latency_shift_comparison`
- `topology_ablation_comparison`
- `baseline_challenge_comparison`
- `milestone_decision_panel`

## Output interpretation notes

- A wave movie alone does not satisfy the claim. It only supports the weakest level of evidence.
- The primary claim clears the Milestone 1 bar only when the shared-output change is geometry-sensitive and challengeable by shuffling.
- `P0` and `P1` outputs must both be represented in the metric bundle so survival against the stronger reduced baseline is auditable.
