Work ticket FW-M5-004: Add derived geometry descriptors and simplification QA with documented error budgets.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: medium
Source: Milestone 5 roadmap 2026-03-21

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
The repo currently has no quantitative answer to a basic Milestone 5 question: did simplification and patchification preserve the geometry features that matter for later wave propagation experiments? Without descriptor sidecars and QA thresholds, the pipeline can produce smaller assets but cannot tell us whether they are still faithful enough for downstream numerical work.

Requested Change:
Add a descriptor and QA stage that computes wave-relevant geometry summaries for raw, simplified, and coarse representations, then compares them against configurable error budgets. Capture both the implemented metrics and the reasoning behind them in a short markdown design note so later milestones have a documented baseline for what counts as an acceptable morphology approximation.

Acceptance Criteria:
- The processed bundle includes a descriptor sidecar with geometry summaries such as counts, component structure, size/extent metrics, and coarse-representation occupancy metrics, plus skeleton summaries when a skeleton is available.
- The build step emits a QA sidecar that compares raw versus simplified versus coarse representations and records pass, warn, or fail outcomes against configurable thresholds.
- Default QA thresholds and descriptor rationale are documented in a dedicated markdown note aimed at later Milestone 6 and Milestone 11 consumers.
- The build summary surfaces QA warnings clearly and fails only for conditions that should block downstream use.
- Regression coverage exercises both a healthy fixture build and a threshold-violating case.

Verification:
- `make test`
- A focused test that asserts descriptor output fields and QA threshold behavior for fixture geometry

Notes:
Keep the first descriptor set pragmatic rather than exhaustive. Favor metrics that are cheap to compute locally and easy to explain in docs, then leave room for future expansion if Milestone 6 needs more physically specific fidelity checks.
