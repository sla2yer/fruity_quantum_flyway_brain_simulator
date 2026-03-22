Work ticket FW-M11-007: Add surrogate-preservation audits, promotion and demotion policy hooks, and offline mixed-fidelity inspection tooling.
Repository root: /home/jack/Documents/github/personal/fly_neural_simulation/flywire_wave_repo
Priority: high
Source: Milestone 11 roadmap 2026-03-22

Please implement the ticket end-to-end in this repository.
Make the code changes, run the relevant tests or validation commands, and finish with a concise summary of what changed and what you verified.

Problem:
Milestone 11 is not finished when mixed classes merely execute. The roadmap explicitly requires rules for when a neuron should be promoted or demoted in fidelity and checks that lower-fidelity surrogates preserve the needed behavior. Right now the repo has no policy hook for those decisions, no shared audit workflow that compares surrogate behavior against a higher-fidelity reference, and no offline report that helps reviewers decide whether a mixed-fidelity plan is scientifically defensible.

Requested Change:
Implement the first policy and audit layer for mixed fidelity. Add a narrow, deterministic policy surface that can express promotion and demotion recommendations from local descriptors, config, or manifest context, and pair it with an offline inspection workflow that compares surrogate behavior against a declared reference class on local fixtures. The inspection output should surface where a point or skeleton surrogate is acceptable, where it materially diverges, and which roots should be promoted before later readout or validation milestones rely on them.

Acceptance Criteria:
- There is a documented policy hook for fidelity selection or promotion and demotion recommendations that downstream planners can consume deterministically.
- A local inspection workflow can compare a mixed-fidelity run or per-root surrogate against a declared higher-fidelity reference and write a deterministic review artifact.
- The inspection output records per-root fidelity choice, surrogate-versus-reference comparison metrics, blocking versus review-level deviations, and any recommended promotion targets.
- The implementation stays local-artifact-only and does not require live FlyWire access for the audit workflow.
- Automated coverage validates deterministic policy normalization, deterministic report paths, and at least one fixture case where a lower-fidelity surrogate is flagged for review or promotion.

Verification:
- `make test`
- A smoke-style fixture run that executes the mixed-fidelity inspection workflow and asserts deterministic report contents, policy metadata, and promotion-review flags

Notes:
Assume `FW-M11-001` through `FW-M11-006` are already in place. This is not the final validation ladder from Milestone 13; it is the first approximation-audit layer that keeps Milestone 11 honest and gives Grant a structured place to review surrogate quality. Do not attempt to create a git commit as part of this ticket.
