Work ticket FW-M15-006: Build suite-level aggregation, comparison tables, and ablation-aware metric rollups.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 15 roadmap 2026-03-29

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 12 already packages experiment-level summaries and Milestone 13 already packages validation findings, but Milestone 15 is specifically about comparing whole suites and ablations rather than inspecting one experiment at a time. There is still no canonical suite-level workflow that can aggregate across seeds, collapse repeated cells deterministically, line up baseline versus wave or intact versus ablated comparisons, and produce one comparison-ready table surface keyed by the dimensions that matter. Without that rollup layer, result indexing alone will not make the outcomes easy to compare, and every reviewer will end up building bespoke notebooks to answer routine questions about whether an ablation changed the shared metrics, wave diagnostics, or validation status.

Requested Change:
Implement the suite-level aggregation workflow for Milestone 15. The workflow should consume the packaged suite index together with existing experiment-analysis and validation outputs, compute deterministic comparison rows and summary tables across dimensions and ablations, and keep fairness boundaries visible by distinguishing shared-comparison metrics, wave-only diagnostics, and validation findings even when they appear in the same review surface. It should also make seed rollup semantics explicit so repeated runs contribute consistently rather than through implicit averaging hidden inside a plotting helper.

Acceptance Criteria:
- There is one canonical API that consumes a packaged Milestone 15 suite inventory and emits deterministic suite-level comparison rows or tables across declared dimensions and ablation families.
- The rollup semantics for seed aggregation, missing data, baseline-versus-wave pairing, and intact-versus-ablated pairing are explicit and testable.
- Shared-comparison metrics, wave-only diagnostics, and validation findings remain visibly separated in the aggregated outputs rather than being merged into one unlabeled score column.
- The workflow fails clearly when required comparison pairings are missing or when incomplete seed coverage would make a declared comparison misleading.
- Regression coverage includes at least one fixture suite with multiple dimensions, repeated seeds, and ablation variants that asserts deterministic comparison rows plus clear failure handling for incomplete coverage.
- A companion rationale note is added at `docs/experiment_orchestration_notes/FW-M15-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A focused integration-style test that loads a representative packaged suite inventory, computes suite-level rollups, and asserts deterministic comparison rows plus explicit fairness-boundary labeling

Notes:
Assume `FW-M15-001` through `FW-M15-005` and the Milestone 12 plus Milestone 13 packaging layers are already in place. Keep the first aggregation layer honest and inspectable; reviewers should be able to trace any reported suite-level delta back to packaged experiment-level evidence. Do not attempt to create a git commit as part of this ticket.
