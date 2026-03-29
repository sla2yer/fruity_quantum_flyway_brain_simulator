Work ticket FW-M13-006: Build the task-sanity validation suite for stable outputs, reproducible arm differences, and perturbation robustness.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 13 roadmap 2026-03-26

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 12 can already turn local result bundles into experiment-level comparisons, but Milestone 13 is not complete until those task-level outputs themselves become validated. There is still no canonical workflow that asks whether task outputs are stable across seeds, whether baseline-versus-wave differences are reproducible rather than anecdotal, or whether those differences survive modest perturbation and noise. Without a task-sanity suite, the repo can emit attractive comparison panels while still failing the basic question of whether the claimed effect is robust enough to trust.

Requested Change:
Implement the Milestone 13 task-sanity validators as reusable experiment-level workflows on top of the normalized validation plan and Milestone 12 analysis bundles. The suite should measure output stability, reproducibility of baseline-versus-wave differences, and robustness under declared perturbation or noise sweeps while preserving the fairness boundary between shared-comparison metrics and wave-only diagnostics. Make seed coverage, perturbation coverage, and effect-consistency reporting explicit so later reviewers can see whether a claimed task effect is stable, review-level, or blocking.

Acceptance Criteria:
- There is a canonical task-validation API or workflow that consumes Milestone 12 experiment-analysis outputs and computes deterministic task-sanity findings for stability, reproducibility, and perturbation robustness.
- The workflow supports seed aggregation, perturbation or noise sweeps, and explicit comparison of baseline versus wave or intact versus ablated arms where those pairings are declared by the validation plan.
- Validation outputs keep fairness-critical shared metrics visibly separate from wave-only diagnostics while still allowing both to coexist in one review artifact.
- Missing seed coverage, contradictory task outcomes, or incompatible analysis inventories fail clearly instead of silently degrading the validation result.
- Regression coverage includes at least one fixture experiment with multiple arms and seeds that asserts deterministic task-sanity summaries under both clean and perturbed conditions.
- A companion rationale note is added at `docs/validation_ladder_notes/FW-M13-006_rationale.md` and explicitly explains design choices, testing strategy, simplifications, and future expansion points.

Verification:
- `make test`
- A smoke-style fixture workflow that loads deterministic experiment-analysis outputs, runs the task-sanity suite, and asserts stable findings for seed consistency and perturbation robustness

Notes:
Assume `FW-M13-001` through `FW-M13-005` and the Milestone 12 analysis bundle workflow are already in place. The goal here is experiment-level confidence, not a new downstream decoder boundary. Do not attempt to create a git commit as part of this ticket.
