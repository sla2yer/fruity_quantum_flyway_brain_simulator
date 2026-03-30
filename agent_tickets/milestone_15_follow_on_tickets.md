# Milestone 15 Follow-On Tickets

This file is intentionally structured so it remains readable in Markdown and
parseable by `scripts/run_agent_tickets.py`.

Ticket format:
- Each ticket starts with `## <ticket-id> - <title>`
- Top-level metadata stays as `- Key: Value` lines directly under the ticket heading
- Ticket body uses `###` sections

## FW-M15-FOLLOW-001 - Rematerialize coupling assets for no-waves and other morphology-demotion ablations
- Status: open
- Priority: high
- Source: Milestone 15 readiness follow-on 2026-03-29
- Area: orchestration / ablations / coupling compatibility

### Problem
`FW-M15-008` now proves that a representative manifest-driven shuffle suite can
plan and execute deterministically, but the required `no_waves` ablation still
fails during local simulation. The current transform demotes affected roots to
`point_neuron`, while the inherited coupling components still require
`surface_patch_cloud` anchors. That leaves Milestone 15 unable to guarantee
that all required ablation families are actually runnable on the local shipped
asset path.

### Requested Change
Teach the relevant Milestone 15 ablation materialization path to either
regenerate or select coupling assets that match the post-ablation morphology
class and anchor-mode requirements. Keep the change within the orchestration
and asset-selection boundary when possible; do not silently mutate baseline
coupling semantics for intact runs.

The intended outcome is one deterministic manifest-driven suite path where the
required `no_waves` family can execute locally without hand-editing bundles or
CLI overrides.

### Acceptance Criteria
- The representative `no_waves` suite used by `make milestone15-readiness`
  completes its simulation stage without anchor-mode compatibility failures.
- The realized coupling artifact references for demoted roots are explicit and
  traceable from the suite execution state and packaged outputs.
- The fix preserves deterministic suite identity and deterministic work-item
  scheduling across repeated runs.
- Regression coverage is added so the same point-versus-surface coupling
  mismatch fails loudly in unit or readiness tests if it reappears.

### Verification
- `make test`
- `make milestone15-readiness`
- Confirm from
  `data/processed/milestone_15_verification/simulator_results/readiness/milestone_15/milestone_15_readiness.json`
  that `required_ablation_runtime` becomes `true`
- Confirm the recorded `no_waves_simulation_suite` command no longer reports an
  anchor-mode mismatch in its first failed work item

### Reproduction Notes
Before the fix, run `make milestone15-readiness` and inspect the recorded
`no_waves_simulation_suite` command under
`data/processed/milestone_15_verification/simulator_results/readiness/milestone_15/commands/`.
The first failed work item reports that hybrid coupling components still
require `surface_patch_cloud` anchors even after the ablation demotes the roots
to `point_neuron`.

## FW-M15-FOLLOW-002 - Bridge manifest-driven suite analysis onto a condition-complete experiment bundle set
- Status: open
- Priority: high
- Source: Milestone 15 readiness follow-on 2026-03-29
- Area: orchestration / analysis / bundle handoff

### Problem
`FW-M15-008` also proves that a representative full-stage manifest-driven suite
stalls at the analysis stage even when the simulation stage succeeds. The
current suite runner feeds `execute_experiment_comparison_workflow()` only the
direct outputs from one materialized suite cell, but the Milestone 12 analysis
workflow expects the richer condition-complete bundle coverage used by
experiment-level comparisons. That leaves a contract gap between Milestone 15
orchestration and the downstream analysis, validation, and dashboard stages.

### Requested Change
Make the suite analysis stage hand off a bundle set that satisfies the
Milestone 12 comparison contract, or explicitly extend the downstream workflow
to support the suite-owned contract with equally clear semantics. Keep the
boundary explicit so review tooling can still tell which comparisons are shared
baseline-versus-wave metrics versus wave-only diagnostics.

The intended outcome is one manifest-driven suite path that can carry seeded
simulation outputs through analysis, validation, and dashboard stages without
fixture-only assumptions.

### Acceptance Criteria
- The representative full-stage shuffle suite used by `make milestone15-readiness`
  reaches analysis without missing-condition coverage failures.
- The same suite can then package downstream analysis, validation, and
  dashboard references in a deterministic, reviewable way.
- The fix preserves deterministic suite scheduling and does not regress the
  packaged Milestone 12 comparison semantics already exercised elsewhere.
- Regression coverage is added so suite analysis cannot silently drift away from
  the required condition-coverage contract again.

### Verification
- `make test`
- `make milestone15-readiness`
- Confirm from
  `data/processed/milestone_15_verification/simulator_results/readiness/milestone_15/milestone_15_readiness.json`
  that `full_stage_manifest_suite` becomes `true`
- Confirm the recorded `shuffle_full_stage_suite` command no longer reports
  missing condition coverage for the generated suite bundles

### Reproduction Notes
Before the fix, run `make milestone15-readiness` and inspect the recorded
`shuffle_full_stage_suite` command under
`data/processed/milestone_15_verification/simulator_results/readiness/milestone_15/commands/`.
The first failed analysis work item reports missing condition coverage for the
generated seeded suite bundles.
